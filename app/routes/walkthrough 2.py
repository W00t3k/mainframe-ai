"""
Walkthrough API Routes

Endpoints for the autonomous guided walkthrough system.
"""

import time as _time
import threading
import httpx
import logging
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app.constants.walkthrough_scripts import WALKTHROUGH_SCRIPTS
from app.config import get_config

logger = logging.getLogger(__name__)

router = APIRouter(tags=["walkthrough"])

# Import agent_tools
try:
    from agent_tools import connection, connect_mainframe, read_screen, read_screen_with_color, send_terminal_key
    AGENT_TOOLS_AVAILABLE = True
except ImportError:
    AGENT_TOOLS_AVAILABLE = False
    connection = None
    connect_mainframe = None
    read_screen = lambda: "[Not connected]"
    read_screen_with_color = lambda: "[Not connected]"
    send_terminal_key = lambda *args: {"success": False}


class WalkthroughRunner:
    """Server-side autonomous walkthrough executor."""

    # Error patterns that indicate the terminal is in a bad state
    ERROR_PATTERNS = [
        "INVALID KEYWORD",
        "REENTER",
        "NOT FOUND",
        "INVALID OPTION",
        "COMMAND NOT RECOGNIZED",
        "NOT AUTHORIZED",
        "IKJ56703",
        "IKJ56429",
        "ENTER FILE NAME",
        "INVALID COMMAND",
        "SYNTAX ERROR",
        "NOT VALID",
    ]

    def __init__(self):
        self.running = False
        self.paused = False
        self.current_step = 0
        self.total_steps = 0
        self.current_title = ""
        self.current_narration = ""
        self.current_screen = ""
        self.current_control_plane = ""
        self.walkthrough_name = ""
        self.log: list[dict] = []
        self.finished = False
        self.error: str | None = None
        self.display_seconds = 4.0
        self._thread: threading.Thread | None = None
        self._recovery_count = 0
        self._max_recoveries = 3  # max recoveries per step

    def start(self, name: str, target: str, speed: float = 4.0, lhost: str = "10.0.0.1", lport: str = "4444"):
        if self.running and (self._thread is None or not self._thread.is_alive()):
            self.running = False
        if self.running:
            return
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)
        try:
            if connection and connection.connected:
                screen = self._read_screen_safe()
                if self._is_logged_in(screen.upper()):
                    self._tso_logoff()
        except Exception:
            pass
        self.running = True
        self.paused = False
        self.finished = False
        self.error = None
        self.current_step = 0
        self.total_steps = 0
        self.current_title = "Starting..."
        self.current_narration = ""
        self.current_screen = ""
        self.current_control_plane = ""
        self.walkthrough_name = ""
        self.log = []
        self.display_seconds = speed
        self.lhost = lhost
        self.lport = lport
        self._thread = threading.Thread(
            target=self._run, args=(name, target), daemon=True
        )
        self._thread.start()

    def stop(self):
        self.running = False

    def pause(self):
        self.paused = True

    def resume(self):
        self.paused = False

    def get_status(self) -> dict:
        if self.running and (self._thread is None or not self._thread.is_alive()):
            self.running = False
        
        # Colorize the cached screen instead of doing a live read
        # (live reads race with the walkthrough thread's connect/disconnect)
        screen_html = ""
        if self.current_screen and not self.current_screen.startswith("["):
            try:
                from agent_tools import colorize_3270_screen
                screen_html = colorize_3270_screen(self.current_screen)
            except Exception:
                screen_html = self.current_screen
        
        return {
            "running": self.running,
            "paused": self.paused,
            "step": self.current_step,
            "total": self.total_steps,
            "title": self.current_title,
            "narration": self.current_narration,
            "screen": self.current_screen,
            "screen_html": screen_html,
            "control_plane": self.current_control_plane,
            "walkthrough_name": self.walkthrough_name,
            "finished": self.finished,
            "error": self.error,
            "log": list(self.log),
        }

    def _run(self, name: str, target: str):
        script = WALKTHROUGH_SCRIPTS.get(name)
        if not script:
            self.error = f"Unknown walkthrough: {name}"
            self.running = False
            return

        self.walkthrough_name = script["title"]
        steps = script["steps"]
        self.total_steps = len(steps)
        # Connect to mainframe (logoff any existing session first)
        try:
            self.current_narration = "Connecting to mainframe..."
            from agent_tools import disconnect_mainframe
            try:
                if connection and connection.connected:
                    screen = self._read_screen_safe()
                    upper = screen.upper()
                    # If stuck in error state, escape first
                    if self._detect_error(screen):
                        logger.info("Pre-connect: error state detected, escaping")
                        screen = self._escape_to_ready()
                        upper = screen.upper()
                    if self._is_logged_in(upper):
                        self._tso_logoff()
                    disconnect_mainframe()
                    _time.sleep(1)
            except Exception:
                pass

            connect_mainframe(target)
            _time.sleep(3)
            self.current_screen = self._read_screen_safe()
        except Exception as e:
            self.error = f"Failed to connect: {e}"
            self.running = False
            return

        for idx, step in enumerate(steps):
            if not self.running:
                break

            while self.paused and self.running:
                _time.sleep(0.25)

            if not self.running:
                break

            self.current_step = idx
            self.current_title = step["title"]
            self.current_control_plane = step.get("control_plane", "")
            self.current_narration = ""

            log_entry = {
                "step": idx,
                "title": step["title"],
                "control_plane": step.get("control_plane", ""),
                "narration": "",
                "executing": True,
            }
            self.log.append(log_entry)

            self._recovery_count = 0  # reset per step
            try:
                for action in step.get("actions", []):
                    if not self.running:
                        break
                    while self.paused and self.running:
                        _time.sleep(0.25)
                    if not self.running:
                        break
                    self._exec_action(action, target)
                    if action["type"] not in ("wait",):
                        try:
                            self.current_screen = read_screen()
                        except Exception:
                            self.current_screen = connection.current_screen if connection else ""
                        # AI-powered screen recovery
                        if self._detect_error(self.current_screen):
                            logger.info(f"Error detected at step {idx+1}, starting AI recovery...")
                            self.current_narration = "AI Recovery: analyzing terminal screen..."
                            recovered = self._recover_from_error(self.current_screen, step, target)
                            if not recovered:
                                logger.warning(f"Pattern recovery failed at step {idx+1}, using AI escape")
                                recovered = self._llm_recover(self.current_screen, step, target)
                            if recovered:
                                logger.info(f"Recovery succeeded at step {idx+1}, waiting before continuing")
                                _time.sleep(3)  # wait for terminal to settle
                            else:
                                logger.error(f"All recovery failed at step {idx+1}")
            except Exception as e:
                self.error = f"Step {idx + 1} failed: {e}"
                self.running = False
                break

            try:
                self.current_screen = read_screen()
            except Exception:
                self.current_screen = connection.current_screen if connection else ""

            narration = step["narration"]
            narration = narration.replace("{{LHOST}}", self.lhost).replace("{{LPORT}}", self.lport)
            log_entry["narration"] = narration
            log_entry["executing"] = False
            self.current_narration = narration

            step_display = step.get("display_seconds", self.display_seconds)
            wait_end = _time.time() + step_display
            while _time.time() < wait_end and self.running:
                while self.paused and self.running:
                    _time.sleep(0.25)
                _time.sleep(0.2)

        if self.running:
            self.finished = True
        self.running = False

    def _detect_error(self, screen: str) -> bool:
        """Check if the screen contains error patterns."""
        upper = screen.upper()
        for pattern in self.ERROR_PATTERNS:
            if pattern in upper:
                return True
        return False

    def _recover_from_error(self, screen: str, step: dict, target: str) -> bool:
        """Pattern-based recovery from known error states.
        
        Returns True if recovery succeeded and we're back to a usable state.
        """
        if self._recovery_count >= self._max_recoveries:
            logger.warning("Max recovery attempts reached for this step")
            return False
        self._recovery_count += 1
        upper = screen.upper()
        logger.info(f"Recovery attempt {self._recovery_count}: screen contains error")

        # "REENTER -" or "ENTER FILE NAME -" — we're in TSO line-mode EDIT
        # Recovery: type END to exit, then CLEAR
        if "REENTER" in upper or "ENTER FILE NAME" in upper:
            send_terminal_key("string", "END")
            send_terminal_key("enter")
            _time.sleep(2)
            screen = self._read_screen_safe()
            upper = screen.upper()
            # May need multiple ENDs
            for _ in range(5):
                if "REENTER" in upper or "ENTER FILE NAME" in upper:
                    send_terminal_key("string", "END")
                    send_terminal_key("enter")
                    _time.sleep(1)
                    screen = self._read_screen_safe()
                    upper = screen.upper()
                else:
                    break
            # If still stuck, try CLEAR
            if self._detect_error(screen):
                send_terminal_key("clear")
                _time.sleep(1)
                screen = self._read_screen_safe()
            self.current_screen = screen
            return not self._detect_error(screen)

        # "INVALID KEYWORD" — wrong command for current context
        # Recovery: CLEAR screen and try to get to READY or known state
        if "INVALID KEYWORD" in upper or "INVALID OPTION" in upper or "INVALID COMMAND" in upper:
            send_terminal_key("clear")
            _time.sleep(1)
            screen = self._read_screen_safe()
            upper = screen.upper()
            # If at a prompt, try pressing PF3 to back out
            if not self._is_logged_in(upper) and "LOGON" not in upper:
                for _ in range(4):
                    send_terminal_key("pf", "3")
                    _time.sleep(1.5)
                    screen = self._read_screen_safe()
                    upper = screen.upper()
                    if self._is_logged_in(upper) or "LOGON" in upper:
                        break
            self.current_screen = screen
            return not self._detect_error(screen)

        # "NOT FOUND" — dataset or member doesn't exist
        if "NOT FOUND" in upper:
            send_terminal_key("pf", "3")
            _time.sleep(1)
            screen = self._read_screen_safe()
            self.current_screen = screen
            return not self._detect_error(screen)

        # "NOT AUTHORIZED" — RACF denied access
        if "NOT AUTHORIZED" in upper:
            send_terminal_key("pf", "3")
            _time.sleep(1)
            screen = self._read_screen_safe()
            self.current_screen = screen
            return not self._detect_error(screen)

        # Generic: try CLEAR + PF3
        send_terminal_key("clear")
        _time.sleep(1)
        send_terminal_key("pf", "3")
        _time.sleep(1)
        screen = self._read_screen_safe()
        self.current_screen = screen
        return not self._detect_error(screen)

    def _llm_recover(self, screen: str, step: dict, target: str) -> bool:
        """Use the LLM to recover from an error state.
        
        Delegates to _escape_to_ready which uses AI on every iteration.
        Returns True if recovery succeeded.
        """
        logger.info(f"LLM recover called for step: {step.get('title', 'unknown')}")
        screen = self._escape_to_ready()
        return not self._detect_error(screen)

    def _exec_action(self, action: dict, target: str):
        atype = action["type"]
        if atype == "connect":
            # Always try to connect if not connected
            try:
                if not connection or not connection.connected:
                    result = connect_mainframe(target)
                    _time.sleep(2)
                    # Read initial screen
                    self.current_screen = self._read_screen_safe()
            except Exception as e:
                self.error = f"Connection failed: {e}"
                self.running = False
                return
        elif atype == "string":
            send_terminal_key("string", action["value"])
        elif atype == "enter":
            send_terminal_key("enter")
            _time.sleep(1.5)
        elif atype == "clear":
            send_terminal_key("clear")
            _time.sleep(1.5)
        elif atype == "pf":
            send_terminal_key("pf", str(action["value"]))
            _time.sleep(1.5)
        elif atype == "tab":
            send_terminal_key("tab")
            _time.sleep(0.3)
        elif atype == "home":
            send_terminal_key("home")
            _time.sleep(0.3)
        elif atype == "eraseeof":
            send_terminal_key("eraseeof")
            _time.sleep(0.3)
        elif atype == "wait":
            _time.sleep(action.get("seconds", 1))
        elif atype == "tso_login":
            userid = action.get("userid", "HERC01")
            password = action.get("password", "CUL8TR")
            self._tso_login(userid, password, target)
        elif atype == "tso_logoff":
            self._tso_logoff()
        elif atype == "enter_rfe":
            self._enter_rfe()

    def _read_screen_safe(self) -> str:
        try:
            return read_screen()
        except Exception:
            return connection.current_screen if connection else ""
    
    def _read_screen_with_color_safe(self) -> str:
        """Read screen with color HTML formatting."""
        try:
            return read_screen_with_color()
        except Exception:
            return self._read_screen_safe()

    def _enter_rfe(self):
        """Enter RFE/ISPF from either TSO Apps Menu or TSO READY.

        TK5 login lands on TSO Applications Menu (option 1 = RFE).
        If already at READY, type ISPF. If at apps menu, select 1.
        """
        screen = self._read_screen_safe()
        upper = screen.upper()

        # Already in RFE/ISPF Primary Option Menu?
        if ("ISPF" in upper or "RFE" in upper) and ("OPTION" in upper or "BROWSE" in upper or "EDIT" in upper):
            # Check if at ISPF primary menu (shows BROWSE, EDIT, UTILITIES)
            if "BROWSE" in upper and "EDIT" in upper and "UTILITIES" in upper:
                return

        # At TSO Applications Menu — select option 1 (RFE)
        if ("RFE" in upper and "RPF" in upper) or "TSOAPPLS" in upper or ("IMON" in upper and "QUEUE" in upper):
            send_terminal_key("home")
            _time.sleep(0.2)
            send_terminal_key("eraseeof")
            _time.sleep(0.2)
            send_terminal_key("string", "1")
            send_terminal_key("enter")
            _time.sleep(4)
            self.current_screen = self._read_screen_safe()
            return

        # At TSO READY — type ISPF
        if "READY" in upper:
            send_terminal_key("home")
            _time.sleep(0.2)
            send_terminal_key("eraseeof")
            _time.sleep(0.2)
            send_terminal_key("string", "ISPF")
            send_terminal_key("enter")
            _time.sleep(4)
            self.current_screen = self._read_screen_safe()
            return

        # Unknown state — try pressing Enter then check again
        send_terminal_key("enter")
        _time.sleep(2)
        screen = self._read_screen_safe()
        upper = screen.upper()
        if "READY" in upper:
            send_terminal_key("home")
            _time.sleep(0.2)
            send_terminal_key("eraseeof")
            _time.sleep(0.2)
            send_terminal_key("string", "ISPF")
            send_terminal_key("enter")
            _time.sleep(4)
        elif ("RFE" in upper and "RPF" in upper) or "TSOAPPLS" in upper:
            send_terminal_key("home")
            _time.sleep(0.2)
            send_terminal_key("eraseeof")
            _time.sleep(0.2)
            send_terminal_key("string", "1")
            send_terminal_key("enter")
            _time.sleep(4)
        self.current_screen = self._read_screen_safe()

    def _tso_logoff(self):
        # Check if we're already at VTAM/LOGON — nothing to logoff
        screen = self._read_screen_safe()
        upper = screen.upper()
        if "LOGON" in upper or "VTAM" in upper or "USS" in upper:
            return
        # If stuck in error state, escape first
        if self._detect_error(screen):
            logger.info("Logoff: error state detected, escaping first")
            screen = self._escape_to_ready()
            upper = screen.upper()
            if "LOGON" in upper or "VTAM" in upper or "USS" in upper:
                return
        if not self._is_logged_in(upper):
            return
        
        for _ in range(6):
            try:
                send_terminal_key("pf", "3")
                _time.sleep(1.5)
            except Exception:
                break
            screen = self._read_screen_safe()
            upper = screen.upper()
            if "READY" in upper or "LOGON" in upper or "VTAM" in upper:
                break
        _time.sleep(1)
        screen = self._read_screen_safe()
        upper = screen.upper()
        if "LOGON" in upper or "VTAM" in upper or "USS" in upper:
            return
        if "READY" in upper:
            send_terminal_key("string", "LOGOFF")
            send_terminal_key("enter")
            _time.sleep(2)

    def _is_logged_in(self, upper: str) -> bool:
        """Check if we're at a logged-in screen (READY, ISPF/RFE, or TSO Apps Menu)."""
        if "READY" in upper:
            return True
        if "ISPF" in upper and "OPTION" in upper:
            return True
        # TSO Applications Menu (TK5 shows this after login)
        if "RFE" in upper and "RPF" in upper:
            return True
        if "TSOAPPLS" in upper:
            return True
        if "IMON" in upper and "QUEUE" in upper:
            return True
        return False

    def _is_post_login(self, upper: str) -> bool:
        """Check if we're at a post-login screen that needs Enter to advance.
        
        After a successful login or reconnect, TK5 may show:
        - IKT00300I LOGON RECONNECT SUCCESSFUL
        - SESSION ESTABLISHED
        - IKJ56455I (broadcast messages)
        - Fortune screen
        - Mostly blank screen after reconnect
        """
        if "IKT00300" in upper or "SESSION ESTABLISHED" in upper:
            return True
        if "RECONNECT SUCCESSFUL" in upper:
            return True
        if "IKJ56455" in upper:
            return True
        if "LOGON IN PROGRESS" in upper:
            return True
        return False

    def _escape_to_ready(self) -> str:
        """Use AI to escape from any stuck terminal state back to TSO READY.
        
        For known error patterns (REENTER, INVALID KEYWORD), use CLEAR directly
        without asking the LLM — the LLM sometimes returns wrong actions.
        For unknown states, ask the LLM.
        Waits between each action so the terminal has time to respond."""
        for attempt in range(6):
            screen = self._read_screen_safe()
            self.current_screen = screen
            upper = screen.upper()
            # Already at a usable state?
            if self._is_logged_in(upper):
                return screen
            if "LOGON" in upper and "===>" in screen:
                return screen

            # ---- KNOWN PATTERNS: handle directly, don't ask LLM ----
            # REENTER at TSO prompt — CLEAR is the ONLY correct action
            # END is INVALID here and causes an infinite loop
            if "REENTER" in upper:
                logger.info(f"AI escape attempt {attempt+1}: REENTER detected, sending CLEAR (pattern override)")
                send_terminal_key("clear")
                _time.sleep(3)
                continue

            # INVALID KEYWORD — CLEAR dismisses it
            if "INVALID KEYWORD" in upper or "INVALID COMMAND" in upper:
                logger.info(f"AI escape attempt {attempt+1}: INVALID KEYWORD detected, sending CLEAR (pattern override)")
                send_terminal_key("clear")
                _time.sleep(3)
                continue

            # ENTER FILE NAME — we're in TSO EDIT, END exits
            if "ENTER FILE NAME" in upper:
                logger.info(f"AI escape attempt {attempt+1}: ENTER FILE NAME detected, sending END (pattern override)")
                send_terminal_key("home")
                _time.sleep(0.3)
                send_terminal_key("eraseeof")
                _time.sleep(0.3)
                send_terminal_key("string", "END")
                send_terminal_key("enter")
                _time.sleep(3)
                continue

            # ---- UNKNOWN STATE: ask the LLM ----
            action = self._ask_llm_recovery_action(screen)
            logger.info(f"AI escape attempt {attempt+1}: LLM says '{action}'")

            if action == "END":
                send_terminal_key("home")
                _time.sleep(0.3)
                send_terminal_key("eraseeof")
                _time.sleep(0.3)
                send_terminal_key("string", "END")
                send_terminal_key("enter")
                _time.sleep(3)
            elif action == "PF3":
                send_terminal_key("pf", "3")
                _time.sleep(3)
            elif action == "CLEAR":
                send_terminal_key("clear")
                _time.sleep(3)
            elif action == "LOGOFF":
                send_terminal_key("home")
                _time.sleep(0.3)
                send_terminal_key("eraseeof")
                _time.sleep(0.3)
                send_terminal_key("string", "LOGOFF")
                send_terminal_key("enter")
                _time.sleep(4)
            elif action == "ENTER":
                send_terminal_key("enter")
                _time.sleep(3)
            elif action == "CANCEL":
                send_terminal_key("string", "CANCEL")
                send_terminal_key("enter")
                _time.sleep(3)
            else:
                send_terminal_key("clear")
                _time.sleep(3)

        screen = self._read_screen_safe()
        self.current_screen = screen
        return screen

    def _ask_llm_recovery_action(self, screen: str) -> str:
        """Ask the LLM to analyze the screen and return a single recovery action.
        
        Returns one of: CLEAR, PF3, ENTER, LOGOFF, END, CANCEL
        Falls back to pattern matching if LLM is unavailable."""
        try:
            config = get_config()
            first_lines = "\n".join(screen.split("\n")[:24])
            prompt = f"""You are an IBM MVS 3.8j mainframe terminal recovery agent.
The terminal is stuck in an error state. Your job is to get back to TSO READY or the VTAM logon screen.

Current terminal screen:
---
{first_lines}
---

Common MVS error states and correct recovery:
- "REENTER -" at TSO command prompt = previous command was invalid. Send CLEAR to dismiss and return to READY. Do NOT send END (that is only valid inside EDIT).
- "ENTER FILE NAME -" = stuck in TSO EDIT line mode. Send END to exit the editor.
- "INVALID KEYWORD" = wrong command for current context. Send CLEAR to dismiss and return to READY.
- "NOT FOUND" = dataset missing. Send PF3 to go back.
- "NOT AUTHORIZED" = RACF denied. Send PF3 to go back.
- "IKJ56" messages = TSO errors. Send CLEAR to dismiss.
- RFE/ISPF panels = Send PF3 to exit back toward READY.
- If deeply nested, multiple PF3 presses needed.

IMPORTANT: CLEAR is almost always the safest action for TSO error prompts. It clears the screen and returns to READY.

What SINGLE action should we take RIGHT NOW?
Reply with EXACTLY one word: CLEAR, PF3, ENTER, LOGOFF, END, or CANCEL"""

            resp = httpx.post(
                f"{config.OLLAMA_URL}/api/generate",
                json={
                    "model": config.OLLAMA_MODEL,
                    "prompt": prompt,
                    "stream": False,
                    "options": {"temperature": 0.1, "num_predict": 10},
                },
                timeout=15.0,
            )
            if resp.status_code == 200:
                answer = resp.json().get("response", "").strip().upper()
                # Extract just the action word
                for cmd in ["LOGOFF", "CANCEL", "CLEAR", "ENTER", "END", "PF3"]:
                    if cmd in answer:
                        return cmd
            # LLM didn't give a valid answer — fall back to pattern
            return self._pattern_recovery_action(screen)
        except Exception as e:
            logger.warning(f"LLM recovery unavailable: {e}")
            return self._pattern_recovery_action(screen)

    def _pattern_recovery_action(self, screen: str) -> str:
        """Fallback pattern-based recovery when LLM is unavailable."""
        upper = screen.upper()
        # REENTER at TSO prompt — CLEAR dismisses it back to READY
        if "REENTER" in upper:
            return "CLEAR"
        # ENTER FILE NAME — we're inside TSO EDIT, END exits
        if "ENTER FILE NAME" in upper:
            return "END"
        if "INVALID KEYWORD" in upper or "INVALID" in upper:
            return "CLEAR"
        if "NOT FOUND" in upper or "NOT AUTHORIZED" in upper:
            return "PF3"
        return "CLEAR"

    def _press_through_screens(self) -> str:
        """Press Enter through broadcast/fortune/info screens until we reach
        a usable screen (READY, ISPF/RFE, TSO Apps Menu, or Logon)."""
        for _ in range(10):
            screen = self._read_screen_safe()
            self.current_screen = screen
            upper = screen.upper()
            if self._is_logged_in(upper):
                return screen
            # VTAM/Logon screen means we're NOT logged in — stop pressing
            if ("LOGON ===>" in screen or "Logon ===>" in screen) and "IKT00300" not in upper:
                return screen
            if "IKJ56400" in upper and "IKT00300" not in upper:
                return screen
            # Error state — escape instead of pressing Enter blindly
            if self._detect_error(screen):
                logger.info("_press_through_screens: detected error, escaping to READY")
                return self._escape_to_ready()
            # Post-login screens (reconnect success, broadcast, fortune) — press Enter
            if self._is_post_login(upper):
                send_terminal_key("enter")
                _time.sleep(3)
                continue
            # Mostly blank screen after reconnect — press Enter to advance
            stripped = screen.strip()
            if len(stripped) < 80 or stripped.count('\n') < 3:
                send_terminal_key("enter")
                _time.sleep(2)
                continue
            # Broadcast messages, fortune, "PRESS ENTER", IKJ56455 — press Enter
            send_terminal_key("enter")
            _time.sleep(2)
        return self._read_screen_safe()

    def _tso_login(self, userid: str, password: str, target: str):
        """Handle TSO login with robust state machine for all TK5 screen states.
        
        TK5 login flow (per featherriver.net):
        1. VTAM screen — Logon ===> (may be missing on first connect, press Enter)
        2. Enter userid at Logon prompt
        3. Password screen
        4. Broadcast messages screen — press Enter
        5. Fortune screen — press Enter  
        6. TSO Applications Menu (RFE, RPF, IMON, QUEUE, etc.)
        """
        max_attempts = 14
        for attempt in range(max_attempts):
            if not self.running:
                return

            if connection and not connection.connected:
                connect_mainframe(target)
                _time.sleep(2)

            screen = self._read_screen_safe()
            self.current_screen = screen
            upper = screen.upper()

            # ── Success checks ──
            if self._is_logged_in(upper):
                return

            # ── ERROR STATE — must check BEFORE post-login ──
            # After reconnect, screen may show BOTH "IKT00300 RECONNECT SUCCESSFUL"
            # AND "INVALID KEYWORD" / "REENTER" from the previous broken session.
            # We must escape the error first, not press Enter into it.
            if self._detect_error(screen):
                logger.info(f"Login attempt {attempt}: error on screen, using AI to escape")
                screen = self._escape_to_ready()
                upper = screen.upper()
                if self._is_logged_in(upper):
                    return
                if "LOGON" in upper and "===>" in screen:
                    continue
                if "IKJ56400" in upper:
                    continue
                continue

            # ── Post-login screen (reconnect success, broadcast, etc.) ──
            if self._is_post_login(upper):
                screen = self._press_through_screens()
                if self._is_logged_in(screen.upper()):
                    return
                continue

            # ── IKJ56400A "ENTER LOGON OR LOGOFF" ──
            if "IKJ56400" in upper or "ENTER LOGON OR LOGOFF" in upper:
                reconnect = "IN USE" in upper or "LOGON REJECTED" in upper
                cmd = f"LOGON {userid} RECONNECT" if reconnect else f"LOGON {userid}"
                send_terminal_key("home")
                _time.sleep(0.3)
                send_terminal_key("eraseeof")
                _time.sleep(0.3)
                send_terminal_key("string", cmd)
                send_terminal_key("enter")
                _time.sleep(4)
                screen = self._read_screen_safe()
                self.current_screen = screen
                upper = screen.upper()
                if "PASSWORD" in upper or "IKJ56476" in upper or "ENTER CURRENT" in upper:
                    send_terminal_key("string", password)
                    send_terminal_key("enter")
                    _time.sleep(4)
                # Press through broadcast/fortune screens
                screen = self._press_through_screens()
                if self._is_logged_in(screen.upper()):
                    return
                continue

            # ── "IN USE" without IKJ56400 prompt ──
            if "IN USE" in upper or "LOGON REJECTED" in upper:
                send_terminal_key("clear")
                _time.sleep(1)
                send_terminal_key("string", f"LOGON {userid} RECONNECT")
                send_terminal_key("enter")
                _time.sleep(4)
                screen = self._read_screen_safe()
                self.current_screen = screen
                upper = screen.upper()
                if "PASSWORD" in upper or "IKJ56476" in upper or "ENTER CURRENT" in upper:
                    send_terminal_key("string", password)
                    send_terminal_key("enter")
                    _time.sleep(4)
                screen = self._press_through_screens()
                if self._is_logged_in(screen.upper()):
                    return
                continue

            # ── "REENTER" / "INVALID KEYWORD" / IKJ56703 / IKJ56429 ──
            # We might be stuck in an editor or bad command context.
            # Escape to a known state first, then check if already logged in.
            if "REENTER" in upper or "INVALID KEYWORD" in upper or "IKJ56703" in upper or "IKJ56429" in upper:
                logger.info(f"Login attempt {attempt}: error state detected, escaping")
                screen = self._escape_to_ready()
                upper = screen.upper()
                if self._is_logged_in(upper):
                    return
                # If we escaped to VTAM/logon, try fresh login
                if "LOGON" in upper and "===>" in screen:
                    continue  # will be caught by VTAM handler next iteration
                # If at IKJ56400 prompt
                if "IKJ56400" in upper:
                    continue  # will be caught by IKJ56400 handler
                # Still stuck — try LLM recovery
                logger.info("Escape didn't reach known state, trying LLM")
                dummy_step = {"title": "TSO Login Recovery"}
                self._llm_recover(screen, dummy_step, target)
                continue

            # ── "TSO COMMAND NOT ACCEPTED DURING LOGON" (IKJ56410) ──
            if "IKJ56410" in upper or "NOT ACCEPTED DURING LOGON" in upper:
                send_terminal_key("clear")
                _time.sleep(1)
                send_terminal_key("string", f"LOGON {userid}")
                send_terminal_key("enter")
                _time.sleep(3)
                continue

            # ── VTAM screen with "Logon ===>" prompt ──
            if "LOGON ===>" in screen or "Logon ===>" in screen:
                send_terminal_key("home")
                _time.sleep(0.3)
                send_terminal_key("eraseeof")
                _time.sleep(0.3)
                send_terminal_key("string", userid)
                send_terminal_key("enter")
                _time.sleep(4)
                screen = self._read_screen_safe()
                self.current_screen = screen
                upper = screen.upper()
                if "PASSWORD" in upper or "IKJ56476" in upper:
                    send_terminal_key("string", password)
                    send_terminal_key("enter")
                    _time.sleep(4)
                screen = self._press_through_screens()
                if self._is_logged_in(screen.upper()):
                    return
                continue

            # ── VTAM screen WITHOUT Logon prompt (first connection) ──
            # Per featherriver.net: first connection may lack Logon ===>
            if ("MVS" in upper or "TK5" in upper or "HERCULES" in upper) and "LOGON" not in upper:
                send_terminal_key("enter")
                _time.sleep(2)
                continue

            # ── "ENTER USERID" / IKJ56700 prompt ──
            if "ENTER USERID" in upper or "IKJ56700" in upper:
                send_terminal_key("clear")
                _time.sleep(1)
                send_terminal_key("string", f"LOGON {userid}")
                send_terminal_key("enter")
                _time.sleep(4)
                screen = self._read_screen_safe()
                self.current_screen = screen
                upper = screen.upper()
                # Fall through to password check below

            # ── Password prompt ──
            if "PASSWORD" in upper or "IKJ56476" in upper:
                send_terminal_key("string", password)
                send_terminal_key("enter")
                _time.sleep(4)
                screen = self._press_through_screens()
                upper = screen.upper()
                if self._is_logged_in(upper):
                    return
                continue

            # ── "ENTER CURRENT PASSWORD" ──
            if "ENTER CURRENT" in upper:
                send_terminal_key("string", password)
                send_terminal_key("enter")
                _time.sleep(3)
                screen = self._press_through_screens()
                if self._is_logged_in(screen.upper()):
                    return
                continue

            # ── "PRESS ENTER TO CONTINUE" / IKJ56455 / broadcast / fortune ──
            if "PRESS ENTER" in upper or "IKJ56455" in upper or "FORTUNE" in upper:
                screen = self._press_through_screens()
                if self._is_logged_in(screen.upper()):
                    return
                continue

            # ── Unknown screen — use AI to figure out what to do ──
            logger.info(f"Login attempt {attempt}: unknown screen state, using AI escape")
            screen = self._escape_to_ready()
            upper = screen.upper()
            if self._is_logged_in(upper):
                return
            _time.sleep(3)

        self.error = f"TSO login failed after {max_attempts} attempts"
        self.running = False


# Singleton runner
_walkthrough_runner = WalkthroughRunner()


@router.post("/start")
async def api_walkthrough_start(request: Request):
    """Start an autonomous walkthrough."""
    data = await request.json()
    name = data.get("name", "session-stack")
    target = data.get("target", "localhost:3270")
    speed = float(data.get("speed", 4.0))
    lhost = data.get("lhost", "10.0.0.1")
    lport = data.get("lport", "4444")

    script = WALKTHROUGH_SCRIPTS.get(name)
    if not script:
        return JSONResponse({"success": False, "error": f"Unknown walkthrough: {name}"})

    if not AGENT_TOOLS_AVAILABLE:
        try:
            import shutil
            if shutil.which("s3270") is None:
                return JSONResponse({"success": False, "error": "s3270 not installed. Run: sudo apt-get install x3270"})
        except Exception:
            pass
        return JSONResponse({"success": False, "error": "TN3270 agent tools not available (py3270 not installed)"})

    if _walkthrough_runner.running:
        _walkthrough_runner.stop()

    _walkthrough_runner.start(name, target, speed, lhost, lport)
    return JSONResponse({"success": True, "walkthrough": script["title"]})


@router.post("/stop")
async def api_walkthrough_stop():
    """Stop the running walkthrough."""
    _walkthrough_runner.stop()
    return JSONResponse({"success": True})


@router.post("/pause")
async def api_walkthrough_pause():
    """Toggle pause/resume on the walkthrough."""
    if _walkthrough_runner.paused:
        _walkthrough_runner.resume()
    else:
        _walkthrough_runner.pause()
    return JSONResponse({"success": True, "paused": _walkthrough_runner.paused})


@router.get("/status")
async def api_walkthrough_status():
    """Get current walkthrough status."""
    return JSONResponse(_walkthrough_runner.get_status())


@router.post("/reset")
async def api_walkthrough_reset():
    """Force reset walkthrough and disconnect from mainframe."""
    # Stop any running walkthrough
    _walkthrough_runner.stop()
    _walkthrough_runner.running = False
    _walkthrough_runner.paused = False
    _walkthrough_runner.finished = False
    _walkthrough_runner.error = None
    _walkthrough_runner.current_step = 0
    _walkthrough_runner.log = []
    
    # Force disconnect from mainframe
    disconnected = False
    if AGENT_TOOLS_AVAILABLE and connection:
        try:
            if connection.connected:
                from agent_tools import disconnect_mainframe
                disconnect_mainframe()
                disconnected = True
        except Exception as e:
            return JSONResponse({"success": True, "disconnected": False, "error": str(e)})
    
    return JSONResponse({"success": True, "disconnected": disconnected, "message": "Walkthrough reset complete"})
