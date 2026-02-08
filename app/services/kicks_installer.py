"""
KICKS Installation Service
Automates KICKS (CICS) installation on MVS 3.8j TK5
"""

import os
import time
import asyncio
import subprocess
import requests
from pathlib import Path
from typing import Optional, Dict, Any, List

# Paths
BASE_DIR = Path(__file__).parent.parent.parent
TK5_DIR = BASE_DIR / "tk5" / "mvs-tk5"
DASD_DIR = TK5_DIR / "dasd"
CONF_DIR = TK5_DIR / "conf"
KICKS_INSTALL_DIR = BASE_DIR / "kicks_install" / "kicks-master" / "kicks-tso-v1r5m0"
XMIT_FILE = KICKS_INSTALL_DIR / "kicks-tso-v1r5m0.xmi"
JCL_DIR = BASE_DIR / "jcl" / "kicks"

# Terminal API base URL
TERMINAL_API = "http://localhost:8080/api/terminal"


class KicksInstaller:
    """Handles KICKS installation process."""
    
    def __init__(self):
        self.status = "idle"
        self.log: List[str] = []
        self.step = 0
        self.total_steps = 6
        self.error: Optional[str] = None
        
    def _log(self, msg: str):
        """Add to installation log."""
        self.log.append(f"[Step {self.step}/{self.total_steps}] {msg}")
        print(f"KICKS: {msg}")
        
    def check_prerequisites(self) -> Dict[str, Any]:
        """Check if all prerequisites are met."""
        checks = {
            "xmit_file": XMIT_FILE.exists(),
            "dasd_dir": DASD_DIR.exists(),
            "kicks_dasd": (DASD_DIR / "kicks0.350").exists(),
            "jcl_dir": JCL_DIR.exists(),
        }
        checks["ready"] = all(checks.values())
        return checks
    
    def check_kicks_installed(self) -> bool:
        """Check if KICKS is already installed by looking for catalog entry."""
        # This would need terminal access - for now check if DASD exists
        return (DASD_DIR / "kicks0.350").exists()
    
    def add_kicks_dasd_config(self) -> bool:
        """Add KICKS DASD to Hercules configuration."""
        self.step = 1
        self._log("Adding KICKS DASD to configuration...")
        
        # Add to cbt_dasd.cnf (placeholder file for additional DASD)
        config_file = CONF_DIR / "cbt_dasd.cnf"
        kicks_config = """#
# KICKS DASD
#
0351 3350 dasd/kicks0.350
"""
        
        try:
            current = config_file.read_text() if config_file.exists() else ""
            if "kicks0" not in current.lower():
                with open(config_file, 'w') as f:
                    f.write(kicks_config)
                self._log("✓ KICKS DASD added to cbt_dasd.cnf")
                return True
            else:
                self._log("✓ KICKS DASD already in configuration")
                return True
        except Exception as e:
            self.error = f"Failed to update config: {e}"
            self._log(f"✗ {self.error}")
            return False
    
    def create_kicks_dasd(self) -> bool:
        """Create KICKS DASD image if it doesn't exist."""
        self.step = 2
        self._log("Checking KICKS DASD image...")
        
        dasd_file = DASD_DIR / "kicks0.350"
        if dasd_file.exists():
            self._log("✓ KICKS DASD image already exists")
            return True
        
        # Try to create with dasdinit
        try:
            result = subprocess.run(
                ["dasdinit", "-a", str(dasd_file), "3350", "111111"],
                capture_output=True,
                text=True,
                timeout=30
            )
            if result.returncode == 0:
                self._log("✓ KICKS DASD image created")
                return True
            else:
                self.error = f"dasdinit failed: {result.stderr}"
                self._log(f"✗ {self.error}")
                return False
        except FileNotFoundError:
            self.error = "dasdinit not found - Hercules tools not in PATH"
            self._log(f"✗ {self.error}")
            return False
        except Exception as e:
            self.error = f"Failed to create DASD: {e}"
            self._log(f"✗ {self.error}")
            return False
    
    def get_hercules_commands(self) -> List[str]:
        """Get list of Hercules console commands needed."""
        return [
            "# Attach KICKS DASD (run at Hercules console)",
            "attach 351 3350 dasd/kicks0.350",
            "# Bring volume online",
            "v 351,online", 
            "# Mount volume",
            "m 351,vol=(sl,kicks0),use=private",
            "# Load XMIT file for RECV370",
            f"devinit 01c {XMIT_FILE} ebcdic",
        ]
    
    def get_mvs_commands(self) -> List[str]:
        """Get list of MVS commands/jobs needed."""
        return [
            "# At TSO READY prompt:",
            "PROFILE PREFIX(KICKS)",
            "# Submit ICKDSF to initialize volume (if new)",
            "SUBMIT 'SYS2.JCLLIB(ICKDSF)'",
            "# Submit DEFCAT to create user catalog", 
            "SUBMIT 'SYS2.JCLLIB(DEFCAT)'",
            "# Run RECV370 to receive XMIT file",
            "EXEC 'SYS2.CMDPROC(RECV370)'",
            "# Unpack installation datasets",
            "See KICKS User's Guide for remaining steps",
        ]
    
    def get_installation_status(self) -> Dict[str, Any]:
        """Get current installation status."""
        prereqs = self.check_prerequisites()
        return {
            "status": self.status,
            "step": self.step,
            "total_steps": self.total_steps,
            "log": self.log[-20:],  # Last 20 entries
            "error": self.error,
            "prerequisites": prereqs,
            "kicks_installed": self.check_kicks_installed(),
            "hercules_commands": self.get_hercules_commands(),
            "mvs_commands": self.get_mvs_commands(),
        }
    
    async def start_installation(self) -> Dict[str, Any]:
        """Start the KICKS installation process."""
        self.status = "running"
        self.log = []
        self.step = 0
        self.error = None
        
        self._log("Starting KICKS installation...")
        
        # Step 1: Check prerequisites
        prereqs = self.check_prerequisites()
        if not prereqs["ready"]:
            missing = [k for k, v in prereqs.items() if not v and k != "ready"]
            self.error = f"Missing prerequisites: {', '.join(missing)}"
            self.status = "failed"
            return self.get_installation_status()
        
        # Step 2: Add DASD config
        if not self.add_kicks_dasd_config():
            self.status = "failed"
            return self.get_installation_status()
        
        # Step 3: Ensure DASD exists
        if not self.create_kicks_dasd():
            self.status = "failed" 
            return self.get_installation_status()
        
        self.step = 3
        self._log("Configuration complete!")
        self._log("")
        self._log("=== MANUAL STEPS REQUIRED ===")
        self._log("1. Restart TK5 to load new DASD config")
        self._log("2. Run Hercules commands listed below")
        self._log("3. Follow MVS commands to complete installation")
        
        self.status = "manual_steps_required"
        return self.get_installation_status()
    
    # Terminal helper methods
    def _send_string(self, text: str) -> bool:
        """Send string to terminal."""
        try:
            r = requests.post(f"{TERMINAL_API}/key", json={"key_type": "string", "value": text}, timeout=5)
            return r.json().get("success", False)
        except:
            return False
    
    def _send_enter(self) -> bool:
        """Send Enter key."""
        try:
            r = requests.post(f"{TERMINAL_API}/key", json={"key_type": "enter", "value": ""}, timeout=5)
            return r.json().get("success", False)
        except:
            return False
    
    def _send_pf(self, num: int) -> bool:
        """Send PF key."""
        try:
            r = requests.post(f"{TERMINAL_API}/key", json={"key_type": "pf", "value": str(num)}, timeout=5)
            return r.json().get("success", False)
        except:
            return False
    
    def _get_screen(self) -> str:
        """Get current screen content."""
        try:
            r = requests.get(f"{TERMINAL_API}/screen", timeout=5)
            data = r.json()
            return data.get("screen", "") if data.get("connected") else ""
        except:
            return ""
    
    def _send_cmd(self, cmd: str) -> bool:
        """Send command and enter."""
        self._send_string(cmd)
        time.sleep(0.3)
        self._send_enter()
        time.sleep(1.5)
        return True
    
    def _wait_for(self, text: str, timeout: int = 30) -> bool:
        """Wait for text on screen."""
        start = time.time()
        while time.time() - start < timeout:
            if text.upper() in self._get_screen().upper():
                return True
            time.sleep(1)
        return False
    
    def _ensure_tso_ready(self) -> bool:
        """Ensure we're at TSO READY prompt."""
        screen = self._get_screen()
        
        if "LOGON" in screen.upper() and "READY" not in screen.upper():
            self._log("Logging into TSO...")
            self._send_string("HERC01")
            self._send_enter()
            time.sleep(2)
            self._send_string("CUL8TR")
            self._send_enter()
            time.sleep(3)
            for _ in range(5):
                if self._wait_for("READY", 2):
                    break
                self._send_enter()
                time.sleep(1)
        
        screen = self._get_screen()
        if "ISPF" in screen.upper() or "OPTION" in screen.upper():
            self._send_pf(3)
            time.sleep(1)
            self._send_pf(3)
            time.sleep(1)
        
        return self._wait_for("READY", 5)
    
    async def run_full_installation(self) -> Dict[str, Any]:
        """Run the full KICKS installation via terminal commands."""
        self.status = "running"
        self.log = []
        self.step = 0
        self.total_steps = 5
        self.error = None
        
        self._log("Starting full KICKS installation...")
        
        # Check terminal connection
        screen = self._get_screen()
        if not screen:
            self.error = "Not connected to mainframe"
            self.status = "failed"
            return self.get_installation_status()
        
        # Step 1: Ensure at TSO READY
        self.step = 1
        self._log("Step 1: Ensuring TSO READY prompt...")
        if not self._ensure_tso_ready():
            self.error = "Could not get to TSO READY prompt"
            self.status = "failed"
            return self.get_installation_status()
        self._log("✓ At TSO READY")
        
        # Step 2: Check/Create catalog
        self.step = 2
        self._log("Step 2: Checking KICKS catalog...")
        self._send_cmd("LISTCAT ENT(KICKS) ALL")
        time.sleep(2)
        screen = self._get_screen()
        
        if "ALIAS" in screen.upper() and "KICKS" in screen:
            self._log("✓ KICKS catalog alias exists")
        else:
            self._log("KICKS catalog not found - needs to be created")
            self._log("Run these at Hercules console first:")
            self._log("  v 351,online")
            self._log("  m 351,vol=(sl,kicks0),use=private")
            self._log("")
            self._log("Then submit DEFCAT job to create catalog")
            self.status = "needs_hercules_commands"
            return self.get_installation_status()
        
        # Step 3: Set KICKS prefix
        self.step = 3
        self._log("Step 3: Setting KICKS prefix...")
        self._send_cmd("PROFILE PREFIX(KICKS)")
        self._log("✓ Prefix set")
        
        # Step 4: Check if KICKS datasets exist
        self.step = 4
        self._log("Step 4: Checking KICKS datasets...")
        self._send_cmd("LISTCAT ENT(KICKS.KICKSSYS.V1R5M0.CLIST) ALL")
        time.sleep(2)
        screen = self._get_screen()
        
        if "KICKS.KICKSSYS" in screen and "NONVSAM" in screen.upper():
            self._log("✓ KICKS datasets already installed!")
            self.status = "installed"
            self._log("")
            self._log("KICKS is ready! To start:")
            self._log("  EXEC 'KICKS.KICKSSYS.V1R5M0.CLIST(KICKS)'")
            return self.get_installation_status()
        else:
            self._log("KICKS datasets not found")
            self._log("Need to upload XMIT file via RECV370")
            self._log("")
            self._log("Run at Hercules console:")
            self._log(f"  devinit 01c {XMIT_FILE} ebcdic")
            self._log("")
            self._log("Then run: EXEC 'SYS2.CMDPROC(RECV370)'")
            self.status = "needs_xmit_upload"
            return self.get_installation_status()


# Global installer instance
_installer: Optional[KicksInstaller] = None

def get_installer() -> KicksInstaller:
    """Get or create installer instance."""
    global _installer
    if _installer is None:
        _installer = KicksInstaller()
    return _installer
