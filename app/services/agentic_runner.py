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

        for i, step in enumerate(lab["steps"]):
            if not self.running:
                break

            self.current_step = i
            self.current_goal = step["goal"]
            self.current_narration = step.get("narration", "")
            self.current_control_plane = step.get("control_plane", "")
            max_actions = step.get("max_actions", 20)

            self._add_log(f"Step {i+1}: {step['goal']}", "goal")

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
        matches = sum(1 for c in criteria if c.upper() in upper_screen)
        # Require at least half the criteria to match
        return matches >= len(criteria) / 2

    def _decide_action(self, screen: str, goal: str, context: str, actions_taken: int) -> Optional[str]:
        """Use LLM to decide what action to take."""
        config = get_config()

        # Truncate screen to first 24 lines (typical 3270 screen)
        screen_lines = screen.split("\n")[:24]
        screen_truncated = "\n".join(screen_lines)

        prompt = f"""You are an MVS 3.8j mainframe terminal agent. You observe the screen and decide ONE action to take.

CURRENT SCREEN:
{screen_truncated}

GOAL: {goal}

CONTEXT: {context}

ACTIONS TAKEN SO FAR: {actions_taken}

VALID ACTIONS:
- TYPE <text> - Type text (e.g., TYPE HERC01, TYPE 1, TYPE SYS1.SECURE.CNTL)
- ENTER - Press Enter key
- CLEAR - Clear screen
- PF3 - Go back / Exit
- PF7 - Scroll up
- PF8 - Scroll down
- TAB - Move to next field
- HOME - Move to home position
- CONNECT - Connect to mainframe (if not connected)
- LOGOFF - Type LOGOFF and press Enter
- WAIT - Wait for screen to update

RULES:
1. Look at the screen carefully. What does it show?
2. Decide ONE action that moves toward the goal.
3. If you see "Logon ===>" type the userid: TYPE HERC01
4. If you see "Password" prompt or "ENTER CURRENT PASSWORD", type: TYPE CUL8TR
5. If you see "REENTER" or "PASSWORD NOT AUTHORIZED", send: CLEAR
6. If you see "READY" you're at TSO prompt.
7. To browse a file: RFE option 1, then enter dataset name.
8. PF3 goes back/exits panels.
9. LOGOFF only when the goal is to logoff.
10. The password for HERC01 is CUL8TR - always use this.

Respond with EXACTLY ONE action. Examples:
TYPE HERC01
ENTER
PF3
TYPE 1
CONNECT

YOUR ACTION:"""

        try:
            resp = httpx.post(
                f"{config.OLLAMA_URL}/api/generate",
                json={
                    "model": config.OLLAMA_MODEL,
                    "prompt": prompt,
                    "stream": False,
                    "options": {"temperature": 0.3, "num_predict": 50},
                },
                timeout=30.0,
            )
            if resp.status_code == 200:
                response = resp.json().get("response", "").strip()
                # Extract action from response
                action = self._parse_action(response)
                logger.info(f"LLM decided: {action} (raw: {response[:100]})")
                return action
        except Exception as e:
            logger.error(f"LLM error: {e}")

        # Fallback: try pattern-based decision
        return self._pattern_decide(screen, goal)

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

        # Password error - need to clear and retry
        if "PASSWORD NOT AUTHORIZED" in upper or "REENTER" in upper:
            return "CLEAR"

        # VTAM logon screen
        if "LOGON ===>" in upper or "LOGON==>" in upper:
            return "TYPE HERC01"

        # Password prompt - look for various patterns
        if "ENTER CURRENT PASSWORD" in upper or "PASSWORD ===>" in upper or ("PASSWORD" in upper and "===>" in upper):
            return "TYPE CUL8TR"

        # Password field without explicit prompt (TSO login)
        if "PASSWORD ==>" in upper or "PASSWORD==" in upper:
            return "TYPE CUL8TR"

        # TSO messages - press enter
        if "IKJ5" in upper or "BROADCAST" in upper:
            return "ENTER"

        # TSOAPPLS menu - select RFE
        if "TSOAPPLS" in upper or "TSO APPLICATIONS" in upper:
            return "TYPE 1"

        # At READY and goal mentions browse/view
        if "READY" in upper:
            if "BROWSE" in goal_upper or "VIEW" in goal_upper:
                return "TYPE RFE"
            if "STATUS" in goal_upper:
                return "TYPE STATUS"
            if "OUTPUT" in goal_upper:
                return "TYPE OUTPUT *"
            if "LOGOFF" in goal_upper:
                return "LOGOFF"

        # Already at ISPF/RFE - don't type random stuff
        if "ISPF" in upper and "OPTION" in upper and "BROWSE" in upper:
            if "BROWSE" in goal_upper or "VIEW" in goal_upper:
                return "TYPE 1"
            # Default: we're logged in, goal might be complete
            return None

        # RFE primary menu
        if "RFE" in upper and "BROWSE" in upper and "EDIT" in upper:
            if "BROWSE" in goal_upper:
                return "TYPE 1"
            return None

        # Generic: try PF3 to go back
        if "ERROR" in upper or "INVALID" in upper:
            return "CLEAR"

        return "ENTER"

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
                send_terminal_key("string", "LOGOFF")
                time.sleep(0.5)
                send_terminal_key("enter")

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
