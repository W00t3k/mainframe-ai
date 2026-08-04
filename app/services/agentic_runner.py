"""
Agentic Lab Runner

Uses BigIronV2 (or other LLM) to decide actions based on screen state and goals.
No scripted action sequences - the agent observes and decides.
"""

import time
import threading
import httpx
import logging
import re
from typing import Optional, List, Dict, Any

from app.config import get_config
from app.constants.agentic_labs import AGENTIC_LABS

logger = logging.getLogger(__name__)

# Import agent_tools
try:
    import sys
    import os
    tools_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'tools')
    if tools_dir not in sys.path:
        sys.path.insert(0, tools_dir)
    from agent_tools import connection, connect_mainframe, read_screen, send_terminal_key
    AGENT_TOOLS_AVAILABLE = True
except ImportError as e:
    AGENT_TOOLS_AVAILABLE = False
    connection = None
    connect_mainframe = None
    read_screen = lambda: "[Not connected]"
    send_terminal_key = lambda *args: {"success": False}
    logger.warning(f"agent_tools import failed: {e}")


class AgenticLabRunner:
    """Goal-based lab runner using LLM to decide actions."""

    # Default credentials
    USERID = "HERC01"
    PASSWORD = "CUL8TR"

    # Valid actions the agent can take
    VALID_ACTIONS = [
        "ENTER", "CLEAR", "PF1", "PF2", "PF3", "PF4", "PF5", "PF6",
        "PF7", "PF8", "PF9", "PF10", "PF11", "PF12", "TAB", "HOME",
        "TYPE <text>", "CONNECT", "LOGOFF", "WAIT"
    ]

    def __init__(self):
        self.running = False
        self.paused = False
        self.current_step = 0
        self.total_steps = 0
        self.current_goal = ""
        self.current_narration = ""
        self.current_screen = ""
        self.current_control_plane = ""
        self.lab_name = ""
        self.log: List[Dict] = []
        self.finished = False
        self.error: Optional[str] = None
        self.action_count = 0
        self._thread: Optional[threading.Thread] = None
        self._logged_in = False

    def _robust_login(self, target: str, max_retries: int = 3) -> bool:
        """Robust login with retry logic - handles all edge cases."""
        if not AGENT_TOOLS_AVAILABLE:
            self._add_log("Agent tools not available", "error")
            return False

        for attempt in range(max_retries):
            self._add_log(f"Login attempt {attempt + 1}/{max_retries}", "info")

            # Connect
            try:
                connect_mainframe(target)
                time.sleep(3)
            except Exception as e:
                self._add_log(f"Connection failed: {e}", "error")
                time.sleep(5)
                continue

            screen = self._read_screen()
            self.current_screen = screen
            upper = screen.upper() if screen else ""

            # Clear any previous state
            send_terminal_key("clear")
            time.sleep(1)
            screen = self._read_screen()
            upper = screen.upper() if screen else ""

            # Type logon command
            if "LOGON ===>" in upper or "LOGON==>" in upper:
                self._add_log(f"At logon prompt, typing {self.USERID}", "action")
                send_terminal_key("string", self.USERID)
                time.sleep(0.5)
                send_terminal_key("enter")
                time.sleep(2)
                screen = self._read_screen()
                upper = screen.upper() if screen else ""
            elif "ENTER LOGON OR LOGOFF" in upper or "IKJ56400A" in upper:
                self._add_log(f"At VTAM prompt, typing LOGON {self.USERID}", "action")
                send_terminal_key("string", f"LOGON {self.USERID}")
                time.sleep(0.5)
                send_terminal_key("enter")
                time.sleep(2)
                screen = self._read_screen()
                upper = screen.upper() if screen else ""

            # Check for IN USE
            if "IN USE" in upper:
                self._add_log(f"Userid {self.USERID} in use, waiting 15 seconds...", "warning")
                send_terminal_key("clear")
                time.sleep(15)
                continue

            # Type password
            if "PASSWORD" in upper:
                self._add_log("Typing password", "action")
                send_terminal_key("string", self.PASSWORD)
                time.sleep(0.5)
                send_terminal_key("enter")
                time.sleep(3)
                screen = self._read_screen()
                upper = screen.upper() if screen else ""

            # Check for password error
            if "PASSWORD NOT AUTHORIZED" in upper or "REENTER" in upper:
                self._add_log("Password rejected, clearing and retrying", "warning")
                send_terminal_key("clear")
                time.sleep(2)
                continue

            # Skip broadcast messages
            for _ in range(5):
                screen = self._read_screen()
                if "***" in (screen or ""):
                    send_terminal_key("enter")
                    time.sleep(1)
                else:
                    break

            # Check if we're at ISPF/TSO menu
            screen = self._read_screen()
            upper = (screen or "").upper()
            if "TSOAPPLS" in upper or "OPTION ===>" in upper or ("BROWSE" in upper and "EDIT" in upper):
                self._add_log("Login successful!", "success")
                self._logged_in = True
                # Exit to TSO READY for better control
                self._add_log("Exiting to TSO READY prompt", "action")
                for _ in range(3):
                    send_terminal_key("pf", "3")
                    time.sleep(0.5)
                    screen = self._read_screen()
                    if "READY" in (screen or "").upper():
                        break
                return True

            self._add_log(f"Login attempt {attempt + 1} failed", "warning")

        self._add_log("Login failed after all retries", "error")
        return False

    def _robust_logoff(self) -> bool:
        """Robust logoff - exits all menus and logs off cleanly."""
        if not AGENT_TOOLS_AVAILABLE or not self._logged_in:
            return True

        self._add_log("Logging off...", "info")

        # Exit any nested menus
        for _ in range(5):
            send_terminal_key("pf", "3")
            time.sleep(0.5)
            screen = self._read_screen()
            if "READY" in (screen or "").upper():
                break

        # Type LOGOFF
        send_terminal_key("string", "LOGOFF")
        time.sleep(0.5)
        send_terminal_key("enter")
        time.sleep(2)

        self._logged_in = False
        self._add_log("Logged off", "success")
        return True

    def start(self, lab_name: str, target: str = "localhost:3270"):
        """Start an agentic lab."""
        if lab_name not in AGENTIC_LABS:
            self.error = f"Unknown lab: {lab_name}"
            return

        if self.running:
            return

        self.running = True
        self.paused = False
        self.finished = False
        self.error = None
        self.current_step = 0
        self.lab_name = lab_name
        self.log = []
        self.action_count = 0

        lab = AGENTIC_LABS[lab_name]
        self.total_steps = len(lab["steps"])

        self._thread = threading.Thread(
            target=self._run, args=(lab_name, target), daemon=True
        )
        self._thread.start()

    def stop(self):
        self.running = False

    def pause(self):
        self.paused = True

    def resume(self):
        self.paused = False

    def get_status(self) -> Dict:
        """Get current status for the UI."""
        return {
            "running": self.running,
            "paused": self.paused,
            "finished": self.finished,
            "error": self.error,
            "step": self.current_step,
            "total": self.total_steps,
            "goal": self.current_goal,
            "narration": self.current_narration,
            "screen": self.current_screen,
            "control_plane": self.current_control_plane,
            "action_count": self.action_count,
            "log": self.log,
        }

    def _run(self, lab_name: str, target: str):
        """Main execution loop."""
        lab = AGENTIC_LABS[lab_name]

        try:
            for i, step in enumerate(lab["steps"]):
                if not self.running:
                    break

                self.current_step = i
                self.current_goal = step["goal"]
                self.current_narration = step.get("narration", "")
                self.current_control_plane = step.get("control_plane", "")
                max_actions = step.get("max_actions", 20)

                self._add_log(f"Step {i+1}: {step['goal']}", "goal")

                # Check if this is a login step - use robust login
                goal_upper = step["goal"].upper()
                if "LOGIN" in goal_upper or "CONNECT" in goal_upper and "TSO" in goal_upper:
                    if not self._logged_in:
                        if not self._robust_login(target):
                            self.error = "Failed to login to mainframe"
                            self._add_log("Login failed", "error")
                            break
                        # Login succeeded - mark step complete
                        self._add_log(f"Completed: {step['goal']}", "success")
                        if step.get("narration"):
                            self._add_log(step["narration"], "narration")
                            time.sleep(3)
                        continue  # Skip to next step

                # Execute step using agent
                success = self._execute_goal(
                    goal=step["goal"],
                    context=step.get("context", ""),
                    success_criteria=step.get("success_criteria", []),
                    max_actions=max_actions,
                    target=target,
                )

                if not success:
                    self.error = f"Failed to achieve goal: {step['goal']}"
                    self._add_log(f"FAILED: {step['goal']}", "error")
                    break

                self._add_log(f"Completed: {step['goal']}", "success")

                # Show narration
                if step.get("narration"):
                    self._add_log(step["narration"], "narration")
                    time.sleep(3)  # Let user read

        finally:
            # Always logoff cleanly
            self._robust_logoff()

        self.finished = True
        self.running = False

    def _execute_goal(self, goal: str, context: str, success_criteria: List[str],
                      max_actions: int, target: str) -> bool:
        """Execute a single goal using the LLM agent."""
        actions_taken = 0

        while actions_taken < max_actions and self.running:
            # Wait if paused
            while self.paused and self.running:
                time.sleep(0.5)

            # Read current screen
            screen = self._read_screen()
            self.current_screen = screen

            # Check if goal is achieved
            if self._check_success(screen, success_criteria):
                return True

            # Ask LLM what action to take
            action = self._decide_action(screen, goal, context, actions_taken)

            if not action:
                # No action needed - check if we're done
                if self._check_success(screen, success_criteria):
                    return True
                self._add_log("Agent pausing - checking screen state", "info")
                time.sleep(2)
                continue

            # Execute the action
            self._add_log(f"Action: {action}", "action")
            self._execute_action(action, target)
            actions_taken += 1
            self.action_count += 1

            time.sleep(1)  # Wait for screen to update

        return self._check_success(self._read_screen(), success_criteria)

    def _read_screen(self) -> str:
        """Read current terminal screen."""
        if not AGENT_TOOLS_AVAILABLE:
            return "[Agent tools not available]"
        try:
            return read_screen() or "[Empty screen]"
        except Exception as e:
            return f"[Error reading screen: {e}]"

    def _check_success(self, screen: str, criteria: List[str]) -> bool:
        """Check if success criteria are met."""
        if not criteria:
            return True
        upper_screen = screen.upper()
        # Require ALL criteria to match
        for c in criteria:
            if c.upper() not in upper_screen:
                return False
        return True

    def _decide_action(self, screen: str, goal: str, context: str, actions_taken: int) -> Optional[str]:
        """Decide what action to take - pattern matching first, then LLM."""
        # Try pattern matching FIRST - more reliable than LLM
        pattern_action = self._pattern_decide(screen, goal)
        if pattern_action == "DONE":
            # Pattern indicates we've achieved the goal - return None to trigger success check
            logger.info("Pattern indicates goal achieved")
            return None
        if pattern_action:
            logger.info(f"Pattern decided: {pattern_action}")
            return pattern_action

        # No pattern match - ask LLM
        config = get_config()
        screen_lines = screen.split("\n")[:24]
        screen_truncated = "\n".join(screen_lines)

        prompt = f"""You are an MVS 3.8j mainframe terminal agent. Observe the screen and decide ONE action.

SCREEN:
{screen_truncated}

GOAL: {goal}

CONTEXT: {context}

ACTIONS SO FAR: {actions_taken}

RULES:
- "ENTER LOGON OR LOGOFF" = VTAM prompt. Type: TYPE LOGON HERC01
- "Logon ===>" = TSO panel. Type: TYPE HERC01
- "USERID IN USE" = Clear and wait
- "ENTER CURRENT PASSWORD" = Type: TYPE CUL8TR
- "OPTION ===>" with "BROWSE/EDIT" = ISPF menu. Type 1 for Browse.
- "DATA SET NAME" = enter dataset path
- "TSOAPPLS" = TSO menu. Type 1 for RFE.
- "READY" = TSO command prompt.
- PF3 goes back/exits

DO NOT type HERC01 if at ISPF!
If screen shows BROWSE, EDIT, UTILITIES - you ARE logged in.

VALID: TYPE <text>, ENTER, CLEAR, PF3, PF7, PF8, TAB, CONNECT, LOGOFF, WAIT

Reply with EXACTLY ONE action:"""

        try:
            resp = httpx.post(
                f"{config.OLLAMA_URL}/api/generate",
                json={
                    "model": config.OLLAMA_MODEL,
                    "prompt": prompt,
                    "stream": False,
                    "options": {"temperature": 0.1, "num_predict": 30},
                },
                timeout=30.0,
            )
            if resp.status_code == 200:
                response = resp.json().get("response", "").strip()
                action = self._parse_action(response)
                logger.info(f"LLM decided: {action} (raw: {response[:100]})")
                return action
        except Exception as e:
            logger.error(f"LLM error: {e}")

        return None

    def _parse_action(self, response: str) -> Optional[str]:
        """Parse LLM response into a valid action."""
        response = response.strip().upper()
        lines = response.split("\n")
        first_line = lines[0].strip()

        # Direct action keywords
        for action in ["ENTER", "CLEAR", "TAB", "HOME", "CONNECT", "LOGOFF", "WAIT"]:
            if action in first_line:
                return action

        # PF keys
        pf_match = re.search(r'PF(\d+)', first_line)
        if pf_match:
            return f"PF{pf_match.group(1)}"

        # TYPE command
        type_match = re.search(r'TYPE\s+(.+)', first_line, re.IGNORECASE)
        if type_match:
            text = type_match.group(1).strip().strip('"\'')
            return f"TYPE {text}"

        # If response looks like text to type
        if first_line and not any(c in first_line for c in ['?', '!', '.']):
            if len(first_line) < 50:
                return f"TYPE {first_line}"

        return None

    def _pattern_decide(self, screen: str, goal: str) -> Optional[str]:
        """Fallback pattern-based decision."""
        upper = screen.upper()
        goal_upper = goal.upper()

        # Not connected
        if "[NOT CONNECTED]" in upper or "[EMPTY" in upper:
            return "CONNECT"

        # Userid locked - need to wait for session to time out
        if "USERID" in upper and "IN USE" in upper:
            logger.warning("Userid in use - waiting 10 seconds before retry")
            time.sleep(10)
            return "CLEAR"

        # Password error - need to clear and retry
        if "PASSWORD NOT AUTHORIZED" in upper or "REENTER" in upper:
            return "CLEAR"

        # VTAM command prompt (IKJ56400A) - need full LOGON command
        if "ENTER LOGON OR LOGOFF" in upper or "IKJ56400A" in upper:
            return "TYPE LOGON HERC01"

        # VTAM logon panel with "Logon ===>" - but only if goal is to login
        if "LOGON ===>" in upper or "LOGON==>" in upper:
            if "LOGIN" in goal_upper or "CONNECT" in goal_upper:
                return "TYPE HERC01"
            # If goal is to logoff and we're at logon screen, we're done!
            if "LOGOFF" in goal_upper or "EXIT" in goal_upper:
                return "DONE"  # Success - we logged off

        # Invalid command syntax - clear and start fresh
        if "INVALID COMMAND SYNTAX" in upper or "IKJ56401I" in upper:
            return "CLEAR"

        # Password prompt - look for various patterns
        # But NOT if we're at the Browse entry panel (has "DATA SET PASSWORD")
        if "ENTER CURRENT PASSWORD" in upper:
            return "TYPE CUL8TR"
        if "PASSWORD ===>" in upper and "DATA SET PASSWORD" not in upper and "ENTRY PANEL" not in upper:
            return "TYPE CUL8TR"

        # TSO messages with *** - press enter to continue
        if "IKJ5" in upper and "***" in upper:
            return "ENTER"

        # TSOAPPLS menu - exit to TSO READY for direct commands
        if "TSOAPPLS" in upper or "TSO APPLICATIONS" in upper:
            if "BROWSE" in goal_upper or "VIEW" in goal_upper or "STATUS" in goal_upper:
                return "PF3"  # Exit to TSO READY
            return "TYPE 1"  # Enter RFE for other tasks

        # At READY prompt and need to do something
        if "READY" in upper:
            # Enter RFE if goal mentions it
            if "RFE" in goal_upper or "ISPF" in goal_upper:
                return "TYPE RFE"
            # For browsing files, use REVIEW command directly
            if "BROWSE" in goal_upper or "VIEW" in goal_upper:
                if "SYS1.SECURE.CNTL(USERS)" in goal_upper:
                    return "TYPE REVIEW 'SYS1.SECURE.CNTL(USERS)'"
                if "SYS1.SECURE.CNTL(PROFILES)" in goal_upper:
                    return "TYPE REVIEW 'SYS1.SECURE.CNTL(PROFILES)'"
                ds_match = re.search(r"([A-Z0-9.]+\([A-Z0-9]+\))", goal_upper)
                if ds_match:
                    return f"TYPE REVIEW '{ds_match.group(1)}'"
                return "TYPE RFE"
            if "STATUS" in goal_upper:
                return "TYPE STATUS"
            if "OUTPUT" in goal_upper:
                return "TYPE OUTPUT *"
            if "LOGOFF" in goal_upper or "EXIT" in goal_upper:
                return "LOGOFF"

        # At RFE/ISPF primary menu - exit to TSO READY for better control
        if "OPTION ===>" in upper and ("BROWSE" in upper or "EDIT" in upper):
            if "BROWSE" in goal_upper or "VIEW" in goal_upper:
                # Exit to TSO READY and use REVIEW command directly
                return "PF3"
            if "LOGIN" in goal_upper:
                return None  # Already logged in!
            return "PF3"  # Exit to TSO for most goals

        # RFE Browse/Review entry panel - always exit with PF3
        # Whether navigating, exiting, or logging off, PF3 is the right choice
        if ("REVIEW" in upper and "ENTRY PANEL" in upper) or \
           ("BROWSE" in upper and "ENTRY PANEL" in upper) or \
           ("DATA SET NAME" in upper and "OTHER PARTITIONED" in upper):
            return "PF3"

        # Dataset not found error - need to correct path or exit
        if "NOT IN CATALOG" in upper or "NOT FOUND" in upper:
            return "PF3"  # Go back and try again

        # Viewing a file in REVIEW - check if we're done and need to exit
        if ("LINE" in upper and "COL" in upper) or ("COMMAND ===>" in upper and "SCROLL" in upper):
            if "EXIT" in goal_upper or "GO BACK" in goal_upper:
                return "PF3"
            # If viewing a different file than what goal asks for, exit
            if "SYS1.SECURE.CNTL(PROFILES)" in goal_upper and "USERS" in upper:
                return "PF3"
            if "SYS1.SECURE.CNTL(USERS)" in goal_upper and "PROFILES" in upper:
                return "PF3"
            return None  # Stay and view - check success criteria

        # Viewing a file - check if we need to exit
        if "BROWSE" in upper and ("LINE" in upper or "COL" in upper):
            if "GO BACK" in goal_upper or "EXIT" in goal_upper:
                return "PF3"
            return None  # Viewing file, might be success

        # Generic error recovery
        if "ERROR" in upper or "INVALID" in upper:
            return "CLEAR"

        # Don't blindly press Enter - might cause issues
        return None

    def _execute_action(self, action: str, target: str):
        """Execute a single action."""
        if not AGENT_TOOLS_AVAILABLE:
            return

        try:
            if action == "CONNECT":
                connect_mainframe(target)
                time.sleep(2)

            elif action == "ENTER":
                send_terminal_key("enter")

            elif action == "CLEAR":
                send_terminal_key("clear")

            elif action == "TAB":
                send_terminal_key("tab")

            elif action == "HOME":
                send_terminal_key("home")

            elif action == "LOGOFF":
                # Exit any nested panels first
                for _ in range(5):
                    send_terminal_key("pf", "3")
                    time.sleep(0.5)
                # Type LOGOFF command
                send_terminal_key("string", "LOGOFF")
                time.sleep(0.5)
                send_terminal_key("enter")
                time.sleep(3)

            elif action == "WAIT":
                time.sleep(2)

            elif action.startswith("PF"):
                num = action[2:]
                send_terminal_key("pf", num)

            elif action.startswith("TYPE "):
                text = action[5:]
                send_terminal_key("string", text)
                time.sleep(0.5)
                send_terminal_key("enter")
                time.sleep(1)  # Wait for response

        except Exception as e:
            logger.error(f"Action execution error: {e}")

    def _add_log(self, message: str, log_type: str = "info"):
        """Add entry to the log."""
        self.log.append({
            "time": time.strftime("%H:%M:%S"),
            "type": log_type,
            "message": message,
        })


# Global instance
_agentic_runner = AgenticLabRunner()


def get_agentic_runner() -> AgenticLabRunner:
    return _agentic_runner
