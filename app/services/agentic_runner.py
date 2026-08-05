"""
Agentic Lab Runner

Uses BigIronV2 (or other LLM) to decide actions based on screen state and goals.
No scripted action sequences - the agent observes and decides.
"""

import os
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
    from agent_tools import connection, connect_mainframe, read_screen, send_terminal_key, disconnect_mainframe
    AGENT_TOOLS_AVAILABLE = True
except ImportError as e:
    AGENT_TOOLS_AVAILABLE = False
    connection = None
    connect_mainframe = None
    read_screen = lambda: "[Not connected]"
    send_terminal_key = lambda *args: {"success": False}
    disconnect_mainframe = lambda: None
    logger.warning(f"agent_tools import failed: {e}")


class AgenticLabRunner:
    """Goal-based lab runner using LLM to decide actions."""

    # Rotating credentials - both have same password on TK5
    USERIDS = ["HERC01", "HERC02"]
    PASSWORD = "CUL8TR"
    _last_userid_index = 0  # Class-level to persist across instances

    # Pacing: pause after each action so a human watching the browser can
    # follow what the agent is doing. Override with env AGENTIC_PACING (seconds).
    PACING_DELAY = float(os.environ.get("AGENTIC_PACING", "2.0"))
    # Extra dwell on screens that show real command output (LISTDS/LISTCAT/
    # REVIEW/STATUS results) so the viewer has time to read the data.
    DATA_DWELL = float(os.environ.get("AGENTIC_DATA_DWELL", "3.5"))

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
        self._current_userid = None
        self._logged_in = False
        self._blank_screens = 0
        self.explain_mode = False
        self._last_paused_screen = None

    def _robust_connect(self, target: str, max_wait: int = 30) -> bool:
        """Connect and wait for VTAM logon screen (don't login)."""
        if not AGENT_TOOLS_AVAILABLE:
            self._add_log("Agent tools not available", "error")
            return False

        try:
            success, msg = connect_mainframe(target)
            if not success:
                self._add_log(f"Connection failed: {msg}", "error")
                return False
            self._add_log(f"Connected to {target}", "info")
        except Exception as e:
            self._add_log(f"Connection error: {e}", "error")
            return False

        # Wait for VTAM logon screen
        for _ in range(max_wait):
            screen = self._read_screen() or ""
            upper = screen.upper()
            # Check for VTAM logon indicators
            if "LOGON" in upper and "===>" in upper:
                self._add_log("VTAM logon screen ready", "success")
                return True
            if "ENTER USERID" in upper or "IKJ56700A" in upper:
                self._add_log("VTAM logon screen ready", "success")
                return True
            # Still at Hercules banner - send Enter to prod VTAM
            if "HERCULES" in upper or len(upper.strip()) == 0:
                send_terminal_key("enter")
            time.sleep(1)

        self._add_log("Timeout waiting for VTAM logon screen", "warning")
        return False

    def _get_next_userid(self) -> str:
        """Rotate to next userid to avoid session locking."""
        AgenticLabRunner._last_userid_index = (AgenticLabRunner._last_userid_index + 1) % len(self.USERIDS)
        return self.USERIDS[AgenticLabRunner._last_userid_index]

    def _restart_tk5(self, target: str) -> bool:
        """Restart TK5 as last resort when both userids are locked."""
        import subprocess
        self._add_log("Both userids locked - restarting TK5...", "warning")

        try:
            # Kill hercules and s3270
            subprocess.run(["pkill", "-9", "hercules"], capture_output=True, timeout=5)
            subprocess.run(["pkill", "-9", "s3270"], capture_output=True, timeout=5)
            time.sleep(3)

            # Find TK5 directory
            import os
            tk5_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "tk5", "mvs-tk5")
            if not os.path.exists(tk5_dir):
                self._add_log(f"TK5 directory not found: {tk5_dir}", "error")
                return False

            # Start TK5
            subprocess.Popen(
                f"cd {tk5_dir} && nohup bash -c 'tail -f /dev/null | hercules -f conf/tk5.cnf -r scripts/ipl.rc -d' > /dev/null 2>&1 &",
                shell=True
            )

            # Wait for TK5 to start
            self._add_log("Waiting for TK5 to start (60s)...", "info")
            time.sleep(60)

            # Verify port is open
            import socket
            host = target.split(":")[0] if ":" in target else target
            port = int(target.split(":")[1]) if ":" in target else 3270
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            result = sock.connect_ex((host, port))
            sock.close()

            if result == 0:
                self._add_log("TK5 restarted successfully", "success")
                return True
            else:
                self._add_log("TK5 restart failed - port not accessible", "error")
                return False

        except Exception as e:
            self._add_log(f"TK5 restart error: {e}", "error")
            return False

    def _try_login_with_userid(self, target: str, userid: str) -> bool:
        """Try to login with a specific userid. Returns True on success."""
        self._current_userid = userid

        # Connect
        try:
            success, msg = connect_mainframe(target)
            if not success:
                self._add_log(f"Connection failed: {msg}", "error")
                return False
            self._add_log(f"Connected to {target}", "info")
            time.sleep(1)
        except Exception as e:
            self._add_log(f"Connection error: {e}", "error")
            return False

        screen = self._read_screen()
        self.current_screen = screen
        upper = screen.upper() if screen else ""

        # Clear any previous state
        send_terminal_key("clear")
        time.sleep(0.3)
        screen = self._read_screen()
        upper = screen.upper() if screen else ""

        # Type logon command
        if "LOGON ===>" in upper or "LOGON==>" in upper:
            self._add_log(f"At logon prompt, typing {userid}", "action")
            send_terminal_key("string", userid)
            time.sleep(0.2)
            send_terminal_key("enter")
            time.sleep(1)
            screen = self._read_screen()
            upper = screen.upper() if screen else ""
        elif "ENTER LOGON OR LOGOFF" in upper or "IKJ56400A" in upper:
            self._add_log(f"At VTAM prompt, typing LOGON {userid}", "action")
            send_terminal_key("string", f"LOGON {userid}")
            time.sleep(0.2)
            send_terminal_key("enter")
            time.sleep(1)
            screen = self._read_screen()
            upper = screen.upper() if screen else ""

        # Check for IN USE
        if "IN USE" in upper:
            self._add_log(f"Userid {userid} in use", "warning")
            send_terminal_key("clear")
            time.sleep(1)
            disconnect_mainframe()
            return False

        # Type password
        if "PASSWORD" in upper:
            self._add_log("Typing password", "action")
            send_terminal_key("string", self.PASSWORD)
            time.sleep(0.2)
            send_terminal_key("enter")
            time.sleep(1)
            screen = self._read_screen()
            upper = screen.upper() if screen else ""

        # Check for password error
        if "PASSWORD NOT AUTHORIZED" in upper or "REENTER" in upper:
            self._add_log("Password rejected", "warning")
            send_terminal_key("clear")
            disconnect_mainframe()
            return False

        # Skip broadcast messages
        for _ in range(5):
            screen = self._read_screen()
            if "***" in (screen or ""):
                send_terminal_key("enter")
                time.sleep(0.3)
            else:
                break

        # Check if we're at ISPF/TSO menu or READY
        screen = self._read_screen()
        upper = (screen or "").upper()
        if "TSOAPPLS" in upper or "OPTION ===>" in upper or ("BROWSE" in upper and "EDIT" in upper) or "READY" in upper:
            self._add_log(f"Login successful as {userid}!", "success")
            self._logged_in = True
            # Exit to TSO READY for consistent state
            for _ in range(5):
                if "READY" in (self._read_screen() or "").upper():
                    break
                send_terminal_key("pf", "3")
                time.sleep(0.5)
            return True

        return False

    def _robust_login(self, target: str, max_retries: int = 2) -> bool:
        """Robust login with userid rotation and TK5 restart fallback."""
        if not AGENT_TOOLS_AVAILABLE:
            self._add_log("Agent tools not available", "error")
            return False

        # Try each userid
        for userid in self.USERIDS:
            self._add_log(f"Trying userid: {userid}", "info")
            if self._try_login_with_userid(target, userid):
                return True
            time.sleep(2)

        # Both userids failed - wait and retry
        self._add_log("All userids locked, waiting 30s...", "warning")
        time.sleep(30)

        for userid in self.USERIDS:
            self._add_log(f"Retry userid: {userid}", "info")
            if self._try_login_with_userid(target, userid):
                return True
            time.sleep(2)

        # Still failing - restart TK5 as last resort
        if self._restart_tk5(target):
            # Try login again after restart
            userid = self._get_next_userid()
            self._add_log(f"Post-restart login: {userid}", "info")
            if self._try_login_with_userid(target, userid):
                return True

        self._add_log("Login failed after all retries", "error")
        return False

    def _robust_logoff(self) -> bool:
        """Robust logoff - exits all menus and logs off cleanly."""
        if not AGENT_TOOLS_AVAILABLE:
            return True

        self._add_log("Logging off...", "info")

        try:
            # Clear any pending input
            send_terminal_key("reset")
            time.sleep(0.2)
            send_terminal_key("clear")
            time.sleep(0.3)

            # Exit any nested menus - keep pressing PF3 until READY
            for _ in range(8):
                screen = self._read_screen() or ""
                upper = screen.upper()
                if "READY" in upper:
                    break
                if "LOGON" in upper or "ENTER USERID" in upper:
                    # Already at VTAM - done
                    self._logged_in = False
                    self._add_log("Already logged off", "success")
                    return True
                send_terminal_key("pf", "3")
                time.sleep(0.5)

            # Now at READY - clear and type LOGOFF
            send_terminal_key("clear")
            time.sleep(0.3)
            send_terminal_key("home")
            time.sleep(0.1)
            send_terminal_key("eraseeof")
            time.sleep(0.1)
            send_terminal_key("string", "LOGOFF")
            time.sleep(0.2)
            send_terminal_key("enter")
            time.sleep(2)

            # Wait for VTAM screen (up to 5 seconds)
            for _ in range(10):
                screen = self._read_screen() or ""
                upper = screen.upper()
                if "LOGON" in upper or "ENTER USERID" in upper or "IKJ56700A" in upper:
                    self._logged_in = False
                    self._add_log("Logged off", "success")
                    return True
                # Only press ENTER to advance a pending "***" message. Pressing
                # ENTER at the bare VTAM logon prompt makes TCAS say
                # "INPUT NOT RECOGNIZED", so never press it blindly.
                if "***" in upper:
                    send_terminal_key("enter")
                time.sleep(0.5)

            # Even if we didn't see VTAM, mark as logged off
            self._logged_in = False
            self._add_log("Logged off (timeout)", "success")

        except Exception as e:
            logger.error(f"Logoff error: {e}")
            self._logged_in = False

        # Always disconnect the TN3270 connection to free the session
        try:
            disconnect_mainframe()
            time.sleep(5)  # Wait for TK5 to release the session
        except:
            pass

        # Reset current userid for next run
        self._current_userid = None
        return True

    def start(self, lab_name: str, target: str = "localhost:3270",
              explain_mode: bool = False):
        """Start an agentic lab.

        explain_mode: when True, the lab auto-pauses on each data/output screen
        so the viewer can read it and ask the AI to explain, then Resume.
        """
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
        self._blank_screens = 0
        self.explain_mode = explain_mode
        self._last_paused_screen = None  # avoid re-pausing on the same screen

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
            "explain_mode": self.explain_mode,
            "log": self.log,
        }

    def set_explain_mode(self, enabled: bool):
        """Toggle auto-pause-on-data-screens mid-run."""
        self.explain_mode = enabled

    def _run(self, lab_name: str, target: str):
        """Main execution loop."""
        lab = AGENTIC_LABS[lab_name]

        # Verify TK5 is running first
        if not AGENT_TOOLS_AVAILABLE:
            self.error = "Agent tools not available - install py3270 and s3270"
            self._add_log(self.error, "error")
            self.finished = True
            self.running = False
            return

        # Check if TK5 port is accessible
        import socket
        try:
            host, port = target.split(":") if ":" in target else (target, "3270")
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2)
            result = sock.connect_ex((host, int(port)))
            sock.close()
            if result != 0:
                self.error = f"TK5 not running - port {port} not accessible. Run ./start.sh first"
                self._add_log(self.error, "error")
                self.finished = True
                self.running = False
                return
        except Exception as e:
            self.error = f"Cannot reach TK5: {e}"
            self._add_log(self.error, "error")
            self.finished = True
            self.running = False
            return

        self._add_log(f"Starting lab: {lab_name}", "info")

        try:
            for i, step in enumerate(lab["steps"]):
                if not self.running:
                    break

                # Step-through gate: in step mode, pause before starting each
                # step after the first. The viewer can explore / ask the AI,
                # then Resume runs the next step and pauses again.
                if self.explain_mode and i > 0:
                    self.paused = True
                    self._add_log(
                        f"⏸ Paused — explore or ask the AI, then press Resume "
                        f"for step {i+1}.", "narration")
                    while self.paused and self.running:
                        time.sleep(0.3)
                    if not self.running:
                        break

                self.current_step = i
                self.current_goal = step["goal"]
                self.current_narration = step.get("narration", "")
                self.current_control_plane = step.get("control_plane", "")
                max_actions = step.get("max_actions", 20)

                self._add_log(f"Step {i+1}: {step['goal']}", "goal")

                # Check if this is a login or connect step
                goal_upper = step["goal"].upper()

                # Connect-only step (just establish connection, don't login)
                if "CONNECT" in goal_upper and "TN3270" in goal_upper and "LOGIN" not in goal_upper:
                    if not self._robust_connect(target):
                        self.error = "Failed to connect to mainframe"
                        self._add_log("Connection failed", "error")
                        break
                    self._add_log(f"Completed: {step['goal']}", "success")
                    if step.get("narration"):
                        self._add_log(step["narration"], "narration")
                        time.sleep(1)
                    continue

                # Full login step
                is_login_step = "LOGIN" in goal_upper or ("CONNECT" in goal_upper and "TSO" in goal_upper)
                if is_login_step:
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
                    time.sleep(2.5)  # Pause so the step summary is readable

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

            # DONE signal means a pattern believes the goal is achieved, but we
            # only trust it if the success criteria actually match the screen.
            if action == "DONE":
                if self._check_success(self._read_screen(), success_criteria):
                    self._add_log("Goal achieved (pattern detected completion)", "success")
                    return True
                actions_taken += 1
                self._add_log("Pattern said DONE but criteria not met - continuing", "debug")
                time.sleep(0.5)
                continue

            if not action:
                # No action needed - check if we're done
                if self._check_success(screen, success_criteria):
                    return True
                # Log what we're seeing to debug stuck states
                actions_taken += 1  # Count "no action" as an action to prevent infinite loop
                self._add_log(f"No action decided. Screen has: {screen[:100]}...", "debug")
                time.sleep(0.5)
                continue

            # Execute the action
            self._add_log(f"Action: {action}", "action")
            self._execute_action(action, target)
            actions_taken += 1
            self.action_count += 1

            time.sleep(0.3)  # Brief wait for screen update
            # Deliberate pacing so a human watching can follow along
            if self.PACING_DELAY > 0:
                time.sleep(self.PACING_DELAY)

            # Log result after action
            new_screen = self._read_screen()
            self.current_screen = new_screen  # keep UI in sync (esp. while paused)
            criteria_met = self._check_success(new_screen, success_criteria)
            self._add_log(f"After action: criteria={success_criteria}, met={criteria_met}", "debug")

            # Linger a few seconds on data-bearing screens for readability.
            if self.DATA_DWELL > 0 and self._is_data_screen(new_screen):
                time.sleep(self.DATA_DWELL)

        final_screen = self._read_screen()
        self._add_log(f"Goal timeout. Screen: {final_screen[:150]}...", "warning")
        return self._check_success(final_screen, success_criteria)

    def _read_screen(self) -> str:
        """Read current terminal screen."""
        if not AGENT_TOOLS_AVAILABLE:
            return "[Agent tools not available]"
        try:
            return read_screen() or "[Empty screen]"
        except Exception as e:
            return f"[Error reading screen: {e}]"

    def _is_data_screen(self, screen: str) -> bool:
        """True if the screen shows real command output worth lingering on.

        Used only for pacing/readability - detects LISTDS/LISTCAT/REVIEW/STATUS
        results and browsed dataset content, but not bare prompts or the logon
        screen (nothing to read there).
        """
        upper = (screen or "").upper()
        # Skip prompts / control screens - nothing to dwell on
        if "LOGON ===>" in upper or "ENTER USERID" in upper or "IKJ56700A" in upper:
            return False
        markers = (
            "--RECFM-", "--MEMBERS--", "--VOLUMES--", "DSORG",
            "IN-CAT", "NONVSAM", "IN CATALOG",
            "TSU ", "JOB ", "$HASP",
            "RECFM", "LRECL", "BLKSIZE",
        )
        if any(m in upper for m in markers):
            return True
        # A screen with several non-blank content lines (browsed file/member
        # list) is also worth a pause.
        content_lines = [l for l in screen.split("\n") if l.strip()]
        return len(content_lines) >= 6

    def _check_success(self, screen: str, criteria: List[str]) -> bool:
        """Check if success criteria are met.

        Every criterion must match. A criterion may list alternatives
        separated by "|", in which case any one of them satisfies it.
        """
        if not criteria:
            return True
        upper_screen = screen.upper()
        # Require ALL criteria to match (each may be a set of alternatives)
        for c in criteria:
            alternatives = [a.strip().upper() for a in c.split("|") if a.strip()]
            if not any(a in upper_screen for a in alternatives):
                return False
        return True

    def _decide_action(self, screen: str, goal: str, context: str, actions_taken: int) -> Optional[str]:
        """Decide what action to take - pattern matching first, then LLM."""
        # Try pattern matching FIRST - more reliable than LLM
        pattern_action = self._pattern_decide(screen, goal)
        if pattern_action == "DONE":
            # Pattern indicates we've achieved the goal - return special marker
            logger.info("Pattern indicates goal achieved")
            return "DONE"  # Signal success without checking criteria
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
- "TSOAPPLS" = TSO menu. Type 1 for ISPF.
- "READY" = TSO command prompt. Type ISPF to enter ISPF.
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

        # Debug: Log key screen indicators
        has_ready = "READY" in upper
        has_option = "OPTION" in upper
        has_browse = "BROWSE" in upper
        has_tsoappls = "TSOAPPLS" in upper or ("RFE" in upper and "RPF" in upper)
        self._add_log(f"Screen: READY={has_ready}, OPTION={has_option}, BROWSE={has_browse}, TSOAPPLS={has_tsoappls}", "debug")

        # Not connected
        if "[NOT CONNECTED]" in upper or "[EMPTY" in upper:
            return "CONNECT"

        # Completely blank screen - the terminal has nothing to show yet.
        # Never treat this as success: an empty screen proves nothing about the
        # goal. Nudge it with ENTER first, and only reconnect if it stays blank.
        screen_content = upper.replace('\n', '').replace(' ', '').strip()
        if len(screen_content) == 0:
            self._blank_screens += 1
            self._add_log(
                f"Blank screen #{self._blank_screens}, goal={goal_upper[:50]}", "debug"
            )
            if self._blank_screens >= 3:
                self._blank_screens = 0
                return "CONNECT"
            time.sleep(1.0)
            return "ENTER"
        self._blank_screens = 0

        # IKJ logoff/error messages - press Enter to continue
        if "IKJ56470I" in upper or "IKJ56420I" in upper or "IKJ56429A" in upper:
            # If goal is logoff and we see these messages, keep pressing Enter
            if "LOGOFF" in goal_upper or "EXIT" in goal_upper:
                return "ENTER"
            return "ENTER"
        if "LOGOFF" in upper and "TSO" in upper:
            return "ENTER"
        if "REENTER" in upper:
            # REENTER prompt after error - clear screen to reset
            return "CLEAR"

        # OUTPUT command prompt - exit with END
        if "ENTER JOBNAME" in upper or "JOBNAME(JOBID)" in upper:
            return "TYPE END"

        # LOGOFF handling - must come BEFORE the output-paging heuristics below.
        # A paged LISTDS/LISTCAT screen would otherwise trap us pressing ENTER
        # forever instead of working our way back to READY and logging off.
        if "LOGOFF" in goal_upper or "VTAM" in goal_upper:
            # At the VTAM logon screen = success
            if "IKJ56700A" in upper or "ENTER USERID" in upper or "LOGON ===>" in upper:
                return "DONE"
            # At READY - type LOGOFF
            if "READY" in upper:
                return "LOGOFF"
            # TSO paused mid-output - continue it
            if "***" in upper:
                return "ENTER"
            # Logoff/informational messages - acknowledge them
            if "IKJ56" in upper:
                return "ENTER"
            # Anything else (leftover command output) - flush it to reach READY
            return "CLEAR"

        # RFE Browse/Review entry panel
        is_entry_panel = (
            ("REVIEW" in upper and "ENTRY" in upper) or
            ("BROWSE" in upper and "ENTRY" in upper) or
            ("DATA SET NAME" in upper and "PARTITIONED" in upper)
        )
        if is_entry_panel:
            # If goal is to ENTER browse mode, this might be success!
            if "BROWSE" in goal_upper and ("MODE" in goal_upper or "ENTER" in goal_upper or "OPTION" in goal_upper):
                return None  # Let success criteria check handle it
            # Otherwise exit
            return "PF3"

        # LISTCAT output - exit with ENTER (scrolls through then returns)
        if "IN-CAT" in upper or "NONVSAM" in upper:
            if "EXIT" in goal_upper or "RETURN" in goal_upper or "READY" in goal_upper:
                return "ENTER"

        # LISTDS member list - press ENTER to scroll/exit
        # Detect by "--MEMBERS--" header or screen full of short PDS member names
        # But NOT if we see READY, LOGON, ISPF menu, etc.
        if "--MEMBERS--" in upper:
            return "ENTER"
        # Also detect scrolled member list (just shows member names)
        # Exclude known prompts that aren't member lists
        if "READY" not in upper and "LOGON" not in upper and "OPTION" not in upper:
            lines = [l.strip() for l in screen.split('\n') if l.strip()]
            # Require a substantial screen - a few stray lines left over from a
            # cleared screen used to trip this and spin ENTER forever.
            if len(lines) >= 8:
                # Check if most lines look like PDS member names (8 chars or less, alphanumeric + @$#)
                def is_member_name(s):
                    return len(s) <= 8 and s.isupper() and all(c.isalnum() or c in '@$#' for c in s)
                member_like = sum(1 for l in lines if is_member_name(l))
                if member_like >= 6 and member_like > len(lines) * 0.8:
                    self._add_log("Detected: LISTDS member list", "debug")
                    return "ENTER"

        # Userid locked - need to wait for session to time out
        if "USERID" in upper and "IN USE" in upper:
            logger.warning("Userid in use - waiting 10 seconds before retry")
            time.sleep(10)
            return "CLEAR"

        # Password error - need to clear and retry
        if "PASSWORD NOT AUTHORIZED" in upper or "REENTER" in upper:
            return "CLEAR"

        # VTAM command prompt (IKJ56400A) - need full LOGON command
        userid = self._current_userid or self.USERIDS[0]
        if "ENTER LOGON OR LOGOFF" in upper or "IKJ56400A" in upper:
            return f"TYPE LOGON {userid}"

        # VTAM logon panel - various formats
        is_vtam_logon = (
            "LOGON ===>" in upper or
            "LOGON==>" in upper or
            "ENTER USERID" in upper or
            "IKJ56700A" in upper
        )
        if is_vtam_logon:
            if "LOGIN" in goal_upper or "CONNECT" in goal_upper:
                return f"TYPE {userid}"
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

        # TSOAPPLS menu - the TSO apps selection BEFORE ISPF
        # Must NOT have "OPTION ===>" which indicates we're already in ISPF/RFE
        has_option_prompt = "OPTION ===>" in upper or "OPTION==>" in upper or ("OPTION" in upper and "===>" in upper)
        is_tsoappls = (
            ("TSOAPPLS" in upper or "TSO APPLICATIONS" in upper) and
            not has_option_prompt
        )
        self._add_log(f"is_tsoappls={is_tsoappls}, has_option_prompt={has_option_prompt}", "debug")
        if is_tsoappls:
            # Check EXIT/LOGOFF FIRST before other keywords
            if "EXIT" in goal_upper or "LOGOFF" in goal_upper or "RETURN" in goal_upper:
                return "PF3"  # Exit to READY first
            # Goal is to login - exit to READY so success criteria matches
            if "LOGIN" in goal_upper or "CONNECT" in goal_upper:
                return "PF3"  # Exit to TSO READY
            # Goal is to enter RFE - type 1
            if "ENTER" in goal_upper and ("RFE" in goal_upper or "ISPF" in goal_upper):
                return "TYPE 1"
            if "BROWSE" in goal_upper or "VIEW" in goal_upper or "STATUS" in goal_upper:
                return "PF3"  # Exit to TSO READY first
            return "TYPE 1"  # Default: enter RFE

        # At READY prompt and need to do something
        if "READY" in upper:
            # Enter RFE/ISPF if goal mentions it - use ISPF command on TK5
            if "RFE" in goal_upper or "ISPF" in goal_upper:
                return "TYPE ISPF"
            # Check specific commands BEFORE generic VIEW/BROWSE
            if "STATUS" in goal_upper:
                return "TYPE STATUS"
            if "OUTPUT" in goal_upper or "CONSOLE" in goal_upper:
                return "TYPE OUTPUT"
            # LISTCAT only if explicitly requested (not just "catalog" as adjective)
            if "LISTCAT" in goal_upper or ("CATALOG" in goal_upper and "CATALOGED" not in goal_upper):
                if "SYS1" in goal_upper and "PROCLIB" not in goal_upper and "PARMLIB" not in goal_upper:
                    return "TYPE LISTCAT LVL(SYS1)"
                if "PROCLIB" not in goal_upper and "PARMLIB" not in goal_upper:
                    return "TYPE LISTCAT"
            if "KICKS" in goal_upper or "CICS" in goal_upper:
                return "TYPE KICKS"
            if "COBOL" in goal_upper or "CBL" in goal_upper:
                # SYS1.COBLIB is the COBOL library that actually exists on TK5
                # (SYS2.CBL does not exist and returns a not-found error)
                return "TYPE LISTDS 'SYS1.COBLIB' M"
            # Check specific datasets BEFORE generic browse
            if "PARMLIB" in goal_upper:
                if "IEASYS" in goal_upper:
                    return "TYPE REVIEW 'SYS1.PARMLIB(IEASYS00)'"
                if "SMFPRM" in goal_upper:
                    return "TYPE REVIEW 'SYS1.PARMLIB(SMFPRM00)'"
                return "TYPE LISTDS 'SYS1.PARMLIB' M"
            if "PROCLIB" in goal_upper:
                return "TYPE LISTDS 'SYS1.PROCLIB' M"
            if "JCLLIB" in goal_upper:
                return "TYPE LISTDS 'SYS2.JCLLIB' M"
            if "SYS1.SECURE.CNTL(USERS)" in goal_upper:
                return "TYPE REVIEW 'SYS1.SECURE.CNTL(USERS)'"
            if "SYS1.SECURE.CNTL(PROFILES)" in goal_upper:
                return "TYPE REVIEW 'SYS1.SECURE.CNTL(PROFILES)'"
            # Generic browse - check for dataset pattern
            if "BROWSE" in goal_upper or "VIEW" in goal_upper:
                ds_match = re.search(r"([A-Z0-9.]+\([A-Z0-9]+\))", goal_upper)
                if ds_match:
                    return f"TYPE REVIEW '{ds_match.group(1)}'"
                # Check for dataset without member
                ds_match = re.search(r"SYS[0-9]\.[A-Z0-9.]+", goal_upper)
                if ds_match:
                    return f"TYPE LISTDS '{ds_match.group(0)}' M"
                return "TYPE ISPF"
            if "LOGOFF" in goal_upper or "EXIT" in goal_upper:
                return "LOGOFF"

        # At RFE/ISPF primary menu - multiple detection patterns for TK5
        is_rfe_menu = (
            ("OPTION" in upper and "===>" in upper) or  # "Option ===>" or "OPTION ===>"
            ("BROWSE" in upper and "EDIT" in upper) or  # Menu shows BROWSE and EDIT options
            ("RFE" in upper and "PRIMARY" in upper) or  # "RFE PRIMARY OPTION MENU"
            ("COMMAND" in upper and "BROWSE" in upper)  # Alternate prompt format
        )
        if is_rfe_menu:
            self._add_log(f"At RFE menu, goal={goal_upper[:50]}", "debug")
            # Check EXIT/LOGOFF/RETURN FIRST
            if "EXIT" in goal_upper or "LOGOFF" in goal_upper or "RETURN" in goal_upper:
                return "PF3"  # Exit RFE
            # Goal is to enter RFE - we're at menu, might be success
            if "ENTER" in goal_upper and ("RFE" in goal_upper or "ISPF" in goal_upper):
                return None  # Success - at RFE menu
            if "VIEW" in goal_upper and "MENU" in goal_upper:
                return None  # Success - viewing menu
            if "LOGIN" in goal_upper:
                return None  # Already logged in!
            # Goal is to use option 1 or enter Browse mode - type 1
            if "OPTION 1" in goal_upper or ("BROWSE" in goal_upper and "MODE" in goal_upper):
                self._add_log("Detected: enter browse mode goal", "debug")
                return "TYPE 1"  # Enter Browse mode
            if "BROWSE" in goal_upper or "VIEW" in goal_upper:
                # Check if goal is to ENTER browse (use option) vs just view
                if "ENTER" in goal_upper or "USE" in goal_upper:
                    return "TYPE 1"  # Enter Browse mode
                # Exit to TSO READY and use REVIEW command directly
                return "PF3"
            return None  # Stay at RFE for other goals

        # RFE Browse/Review entry panel - always exit with PF3
        # Whether navigating, exiting, or logging off, PF3 is the right choice
        if ("REVIEW" in upper and "ENTRY PANEL" in upper) or \
           ("BROWSE" in upper and "ENTRY PANEL" in upper) or \
           ("DATA SET NAME" in upper and "OTHER PARTITIONED" in upper):
            return "PF3"

        # Dataset not found or access denied - exit and report
        if "NOT IN CATALOG" in upper or "NOT FOUND" in upper:
            return "PF3"  # Go back and try again
        if "ACCESS DENIED" in upper or "NOT AUTHORIZED" in upper:
            self._add_log("ACCESS DENIED - need HERC01 with OPERATIONS authority", "error")
            return "PF3"  # Exit the failed command

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

        # KICKS CICS region
        if "KICKS" in upper or "DFHSM" in upper:
            if "EXIT" in goal_upper or "LOGOFF" in goal_upper:
                return "TYPE CESF LOGOFF"  # CICS exit command
            return None  # In KICKS, might be success

        # LISTCAT output - viewing catalog entries
        if "NONVSAM" in upper or "CLUSTER" in upper or "IN-CAT" in upper:
            if "EXIT" in goal_upper:
                return "ENTER"  # Exit paging output
            return None  # Viewing catalog, might be success

        # LISTDS member list - viewing dataset members
        if "--MEMBERS--" in upper or "MEMBER" in upper and "VOL" in upper:
            if "EXIT" in goal_upper:
                return "ENTER"  # Exit member list
            return None  # Viewing members, might be success

        # OUTPUT command results
        if "OUTPUT" in upper or "HELD" in upper or "SYSOUT" in upper:
            if "EXIT" in goal_upper or "LOGOFF" in goal_upper:
                return "ENTER"  # Exit output view
            return None  # Viewing output, might be success

        # Generic error recovery
        if "ERROR" in upper or "INVALID" in upper:
            return "CLEAR"

        # Catch-all for logoff goals - if we're not at READY and trying to logoff,
        # keep trying to get to VTAM by pressing PF3 or CLEAR
        if "LOGOFF" in goal_upper or "EXIT" in goal_upper:
            if "READY" not in upper:
                # Not at READY - try to exit whatever state we're in
                return "PF3"

        # Don't blindly press Enter - might cause issues
        return None

    def _execute_action(self, action: str, target: str):
        """Execute a single action."""
        if not AGENT_TOOLS_AVAILABLE:
            return

        try:
            if action == "CONNECT":
                success, msg = connect_mainframe(target)
                if not success:
                    self._add_log(f"Connection failed: {msg}", "warning")
                time.sleep(1)

            elif action == "ENTER":
                send_terminal_key("enter")

            elif action == "CLEAR":
                send_terminal_key("clear")

            elif action == "TAB":
                send_terminal_key("tab")

            elif action == "HOME":
                send_terminal_key("home")

            elif action == "LOGOFF":
                # Ensure clean input field before LOGOFF
                # Press RESET to clear any pending input
                send_terminal_key("reset")
                time.sleep(0.2)
                # Clear screen
                send_terminal_key("clear")
                time.sleep(0.5)
                # Read screen to check state
                screen = read_screen() or ""
                upper = screen.upper()
                # If not at READY, press PF3 to exit any panels
                if "READY" not in upper:
                    for _ in range(3):
                        send_terminal_key("pf", "3")
                        time.sleep(0.5)
                        screen = read_screen() or ""
                        if "READY" in screen.upper():
                            break
                # Now at READY - use newline method to ensure clean field
                send_terminal_key("home")
                time.sleep(0.1)
                # Clear entire field
                send_terminal_key("eraseeof")
                time.sleep(0.1)
                # Type LOGOFF on fresh line
                send_terminal_key("string", "LOGOFF")
                time.sleep(0.2)
                send_terminal_key("enter")
                time.sleep(2)
                # Clear any goodbye/"***" messages — but STOP as soon as we reach
                # the VTAM logon screen. Pressing ENTER at "Logon ===>" with no
                # command makes TCAS reply "INPUT NOT RECOGNIZED", so never press
                # ENTER once we're already there.
                for _ in range(3):
                    scr = (read_screen() or "").upper()
                    if ("LOGON ===>" in scr or "ENTER USERID" in scr or
                            "IKJ56700A" in scr):
                        break  # Already at the logon screen - done
                    if "***" in scr:
                        send_terminal_key("enter")
                        time.sleep(0.8)
                    else:
                        time.sleep(0.5)

            elif action == "WAIT":
                time.sleep(1)

            elif action.startswith("PF"):
                num = action[2:]
                send_terminal_key("pf", num)

            elif action.startswith("TYPE "):
                text = action[5:]
                # Clear field first (like walkthrough does)
                send_terminal_key("home")
                time.sleep(0.1)
                send_terminal_key("eraseeof")
                time.sleep(0.1)
                # Type the text
                send_terminal_key("string", text)
                time.sleep(0.2)
                send_terminal_key("enter")
                # ISPF/panel commands need more time to load
                text_upper = text.upper()
                if text_upper in ("ISPF", "RFE", "RPF", "KICKS", "1", "2", "3") or \
                   text_upper.startswith("REVIEW") or text_upper.startswith("LISTDS") or \
                   text_upper.startswith("LISTCAT"):
                    time.sleep(5)  # Panel/file load time (increased for slow datasets)
                else:
                    time.sleep(1)  # Normal command

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
