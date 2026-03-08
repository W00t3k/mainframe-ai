"""
KICKS Service
Start, stop, and check KICKS (CICS) on MVS 3.8j TK5.
Works via the terminal API (s3270 connection).
"""

import time
import requests
from pathlib import Path
from typing import Optional, Dict, Any, List

BASE_DIR = Path(__file__).parent.parent.parent
TK5_DIR = BASE_DIR / "tk5" / "mvs-tk5"
DASD_DIR = TK5_DIR / "dasd"
TERMINAL_API = "http://localhost:8080/api/terminal"

KICKS_START_CMD = "EXEC 'KICKS.KICKSSYS.V1R5M0.CLIST(KICKS)'"
KICKS_STOP_CMD = "KSSF"


class KicksService:
    """Manages KICKS lifecycle via the web app terminal."""

    def __init__(self):
        self.running = False
        self.last_check: Optional[Dict] = None

    # ── Terminal helpers ──────────────────────────────────

    def _get_screen(self) -> str:
        try:
            r = requests.get(f"{TERMINAL_API}/screen", timeout=5)
            d = r.json()
            return d.get("screen", "") if d.get("connected") else ""
        except Exception:
            return ""

    def _send_string(self, text: str):
        try:
            requests.post(f"{TERMINAL_API}/key",
                          json={"key_type": "string", "value": text}, timeout=5)
        except Exception:
            pass

    def _send_key(self, key_type: str, value: str = ""):
        try:
            requests.post(f"{TERMINAL_API}/key",
                          json={"key_type": key_type, "value": value}, timeout=5)
        except Exception:
            pass

    def _send_enter(self):
        self._send_key("enter")

    def _send_pf(self, n: int):
        self._send_key("pf", str(n))

    def _send_clear(self):
        self._send_key("clear")

    def _send_cmd(self, cmd: str, delay: float = 1.5):
        self._send_string(cmd)
        time.sleep(0.3)
        self._send_enter()
        time.sleep(delay)

    def _wait_for(self, text: str, timeout: int = 15) -> bool:
        end = time.time() + timeout
        while time.time() < end:
            if text.upper() in self._get_screen().upper():
                return True
            time.sleep(0.5)
        return False

    def _at_ready(self) -> bool:
        return "READY" in self._get_screen().upper()

    def _navigate_to_ready(self) -> bool:
        """Try to get to TSO READY prompt from wherever we are."""
        screen = self._get_screen()
        if not screen:
            return False

        # Already at READY
        if "READY" in screen.upper():
            return True

        # At VTAM logon
        if "LOGON" in screen.upper() and "==>" in screen:
            self._send_cmd("TSO", 2)
            screen = self._get_screen()

        # At TSO logon panel
        if "ENTER USERID" in screen.upper() or "TSO/E LOGON" in screen.upper():
            self._send_cmd("HERC01", 1)
            screen = self._get_screen()
            if "PASSWORD" in screen.upper() or "ENTER" in screen.upper():
                self._send_cmd("CUL8TR", 3)

        # Press through messages
        for _ in range(5):
            screen = self._get_screen()
            if "READY" in screen.upper():
                return True
            if "ISPF" in screen.upper() or "OPTION" in screen.upper():
                self._send_pf(3)
                time.sleep(1)
                continue
            self._send_enter()
            time.sleep(1)

        return "READY" in self._get_screen().upper()

    # ── Public API ────────────────────────────────────────

    def check_status(self) -> Dict[str, Any]:
        """Check KICKS installation and runtime status."""
        result = {
            "dasd_exists": (DASD_DIR / "kicks0.350").exists(),
            "dasd_size_mb": 0,
            "terminal_connected": False,
            "catalog_exists": False,
            "datasets_exist": False,
            "kicks_running": False,
            "screen_snippet": "",
            "log": [],
        }

        dasd = DASD_DIR / "kicks0.350"
        if dasd.exists():
            result["dasd_size_mb"] = round(dasd.stat().st_size / 1024 / 1024)

        screen = self._get_screen()
        if not screen:
            result["log"].append("Terminal not connected to mainframe")
            self.last_check = result
            return result

        result["terminal_connected"] = True
        result["screen_snippet"] = screen[:200]

        # Check if KICKS is currently running (banner or transaction screen)
        upper = screen.upper()
        if "K I C K S" in upper or ("KICKS" in upper and "TRANSACTION" in upper):
            result["kicks_running"] = True
            self.running = True
            result["log"].append("KICKS is currently running")
            self.last_check = result
            return result

        # We need to be at READY to check datasets
        if "READY" not in upper:
            result["log"].append("Not at TSO READY — cannot check datasets")
            self.last_check = result
            return result

        # Check catalog alias
        self._send_cmd("LISTCAT ENT(KICKS) ALL", 2)
        screen = self._get_screen()
        if "ALIAS" in screen.upper() and "KICKS" in screen:
            result["catalog_exists"] = True
            result["log"].append("KICKS catalog alias found")
        else:
            result["log"].append("KICKS catalog alias NOT found")

        # Clear output
        for _ in range(3):
            if "READY" in self._get_screen().upper():
                break
            self._send_enter()
            time.sleep(0.5)

        # Check CLIST dataset
        self._send_cmd("LISTDS 'KICKS.KICKSSYS.V1R5M0.CLIST'", 2)
        screen = self._get_screen()
        if "KICKS.KICKSSYS" in screen and "NOT IN CATALOG" not in screen.upper():
            result["datasets_exist"] = True
            result["log"].append("KICKS datasets found")
        else:
            result["log"].append("KICKS datasets NOT found")

        # Clear
        for _ in range(3):
            if "READY" in self._get_screen().upper():
                break
            self._send_enter()
            time.sleep(0.5)

        self.last_check = result
        return result

    def start_kicks(self) -> Dict[str, Any]:
        """Start KICKS from TSO READY prompt."""
        result = {"success": False, "message": "", "log": []}

        screen = self._get_screen()
        if not screen:
            result["message"] = "Terminal not connected"
            return result

        # Already running?
        if "K I C K S" in screen.upper() or ("KICKS" in screen.upper() and "TRANSACTION" in screen.upper()):
            result["success"] = True
            result["message"] = "KICKS is already running"
            self.running = True
            return result

        # Navigate to READY
        if not self._navigate_to_ready():
            result["message"] = "Could not reach TSO READY prompt"
            result["log"].append(f"Screen: {self._get_screen()[:200]}")
            return result

        result["log"].append("At TSO READY")

        # Start KICKS
        result["log"].append(f"Running: {KICKS_START_CMD}")
        self._send_cmd(KICKS_START_CMD, 5)

        # Wait for KICKS to appear
        screen = self._get_screen()
        result["log"].append(f"Screen after EXEC: {screen[:200]}")

        # KICKS shows startup messages then banner on Enter
        for _ in range(5):
            screen = self._get_screen()
            upper = screen.upper()
            if "K I C K S" in upper or "KICKS" in upper:
                result["success"] = True
                result["message"] = "KICKS started successfully"
                self.running = True
                return result
            if "ERROR" in upper or "NOT FOUND" in upper or "NOT IN CATALOG" in upper:
                result["message"] = "KICKS failed to start — datasets may not be installed"
                result["log"].append(screen[:300])
                return result
            self._send_enter()
            time.sleep(2)

        # One more check
        screen = self._get_screen()
        if "KICKS" in screen.upper():
            result["success"] = True
            result["message"] = "KICKS started"
            self.running = True
        else:
            result["message"] = "KICKS may not have started — check terminal"
            result["log"].append(screen[:300])

        return result

    def stop_kicks(self) -> Dict[str, Any]:
        """Stop KICKS cleanly with KSSF."""
        result = {"success": False, "message": "", "log": []}

        screen = self._get_screen()
        if not screen:
            result["message"] = "Terminal not connected"
            return result

        # Send CLEAR then KSSF
        self._send_clear()
        time.sleep(0.5)
        self._send_cmd(KICKS_STOP_CMD, 3)

        screen = self._get_screen()
        result["log"].append(f"After KSSF: {screen[:200]}")

        # Press enter to get back to READY
        for _ in range(3):
            self._send_enter()
            time.sleep(1)
            if "READY" in self._get_screen().upper():
                break

        self.running = False
        result["success"] = True
        result["message"] = "KICKS stopped"
        return result

    def get_installation_status(self) -> Dict[str, Any]:
        """Legacy compat wrapper."""
        return self.last_check or self.check_status()


_service: Optional[KicksService] = None

def get_installer() -> KicksService:
    """Get or create KICKS service instance."""
    global _service
    if _service is None:
        _service = KicksService()
    return _service
