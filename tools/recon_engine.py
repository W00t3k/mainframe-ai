#!/usr/bin/env python3
"""
Native Recon Engine for Mainframe AI Assistant
Reimplements TN3270 enumeration logic as pure Python
using agent_tools.py for all emulator I/O.

Classes:
    TSOEnumerator       - TSO userid enumeration (tso-enum.nse)
    CICSEnumerator      - CICS transaction enumeration (cics-enum.nse)
    VTAMEnumerator      - VTAM APPLID enumeration (vtam-enum.nse)
    HiddenFieldDetector - Hidden field extraction (tn3270-hidden.nse)
    ScreenAnalyzer      - Credential/pattern detection (scanner.py)
    ApplicationMapper   - Depth-first screen crawler (AutomatedCrawler)
"""

import re
import hashlib
import time
from datetime import datetime
from typing import Optional, List

# Import agent_tools - try absolute import first to share connection state with web app
try:
    from agent_tools import (
        connection, exec_emulator_command, read_screen,
        normalize_screen_text
    )
except ImportError:
    from .agent_tools import (
        connection, exec_emulator_command, read_screen,
        normalize_screen_text
    )


# =============================================================================
# Base Classes
# =============================================================================

class BaseEnumerator:
    """Base class for all enumerators with common pattern matching logic."""

    # Subclasses define pattern groups as class attributes
    # Format: {"status_name": ["PATTERN1", "PATTERN2", ...]}
    PATTERN_GROUPS = {}

    def _check_connected(self) -> bool:
        """Check if TN3270 connection is active."""
        return connection.connected and connection.emulator is not None

    def _classify_by_patterns(self, text: str, pattern_groups: dict = None) -> tuple:
        """Classify screen text by matching against pattern groups.

        Args:
            text: Screen text to classify
            pattern_groups: Dict of {status: [patterns]}. Uses self.PATTERN_GROUPS if None.

        Returns:
            (status, matched_pattern) tuple
        """
        groups = pattern_groups or self.PATTERN_GROUPS
        upper = text.upper()

        for status, patterns in groups.items():
            for pattern in patterns:
                if pattern in upper:
                    return (status, pattern)

        return ("unknown", "No pattern matched")

    def stop(self):
        """Stop the enumeration."""
        self.running = False


# =============================================================================
# Terminal State Detection & Navigation
# =============================================================================
# Every recon feature depends on being in the right terminal state.
# These helpers detect the current state and navigate to the required one.
# They are designed to recover from ANY state the terminal might be in.

import logging as _logging
_log = _logging.getLogger("recon_engine")

# Terminal states
STATE_VTAM_USS = "vtam_uss"          # VTAM logon screen  (Logon ==>)
STATE_TSO_LOGON = "tso_logon"        # TSO userid prompt  (IKJ56700A)
STATE_TSO_PASSWORD = "tso_password"  # TSO password prompt
STATE_TSO_READY = "tso_ready"        # TSO READY prompt
STATE_TSO_ISPF = "tso_ispf"          # Inside ISPF panels
STATE_TSO_APPS_MENU = "tso_apps_menu"  # TSO Applications Menu (RFE, RPF, IMON)
STATE_TSO_POST_LOGIN = "tso_post_login"  # Post-login screens (broadcast, fortune, reconnect)
STATE_TSO_MORE = "tso_more"          # TSO output with *** (MORE) indicator
STATE_TSO_REENTER = "tso_reenter"    # TSO asking to reenter (IKJ56703A)
STATE_TSO_LOGON_LOGOFF = "tso_logon_logoff"  # IKJ56400A ENTER LOGON OR LOGOFF
STATE_CICS = "cics"                  # Inside a CICS region
STATE_UNKNOWN = "unknown"

# Fallback userids when primary is IN USE
_FALLBACK_USERS = {"HERC01": "HERC02", "HERC02": "HERC03", "HERC03": "HERC01"}


def _clear_input_field() -> None:
    """Clear the current input field before typing.

    Uses multiple methods to ensure field is completely clear:
    - Home() to first unprotected field
    - DeleteField() to clear entire field
    - EraseEOF() to clear to end of field
    """
    try:
        exec_emulator_command(b'Reset()')
        exec_emulator_command(b'Home()')
        exec_emulator_command(b'DeleteField()')
        exec_emulator_command(b'Home()')
        exec_emulator_command(b'EraseEOF()')
    except Exception:
        pass
    time.sleep(0.1)


def _read_screen_upper() -> str:
    """Read the terminal screen, return upper-cased text. Handles errors."""
    try:
        return read_screen().upper()
    except Exception:
        return ""


def _detect_state() -> str:
    """Read the current screen and classify terminal state.

    Order matters: check the most specific patterns first to avoid
    false matches (e.g. IKJ56700A before the generic 'IKJ5' prefix).
    """
    screen = _read_screen_upper()
    if not screen.strip():
        return STATE_UNKNOWN

    # VTAM USS logon screen — full-screen check (distinct banner)
    if "LOGON ==>" in screen or "RUNNING  TK5" in screen:
        return STATE_VTAM_USS

    # ISPF panels — full-screen check
    if "ISPF PRIMARY" in screen or "OPTION ===>" in screen or "ISPF/PDF" in screen:
        return STATE_TSO_ISPF

    # TSO Applications Menu (TK5 lands here after login)
    # Check before CICS since menu may show CICS as an option
    if ("RFE" in screen and "RPF" in screen) or "TSOAPPLS" in screen:
        return STATE_TSO_APPS_MENU
    if "IMON" in screen and "QUEUE" in screen and "TSO" in screen:
        return STATE_TSO_APPS_MENU

    # CICS/KICKS — full-screen check
    if "DFHCE" in screen or ("CICS" in screen and ("SIGN" in screen or "CESN" in screen)):
        return STATE_CICS

    # --- For TSO prompts, check only the BOTTOM of the screen ---
    # TSO scrolls: old prompts remain visible above the current one.
    # Only the last few non-empty lines contain the ACTIVE prompt.
    lines = screen.split('\n')
    bottom_lines = [l for l in lines if l.strip()]
    bottom = '\n'.join(bottom_lines[-6:]) if bottom_lines else ""

    # Post-login screens (reconnect success, broadcast messages, fortune)
    # Must press Enter to continue
    if "IKT00300" in screen or "RECONNECT SUCCESSFUL" in screen:
        return STATE_TSO_POST_LOGIN
    if "SESSION ESTABLISHED" in screen:
        return STATE_TSO_POST_LOGIN
    if "IKJ56455" in screen:  # Broadcast messages
        return STATE_TSO_POST_LOGIN
    if "LOGON IN PROGRESS" in screen:
        return STATE_TSO_POST_LOGIN

    # TSO READY prompt
    if "READY" in bottom:
        # Make sure it's the actual READY prompt, not just part of other text
        for bl in reversed(bottom_lines):
            if "READY" in bl:
                return STATE_TSO_READY
                break

    # Password failed (NOT AUTHORIZED) — bail out
    if "NOT AUTHORIZED" in bottom:
        return STATE_TSO_REENTER

    # TSO asking to reenter after invalid command
    if "IKJ56703A" in bottom or "REENTER" in bottom:
        return STATE_TSO_REENTER

    # Password prompt
    if "ENTER CURRENT PASSWORD" in bottom or "ENTER PASSWORD" in bottom:
        return STATE_TSO_PASSWORD

    # "ENTER LOGON OR LOGOFF" — userid in use
    if "IKJ56400A" in bottom or "ENTER LOGON OR LOGOFF" in bottom:
        return STATE_TSO_LOGON_LOGOFF

    # TSO userid prompt
    if "IKJ56700A" in bottom or "ENTER USERID" in bottom:
        return STATE_TSO_LOGON

    # TSO MORE indicator (*** at end of output)
    if "***" in bottom and "READY" not in bottom:
        return STATE_TSO_MORE

    # Generic TSO message prefix — probably at some prompt
    if "IKJ5" in bottom:
        return STATE_TSO_READY

    return STATE_UNKNOWN


def _is_logged_in(screen: str) -> bool:
    """Check if we're at a logged-in screen (READY, ISPF/RFE, or TSO Apps Menu)."""
    upper = screen.upper() if screen else ""
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


def _is_post_login_screen(screen: str) -> bool:
    """Check if we're at a post-login screen that needs Enter to advance."""
    upper = screen.upper() if screen else ""
    if "IKT00300" in upper or "SESSION ESTABLISHED" in upper:
        return True
    if "RECONNECT SUCCESSFUL" in upper:
        return True
    if "IKJ56455" in upper:  # Broadcast messages
        return True
    if "LOGON IN PROGRESS" in upper:
        return True
    return False


def _press_through_screens(max_pages: int = 10) -> str:
    """Press Enter through broadcast/fortune/info screens until we reach
    a usable screen (READY, ISPF/RFE, TSO Apps Menu, or Logon)."""
    for _ in range(max_pages):
        screen = _read_screen_upper()
        if _is_logged_in(screen):
            return screen
        # VTAM/Logon screen means we're NOT logged in — stop pressing
        if ("LOGON ==>" in screen or "LOGON ===>" in screen) and "IKT00300" not in screen:
            return screen
        if "IKJ56400" in screen and "IKT00300" not in screen:
            return screen
        # Error state — don't press Enter blindly
        if "REENTER" in screen or "INVALID" in screen:
            return screen
        # Post-login screens (reconnect success, broadcast, fortune) — press Enter
        if _is_post_login_screen(screen):
            _fast_key("enter", wait=True)
            time.sleep(3)
            continue
        # Mostly blank screen after reconnect — press Enter to advance
        stripped = screen.strip()
        if len(stripped) < 80:
            _fast_key("enter", wait=True)
            time.sleep(2)
            continue
        # Press Enter and check again
        _fast_key("enter", wait=True)
        time.sleep(2)
    return _read_screen_upper()


def _cancel_stuck_tso_session(userid: str = "HERC01") -> None:
    """Reply CANCEL to all pending IEF238D operator messages that block TSO login.
    Also attempts to cancel the zombie TSU session by jobname via Hercules console."""
    import urllib.request
    import urllib.parse
    import os as _os

    hardcopy = _os.path.join(
        _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))),
        "tk5", "mvs-tk5", "log", "hardcopy.log"
    )
    try:
        if _os.path.exists(hardcopy):
            with open(hardcopy, errors="replace") as f:
                content = f.read()
            import re as _re
            nums = set(_re.findall(r'\*([0-9A-Fa-f]{2})\s+IEF238D', content))
            for num in nums:
                cmd = urllib.parse.quote(f"/R {num},CANCEL")
                url = f"http://localhost:8038/cgi-bin/tasks/cmd?cmd={cmd}"
                urllib.request.urlopen(url, timeout=5)
                _log.info(f"Replied CANCEL to IEF238D *{num}")
    except Exception as e:
        _log.warning(f"IEF238D cancel error: {e}")
    # Also try cancelling the stuck TSO job by userid
    try:
        cmd = urllib.parse.quote(f"/C {userid}")
        url = f"http://localhost:8038/cgi-bin/tasks/cmd?cmd={cmd}"
        urllib.request.urlopen(url, timeout=5)
    except Exception:
        pass
    time.sleep(0.5)  # Reduced from 3s to speed up login recovery


def _clear_screen_state() -> None:
    """Dismiss any pending prompt: page through MORE, clear REENTER, etc."""
    for _ in range(8):
        state = _detect_state()
        if state == STATE_TSO_MORE:
            _fast_key("enter", wait=True)
            time.sleep(0.5)
        elif state == STATE_TSO_REENTER:
            _fast_key("pa", "1", wait=True)
            time.sleep(0.3)
            _fast_key("clear")
            time.sleep(0.3)
        else:
            break


def _reset_terminal() -> None:
    """Reset the terminal to a clean state before running any assessment.

    Aggressive reset: multiple attempts to clear any stuck state.
    """
    # First check if connection is alive
    if not connection.connected or not connection.emulator:
        return

    # Try Reset multiple times
    for _ in range(3):
        try:
            exec_emulator_command(b'Reset()')
        except Exception:
            pass
        time.sleep(0.1)

    # Clear keyboard lock and pending prompts
    _fast_key("pa", "1", wait=True)
    time.sleep(0.2)
    _fast_key("clear")
    time.sleep(0.3)

    # If screen is blank, send Enter to wake it up
    screen = read_screen()
    if not screen or not screen.strip():
        _fast_key("enter", wait=True)
        time.sleep(0.5)

    # Clear screen state (MORE, REENTER, etc)
    _clear_screen_state()


def _ensure_connection() -> bool:
    """Verify connection is alive and responsive. Reconnect if needed."""
    if not connection.connected or not connection.emulator:
        _log.warning("_ensure_connection: no connection object")
        return False

    # Simple liveness check - just verify emulator object is valid
    em = connection.emulator
    if em is None:
        _log.warning("_ensure_connection: emulator is None")
        return False

    # Try reading screen as a quick health check (non-blocking)
    try:
        screen = read_screen()
        if screen is None:
            _log.warning("_ensure_connection: read_screen returned None")
            # Try to reconnect
            try:
                from agent_tools import connect_mainframe
                host = getattr(connection, 'host', 'localhost')
                port = getattr(connection, 'port', 3270)
                success, _ = connect_mainframe(f"{host}:{port}")
                return success
            except Exception as e:
                _log.error("_ensure_connection: reconnect failed: %s", e)
                return False
        return True
    except Exception as e:
        _log.error("_ensure_connection: health check failed: %s", e)
        return False


def _go_to_vtam(max_attempts: int = 4) -> bool:
    """Navigate from any state back to the VTAM USS logon screen.
    Returns True if successful."""
    for attempt in range(max_attempts):
        _clear_screen_state()
        state = _detect_state()
        _log.debug("_go_to_vtam attempt %d: state=%s", attempt, state)

        if state == STATE_VTAM_USS:
            return True

        if state == STATE_TSO_ISPF:
            # Exit ISPF — press PF3 up to 6 times to handle nested panels
            for _ in range(6):
                _fast_key("pf", "3", wait=True)
                time.sleep(0.4)
                s = _detect_state()
                if s != STATE_TSO_ISPF:
                    break
            # Now at TSO READY — fall through to logoff

        if state == STATE_TSO_APPS_MENU:
            # Exit TSO Apps Menu — PF3 to READY, then logoff
            for _ in range(4):
                _fast_key("pf", "3", wait=True)
                time.sleep(0.5)
                s = _detect_state()
                if s == STATE_TSO_READY or s == STATE_VTAM_USS:
                    break
            # Fall through to logoff if now at READY

        # At TSO login prompt - press Clear to go back to VTAM USS
        if state in (STATE_TSO_LOGON, STATE_TSO_PASSWORD, STATE_TSO_REENTER,
                     STATE_TSO_LOGON_LOGOFF):
            _fast_key("clear")
            time.sleep(0.3)
            continue

        # Logged into TSO - type LOGOFF to exit
        if state in (STATE_TSO_READY, STATE_TSO_MORE, STATE_TSO_ISPF,
                     STATE_TSO_APPS_MENU, STATE_TSO_POST_LOGIN):
            _clear_input_field()
            _fast_key("string", "LOGOFF")
            _fast_key("enter", wait=True)
            time.sleep(1.0)
            continue

        if state == STATE_CICS:
            _clear_input_field()
            _fast_key("string", "CESF LOGOFF")
            _fast_key("enter", wait=True)
            time.sleep(0.8)
            continue

        # STATE_UNKNOWN — try PA1 to reset, then LOGOFF
        _fast_key("pa", "1", wait=True)
        time.sleep(0.5)
        _clear_input_field()
        _fast_key("string", "LOGOFF")
        _fast_key("enter", wait=True)
        time.sleep(1.0)

    return _detect_state() == STATE_VTAM_USS


def _go_to_tso_logon() -> bool:
    """Navigate to the TSO logon userid prompt.
    Returns True if successful."""
    state = _detect_state()

    # Even if already at TSO logon, go through VTAM to ensure cursor is positioned
    # correctly. The cursor might be in the wrong place after a terminal reset.
    if state != STATE_VTAM_USS:
        _fast_key("clear")
        time.sleep(0.3)
        state = _detect_state()
        if state != STATE_VTAM_USS:
            if not _go_to_vtam():
                return False

    # On TK5, typing "TSO" at Logon ==> goes to the TSO userid prompt
    # The cursor will be positioned in the userid field after this
    _clear_input_field()
    _fast_key("string", "TSO")
    _fast_key("enter", wait=True)
    time.sleep(0.5)
    state = _detect_state()
    # May also land on VTAM USS if TSO app isn't defined - keep trying
    return state in (STATE_TSO_LOGON, STATE_TSO_PASSWORD, STATE_VTAM_USS)


def _send_password(password: str) -> None:
    """Type password and press Enter. Used at any TSO password prompt.

    Clears the input field first to avoid appending to leftover text
    from a previous failed attempt (REENTER scenario).
    """
    try:
        exec_emulator_command(b'Reset()')
        exec_emulator_command(b'Home()')
        exec_emulator_command(b'EraseEOF()')
    except Exception:
        pass
    time.sleep(0.2)
    _fast_key("string", password)
    _fast_key("enter", wait=True)
    time.sleep(0.8)


def _go_to_tso_ready(userid: str = "HERC01", password: str = "CUL8TR") -> bool:
    """Log into TSO and reach the READY prompt.

    If the requested userid is in use, automatically falls back to HERC02/HERC03.
    Handles every known intermediate state:
      - Already at READY → done
      - TSO Apps Menu → exit to READY
      - ISPF → PF3 out to READY
      - VTAM USS → type TSO → userid → password → READY
      - Userid in use → auto-cancel stuck session, reconnect, or try fallback
      - Reconnect prompt → press Enter
      - Post-login screens → press through
      - MORE / REENTER → dismiss
    Returns True if at READY when done.
    """
    # Build fallback chain
    userids_to_try = [userid]
    fallback = _FALLBACK_USERS.get(userid.upper())
    if fallback:
        userids_to_try.append(fallback)
        fallback2 = _FALLBACK_USERS.get(fallback)
        if fallback2 and fallback2 != userid.upper():
            userids_to_try.append(fallback2)

    for current_userid in userids_to_try:
        _log.info("Trying TSO login as %s", current_userid)
        result = _try_tso_login(current_userid, password)
        if result:
            return True
        _log.warning("Login as %s failed, trying next", current_userid)
        # Make sure we're back at a clean state before trying next
        _go_to_vtam()

    final = _detect_state()
    _log.error("All TSO login attempts failed. Final state: %s", final)
    return _is_logged_in(_read_screen_upper()) or final == STATE_TSO_READY


def _navigate_apps_menu_to_ready() -> bool:
    """From TSO Apps Menu, press PF3 repeatedly to get to TSO READY."""
    for _ in range(4):
        _fast_key("pf", "3", wait=True)
        time.sleep(1.0)
        state = _detect_state()
        if state == STATE_TSO_READY:
            return True
        screen = _read_screen_upper()
        if "READY" in screen:
            return True
    return False


def _try_tso_login(userid: str, password: str) -> bool:
    """Single attempt to log into TSO as the given userid.

    Walks through screens step by step. Returns True if READY reached.
    Returns False if userid is in use or login fails (caller should
    try a different userid).
    """
    in_use_count = 0

    for step in range(25):
        # Bail immediately if connection died
        if not connection.connected or not connection.emulator:
            return False

        _clear_screen_state()
        state = _detect_state()
        screen = _read_screen_upper()
        # Temporary debug — shows in server stdout
        last_lines = [l for l in screen.split('\n') if l.strip()][-3:]

        # === CONNECTION LOST ===
        if "NOT CONNECTED" in screen:
            return False

        # === SUCCESS: TSO READY ===
        if state == STATE_TSO_READY:
            return True

        # === SUCCESS: TSO Apps Menu — navigate to READY ===
        if state == STATE_TSO_APPS_MENU:
            if _navigate_apps_menu_to_ready():
                return True
            continue

        # === SUCCESS: Logged in (check with helper) ===
        if _is_logged_in(screen):
            # Try to get to READY from wherever we are
            if state == STATE_TSO_ISPF:
                for _ in range(6):
                    _fast_key("pf", "3", wait=True)
                    time.sleep(0.5)
                    if _detect_state() == STATE_TSO_READY:
                        return True
            return True

        # === POST-LOGIN SCREENS — press through broadcasts/fortune ===
        if state == STATE_TSO_POST_LOGIN or _is_post_login_screen(screen):
            result_screen = _press_through_screens()
            if _is_logged_in(result_screen):
                # Now navigate to READY
                if "READY" in result_screen:
                    return True
                state = _detect_state()
                if state == STATE_TSO_APPS_MENU:
                    if _navigate_apps_menu_to_ready():
                        return True
                continue
            continue

        # === PASSWORD FAILED — must be checked BEFORE password handler ===
        if "NOT AUTHORIZED" in screen or "INVALID PASSWORD" in screen:
            _fast_key("pa", "1", wait=True)
            time.sleep(0.5)
            return False

        # === USERID IN USE — try auto-cancel, then reconnect ===
        if state == STATE_TSO_LOGON_LOGOFF or "IKJ56400A" in screen:
            reconnect = "IN USE" in screen or "LOGON REJECTED" in screen
            if reconnect:
                in_use_count += 1
                if in_use_count == 1:
                    _cancel_stuck_tso_session(userid)
                    continue
                if in_use_count >= 3:
                    return False  # Let caller try fallback userid
            cmd = f"LOGON {userid} RECONNECT" if reconnect else f"LOGON {userid}"
            _clear_input_field()
            _fast_key("string", cmd)
            _fast_key("enter", wait=True)
            time.sleep(1.0)
            continue

        if "IKJ56425I" in screen or ("IN USE" in screen and "IKJ" in screen):
            in_use_count += 1
            if in_use_count == 1:
                _cancel_stuck_tso_session(userid)
                continue
            if in_use_count >= 3:
                return False
            _clear_input_field()
            _fast_key("string", f"LOGON {userid} RECONNECT")
            _fast_key("enter", wait=True)
            time.sleep(0.5)
            continue

        # === "IN USE" without IKJ56400 prompt ===
        if "IN USE" in screen or "LOGON REJECTED" in screen:
            in_use_count += 1
            if in_use_count == 1:
                _cancel_stuck_tso_session(userid)
                _fast_key("clear")
                time.sleep(0.5)
                continue
            if in_use_count >= 3:
                return False
            _fast_key("clear")
            time.sleep(0.3)
            _clear_input_field()
            _fast_key("string", f"LOGON {userid} RECONNECT")
            _fast_key("enter", wait=True)
            time.sleep(0.5)
            continue

        # === ISPF — PF3 out to READY ===
        if state == STATE_TSO_ISPF:
            for _ in range(6):
                _fast_key("pf", "3", wait=True)
                time.sleep(0.4)
                if _detect_state() != STATE_TSO_ISPF:
                    break
            continue

        # === PASSWORD PROMPT — enter password ===
        if state == STATE_TSO_PASSWORD:
            _send_password(password)
            continue

        # === USERID PROMPT — enter userid ===
        if state == STATE_TSO_LOGON:
            _clear_input_field()
            _fast_key("string", userid)
            _fast_key("enter", wait=True)
            time.sleep(0.5)
            continue

        # === LOGON RECONNECT — press Enter to proceed ===
        if "LOGON RECONNECT" in screen:
            _fast_key("enter", wait=True)
            time.sleep(0.5)
            continue

        # === ALREADY LOGGED ON — press Enter ===
        if "ALREADY LOGGED ON" in screen or "IKJ56455I" in screen:
            _fast_key("enter", wait=True)
            time.sleep(0.5)
            continue

        # === MORE indicator ===
        if state == STATE_TSO_MORE:
            _fast_key("enter", wait=True)
            time.sleep(0.5)
            continue

        # === REENTER prompt ===
        if state == STATE_TSO_REENTER:
            _fast_key("pa", "1", wait=True)
            time.sleep(0.3)
            _fast_key("clear")
            time.sleep(0.3)
            continue

        # === ENTER AN OPTION ===
        if "ENTER AN OPTION" in screen or "ENTER OPTION" in screen:
            _fast_key("enter", wait=True)
            time.sleep(1.0)
            continue

        # === VTAM USS — type userid at the Logon ==> field (TK5 style) ===
        if state == STATE_VTAM_USS:
            _clear_input_field()
            _fast_key("string", userid)
            _fast_key("enter", wait=True)
            time.sleep(1.0)
            # Check for password prompt immediately after
            screen = _read_screen_upper()
            if "PASSWORD" in screen or "IKJ56476" in screen or "ENTER CURRENT" in screen:
                _send_password(password)
                # Press through post-login screens
                result_screen = _press_through_screens()
                if _is_logged_in(result_screen):
                    state = _detect_state()
                    if state == STATE_TSO_APPS_MENU:
                        _navigate_apps_menu_to_ready()
                    return True
            continue

        # === CICS — logoff first ===
        if state == STATE_CICS:
            _clear_input_field()
            _fast_key("string", "CESF LOGOFF")
            _fast_key("enter", wait=True)
            time.sleep(0.8)
            continue

        # === INPUT NOT RECOGNIZED — keyboard locked, Reset+Clear ===
        if "INPUT NOT RECOGNIZED" in screen or "NOT RECOGNIZED" in screen:
            try:
                exec_emulator_command(b'Reset()')
            except Exception:
                pass
            time.sleep(0.3)
            _fast_key("clear")
            time.sleep(2)
            continue

        # === Blank/frozen screen — wait for ISPLOGON processing ===
        if not screen.strip():
            deadline = time.time() + 15
            while time.time() < deadline:
                time.sleep(3)
                screen = _read_screen_upper()
                if screen.strip():
                    break
            continue

        # === UNKNOWN — press Enter once ===
        _log.debug("  unknown screen, pressing Enter")
        _fast_key("enter", wait=True)
        time.sleep(1.0)

    # Final check
    final_state = _detect_state()
    return final_state == STATE_TSO_READY or _is_logged_in(_read_screen_upper())


def _wait_output(timeout: float = 0.5) -> None:
    """Wait for screen output using sleep (Wait commands hang)."""
    time.sleep(timeout)


def _fast_key(key_type: str, value: str = "", wait: bool = False) -> None:
    """Send a key to the emulator. Uses sleep instead of Wait to avoid hangs."""
    try:
        exec_emulator_command(b'Reset()')
    except Exception:
        pass

    try:
        if key_type == "string":
            if value:
                exec_emulator_command(f'String("{value}")'.encode())
        elif key_type == "enter":
            exec_emulator_command(b'Enter()')
            if wait:
                time.sleep(0.8)
        elif key_type == "clear":
            exec_emulator_command(b'Clear()')
            if wait:
                time.sleep(0.3)
        elif key_type == "pf":
            exec_emulator_command(f'PF({value})'.encode())
            if wait:
                time.sleep(0.5)
        elif key_type == "tab":
            exec_emulator_command(b'Tab()')
        elif key_type == "pa":
            exec_emulator_command(f'PA({value})'.encode())
            if wait:
                time.sleep(0.3)
    except Exception:
        pass


# =============================================================================
# Built-in Wordlists
# =============================================================================

DEFAULT_TSO_USERIDS = [
    "IBMUSER", "HERC01", "HERC02", "HERC03", "HERC04",
    "MVSUSER", "MVSUSR", "ADMIN", "OPER", "OPERATOR",
    "SYSPROG", "SYSTASK", "STCUSER", "CICSUSR", "CICSUSER",
    "IMSUSER", "DBADMIN", "SECADM", "AUDITOR", "GUEST",
    "TEST", "TESTUSER", "USER01", "USER02", "USER03",
    "VTAMUSER", "NETVIEW", "SDSF", "RACFADM", "TSOADM",
]

DEFAULT_CICS_TRANSACTIONS = [
    "CEDA", "CEDB", "CEDC", "CECI", "CECS", "CECT",
    "CEDF", "CEDX", "CEGN", "CEHS", "CEKL", "CEMN",
    "CEMT", "CEOT", "CEPD", "CEPF", "CEPH", "CEPM",
    "CEPQ", "CESD", "CESF", "CESN", "CESL", "CEST",
    "CETR", "CEX2", "CFCR", "CFQR", "CFOR", "CFQS",
    "CFTL", "CGRP", "CIQR", "CKAM", "CKBC", "CKBM",
    "CKBP", "CKDL", "CKQC", "CKRS", "CKRT", "CKSD",
    "CKTI", "CLQ2", "CMAC", "CMSG", "CMPX", "CMXI",
    "COSH", "CPIA", "CPIH", "CPIL", "CPIQ", "CPIR",
    "CQPI", "CQPO", "CQRY", "CRMD", "CRMF", "CRPA",
    "CRPC", "CRPM", "CRTE", "CRTX", "CSAC", "CSCY",
    "CSFE", "CSFR", "CSFU", "CSGM", "CSHR", "CSKP",
    "CSLG", "CSMI", "CSNC", "CSOL", "CSPS", "CSQC",
    "CSQO", "CSRD", "CSRS", "CSSY", "CSZI", "CWBA",
    "CWBG", "CWTO", "CWXN", "CWXU", "DSNC", "DSNP",
    "DSNT", "DSNU", "EXEC", "ICRQ", "IMPX", "IVTL",
    "KFUN", "KXPR", "LOCK", "LSRP", "MQCL", "MQCO",
    "MQIN", "MQMT", "MQSC", "MSEZ", "OHCN", "SXZZ",
    "VLMP", "WBSN", "WBST", "XZKU",
    "CADP", "CALE", "CARL", "CAUT", "CBAM", "CBRC",
    "CCIN", "CCRL", "CDBC", "CDBI", "CDBS", "CDTS",
    "CEBT", "CELP", "CENR", "CEST", "CETR", "CFCL",
    "CFOR", "CGNS", "CHRM", "CJSL", "CKAM", "CKDL",
    "CLOP", "CMMT", "COLM", "COMI", "COTR", "CPSS",
    "CRAQ", "CRSP", "CRTB", "CRVW", "CSCA", "CSCM",
    "CSCO", "CSDN", "CSOT", "CSQP", "CSTA", "CSTD",
    "CSWP", "CTRN", "CTSD", "CWBA", "CWRK", "CZOP",
    "CZRD", "CZSD", "CZUP",
]

DEFAULT_VTAM_APPLIDS = [
    "TSO", "TSOA", "TSOB", "TSOC", "TSO1", "TSO2", "TSO3",
    "CICS", "CICSA", "CICSB", "CICSC", "CICS1", "CICS2",
    "CICSPROD", "CICSTEST", "CICSDEV",
    "IMS", "IMSA", "IMS1", "IMSPROD", "IMSTEST",
    "NVAS", "NETVIEW", "NLDM",
    "TPX", "TPXA",
    "DB2A", "DB2B", "DB2PROD", "DB2TEST",
    "MQMA", "MQMB", "MQMPROD",
    "SDSF", "ISPF", "PDF",
    "VTAM", "APPC", "LU62",
]


# =============================================================================
# TSOEnumerator
# =============================================================================

class TSOEnumerator:
    """Enumerate valid TSO userids by navigating to the TSO logon screen
    and probing each candidate.

    Reimplements the logic of nmap's tso-enum.nse using agent_tools I/O.
    """

    # Indicators that the userid is valid (password prompt reached or in use)
    VALID_PATTERNS = [
        "ENTER PASSWORD",
        "IKJ56476I",       # TSO password prompt message
        "LOGON RECONNECT",
        "ALREADY LOGGED ON",
        "IKJ56455I",       # userid already logged on
        "IKJ56425I",       # userid in use (login rejected but userid exists)
        "IN USE",          # userid is currently logged in
        "PASSWORD",
        "ENTER CURRENT PASSWORD",
    ]

    # Indicators the userid doesn't exist
    INVALID_PATTERNS = [
        "IKJ56420I",       # userid not authorized to use TSO
        "NOT AUTHORIZED",
        "USERID NOT DEFINED",
        "UNKNOWN USERID",
        "NOT IN LIST OF VALID LOGON",
        "IKJ56421I",       # userid not defined to RACF
    ]

    # Indicators of a locked account
    LOCKED_PATTERNS = [
        "REVOKED",
        "IKJ56422I",       # userid has been revoked
        "ACCOUNT LOCKED",
        "NOT ALLOWED TO LOGON",
    ]

    def __init__(self, userids: Optional[list[str]] = None,
                 command_sequence: Optional[list[str]] = None):
        """
        Args:
            userids: List of userids to test. Uses defaults if None.
            command_sequence: Commands to navigate to TSO logon screen.
                             Defaults to ["TSO"] to handle VTAM USS screen.
        """
        self.userids = userids or list(DEFAULT_TSO_USERIDS)
        self.command_sequence = command_sequence or ["TSO"]
        self.results: list[dict] = []
        self.running = False
        self.progress = 0
        self.total = len(self.userids)

    def _check_connected(self) -> bool:
        return connection.connected and connection.emulator is not None

    def _navigate_to_tso_logon(self) -> bool:
        """Navigate to TSO logon userid prompt.
        Uses the navigation helpers to get to VTAM USS then TSO logon.
        Always calls _go_to_tso_logon to ensure cursor is positioned correctly."""
        return _go_to_tso_logon()

    def _reset_to_tso_logon(self):
        """After testing a userid, get back to the TSO userid prompt."""
        screen = read_screen().upper()
        # If at password prompt or logged in — escape
        if "PASSWORD" in screen or "READY" in screen or "ISPF" in screen:
            _fast_key("pa", "1", wait=True)
            time.sleep(0.5)
            _fast_key("clear")
            time.sleep(0.3)
            _fast_key("string", "LOGOFF")
            _fast_key("enter", wait=True)
            time.sleep(0.5)
        # If we ended up at VTAM, send TSO again
        state = _detect_state()
        if state == STATE_VTAM_USS:
            _clear_input_field()
            _fast_key("string", "TSO")
            _fast_key("enter", wait=True)
            time.sleep(0.5)
        # If already at TSO logon or REENTER prompt, just clear input
        elif state in (STATE_TSO_LOGON, STATE_UNKNOWN):
            _clear_input_field()

    def _classify_screen(self, screen_text: str) -> tuple[str, str]:
        """Classify screen response after sending a userid.

        Returns:
            (status, message) where status is 'valid', 'invalid', 'locked', or 'unknown'
        """
        upper = screen_text.upper()

        for pattern in self.LOCKED_PATTERNS:
            if pattern in upper:
                return "locked", pattern

        for pattern in self.VALID_PATTERNS:
            if pattern in upper:
                return "valid", pattern

        for pattern in self.INVALID_PATTERNS:
            if pattern in upper:
                return "invalid", pattern

        return "unknown", "Unrecognized response"

    def enumerate(self, callback=None) -> list[dict]:
        """Run TSO enumeration against all candidate userids.

        Navigates to TSO logon prompt first, enumerates userids,
        then returns to TSO READY.

        Args:
            callback: Optional callable(progress, total, result_dict) for progress updates.

        Returns:
            List of {userid, status, message, screen_text} dicts.
        """
        if not self._check_connected():
            return [{"userid": "*", "status": "error", "message": "Not connected"}]

        # Verify connection is healthy
        if not _ensure_connection():
            return [{"userid": "*", "status": "error",
                     "message": "Connection not responsive"}]

        # Reset terminal to clean state before starting
        _reset_terminal()

        # Navigate to TSO logon prompt
        if not self._navigate_to_tso_logon():
            return [{"userid": "*", "status": "error",
                     "message": "Could not navigate to TSO logon screen"}]

        self.results = []
        self.running = True
        self.progress = 0
        self.total = len(self.userids)

        for i, userid in enumerate(self.userids):
            if not self.running:
                break

            self.progress = i + 1

            # Make sure we're at the TSO logon prompt
            state = _detect_state()
            if state != STATE_TSO_LOGON:
                self._reset_to_tso_logon()

            # Clear input field and send the userid
            _clear_input_field()
            _fast_key("string", userid)
            _fast_key("enter", wait=True)
            time.sleep(0.5)

            screen_text = read_screen()
            status, message = self._classify_screen(screen_text)

            result = {
                "userid": userid,
                "status": status,
                "message": message,
                "screen_text": screen_text[:500],
            }
            self.results.append(result)

            if callback:
                callback(self.progress, self.total, result)

            # Reset for next attempt
            self._reset_to_tso_logon()

        self.running = False

        # Return to TSO READY
        _go_to_tso_ready()

        return self.results

    def stop(self):
        self.running = False


# =============================================================================
# CICSEnumerator
# =============================================================================

class CICSEnumerator:
    """Enumerate valid CICS transactions by sending each 4-char ID
    and classifying the response.

    Reimplements cics-enum.nse logic.
    """

    INVALID_PATTERNS = [
        "DFHAC2001",       # Transaction not recognized
        "NOT RECOGNIZED",
        "UNKNOWN TRANSACTION",
        "INVALID TRANSACTION",
    ]

    AUTH_REQUIRED_PATTERNS = [
        "DFHAC2002",       # Not authorized
        "UNAUTHORIZED",
        "NOT AUTHORIZED",
        "SECURITY VIOLATION",
        "DFHAC2206",       # Authorization failure
    ]

    ERROR_PATTERNS = [
        "DFHAC2008",       # Transaction disabled
        "DISABLED",
        "DFHRT4401",       # Region not available
        "NOT AVAILABLE",
    ]

    def __init__(self, transactions: Optional[list[str]] = None):
        self.transactions = transactions or list(DEFAULT_CICS_TRANSACTIONS)
        self.results: list[dict] = []
        self.running = False
        self.progress = 0
        self.total = len(self.transactions)

    def _check_connected(self) -> bool:
        return connection.connected and connection.emulator is not None

    def _classify_screen(self, screen_text: str) -> tuple[str, str]:
        upper = screen_text.upper()

        for pattern in self.INVALID_PATTERNS:
            if pattern in upper:
                return "invalid", pattern

        for pattern in self.AUTH_REQUIRED_PATTERNS:
            if pattern in upper:
                return "auth_required", pattern

        for pattern in self.ERROR_PATTERNS:
            if pattern in upper:
                return "error", pattern

        stripped = screen_text.strip()
        if not stripped or len(stripped) < 5:
            return "valid_blank", "Screen cleared (transaction executed)"

        return "valid", "Transaction responded"

    # Common CICS APPLIDs to try when navigating
    CICS_APPLIDS = ["CICS", "CICS2", "CICSA", "CICSTEST", "KICKS"]

    def _navigate_to_cics(self) -> bool:
        """Navigate to a CICS region from VTAM USS.
        Tries common CICS APPLIDs until one responds."""
        if not _go_to_vtam():
            return False

        for applid in self.CICS_APPLIDS:
            _fast_key("clear")
            time.sleep(0.3)
            _fast_key("string", f"LOGON APPLID({applid})")
            _fast_key("enter", wait=True)
            time.sleep(0.5)

            screen = read_screen().upper()
            # Check if we got into CICS (no error patterns)
            if any(p in screen for p in ["DFHCE", "SIGN", "CICS", "CESN",
                                          "TRANSACTION", "ENTER TRANS"]):
                return True
            # Also check: if it's not an error, we might be in CICS
            if not any(p in screen for p in ["NOT ACTIVE", "UNABLE",
                                              "IST075I", "IST453I",
                                              "UNKNOWN", "NOT FOUND",
                                              "INACTIVE", "LOGON ==>"]):
                # Might be in the application
                state = _detect_state()
                if state == STATE_CICS:
                    return True

            # Failed — go back to VTAM and try next
            _fast_key("clear")
            time.sleep(0.3)

        return False

    def enumerate(self, callback=None) -> list[dict]:
        """Run CICS transaction enumeration.

        Navigates to a CICS region first. If no CICS is available,
        returns a clear error. Returns to TSO READY after enumeration.

        Args:
            callback: Optional callable(progress, total, result_dict).

        Returns:
            List of {transaction_id, status, message, screen_text} dicts.
        """
        if not self._check_connected():
            return [{"transaction_id": "*", "status": "error",
                     "message": "Not connected"}]

        # Verify connection is healthy
        if not _ensure_connection():
            return [{"transaction_id": "*", "status": "error",
                     "message": "Connection not responsive"}]

        # Reset terminal to clean state before starting
        _reset_terminal()

        # Try to navigate to CICS
        if not self._navigate_to_cics():
            # No CICS available — return to TSO and report
            _go_to_tso_ready()
            return [{"transaction_id": "*", "status": "error",
                     "message": "No CICS region found. Tried: " +
                     ", ".join(self.CICS_APPLIDS)}]

        self.results = []
        self.running = True
        self.progress = 0
        self.total = len(self.transactions)

        for i, txn in enumerate(self.transactions):
            if not self.running:
                break

            self.progress = i + 1

            # Clear and send transaction
            _fast_key("clear")
            time.sleep(0.3)
            _fast_key("string", txn)
            _fast_key("enter", wait=True)
            time.sleep(0.8)

            screen_text = read_screen()
            status, message = self._classify_screen(screen_text)

            result = {
                "transaction_id": txn,
                "status": status,
                "message": message,
                "screen_text": screen_text[:500],
            }
            self.results.append(result)

            if callback:
                callback(self.progress, self.total, result)

            # Clear after each attempt
            _fast_key("clear")
            time.sleep(0.2)

        self.running = False

        # Return to TSO READY
        _go_to_vtam()
        _go_to_tso_ready()

        return self.results

    def stop(self):
        self.running = False


# =============================================================================
# VTAMEnumerator
# =============================================================================

class VTAMEnumerator:
    """Enumerate valid VTAM application IDs by sending LOGON APPLID(...)
    and classifying the response.

    Reimplements vtam-enum.nse logic.
    """

    ERROR_PATTERNS = [
        "UNABLE TO ESTABLISH SESSION",
        "COMMAND UNRECOGNIZED",
        "INVALID COMMAND",
        "SESSION NOT BOUND",
        "UNKNOWN APPLID",
        "APPLID NOT FOUND",
        "IST075I",          # Name not found
        "IST453I",          # LOGON failed
        "IST457I",          # Session setup failure
        "IST526I",          # Insufficient storage
        "NOT ACTIVE",
        "INACTIVE",
    ]

    VALID_PATTERNS = [
        "LOGON IN PROGRESS",
        "SESSION ESTABLISHED",
        "BOUND",
        "USS",
        "READY",
    ]

    def __init__(self, applids: Optional[list[str]] = None):
        self.applids = applids or list(DEFAULT_VTAM_APPLIDS)
        self.results: list[dict] = []
        self.running = False
        self.progress = 0
        self.total = len(self.applids)

    def _check_connected(self) -> bool:
        return connection.connected and connection.emulator is not None

    def _classify_screen(self, screen_text: str) -> tuple[str, str]:
        upper = screen_text.upper()

        for pattern in self.ERROR_PATTERNS:
            if pattern in upper:
                return "invalid", pattern

        for pattern in self.VALID_PATTERNS:
            if pattern in upper:
                return "valid", pattern

        # If no error detected, the applid probably responded
        stripped = screen_text.strip()
        if stripped and len(stripped) > 20:
            return "valid", "Application responded"

        return "unknown", "Unrecognized response"

    def enumerate(self, callback=None) -> list[dict]:
        """Run VTAM APPLID enumeration.

        Navigates to the VTAM USS screen first (logging off TSO if needed),
        enumerates APPLIDs, then returns to TSO READY.

        Args:
            callback: Optional callable(progress, total, result_dict).

        Returns:
            List of {applid, status, message, screen_text} dicts.
        """
        if not self._check_connected():
            return [{"applid": "*", "status": "error",
                     "message": "Not connected"}]

        # Verify connection is healthy
        if not _ensure_connection():
            return [{"applid": "*", "status": "error",
                     "message": "Connection not responsive"}]

        # Reset terminal to clean state before starting
        _reset_terminal()

        # Navigate to VTAM USS screen
        if not _go_to_vtam():
            return [{"applid": "*", "status": "error",
                     "message": "Could not navigate to VTAM USS screen"}]

        self.results = []
        self.running = True
        self.progress = 0
        self.total = len(self.applids)

        for i, applid in enumerate(self.applids):
            if not self.running:
                break

            self.progress = i + 1

            # Make sure we're at VTAM USS for each attempt
            state = _detect_state()
            if state != STATE_VTAM_USS:
                # We navigated away — try to get back
                _clear_input_field()
                _fast_key("string", "LOGOFF")
                _fast_key("enter", wait=True)
                time.sleep(0.5)

            # Send LOGON APPLID command
            _fast_key("clear")
            time.sleep(0.3)
            _fast_key("string", f"LOGON APPLID({applid})")
            _fast_key("enter", wait=True)
            time.sleep(1.0)

            screen_text = read_screen()
            status, message = self._classify_screen(screen_text)

            result = {
                "applid": applid,
                "status": status,
                "message": message,
                "screen_text": screen_text[:500],
            }
            self.results.append(result)

            if callback:
                callback(self.progress, self.total, result)

            # If valid, we may have entered the application — escape back
            if status == "valid":
                _fast_key("clear")
                time.sleep(0.3)
                _fast_key("string", "LOGOFF")
                _fast_key("enter", wait=True)
                time.sleep(0.5)
            else:
                _fast_key("clear")
                time.sleep(0.3)

        self.running = False

        # Return to TSO READY
        _go_to_tso_ready()

        return self.results

    def stop(self):
        self.running = False


# =============================================================================
# HiddenFieldDetector
# =============================================================================

class HiddenFieldDetector:
    """Detect hidden (non-display) fields in the 3270 screen buffer.

    Parses the raw ReadBuffer(Ascii) output to find Start Field (SF)
    and Start Field Extended (SFE) attribute bytes, then identifies
    fields whose attribute bits indicate non-display.

    Reimplements tn3270-hidden.nse logic.
    """

    # 3270 field attribute bit masks
    PROTECTED_BIT = 0x20
    NUMERIC_BIT = 0x10
    NON_DISPLAY_BITS = 0x0C  # bits 4-5 of the attribute byte
    NON_DISPLAY_VALUE = 0x0C  # both bits set = non-display
    INTENSIFIED_VALUE = 0x08  # bit 4 only = intensified
    MDT_BIT = 0x01

    def __init__(self):
        self.results: list[dict] = []

    def _check_connected(self) -> bool:
        return connection.connected and connection.emulator is not None

    def _parse_buffer_fields(self, raw_buffer) -> list[dict]:
        """Parse ReadBuffer(Ascii) output for field attributes.

        The raw buffer from x3270 ReadBuffer(Ascii) returns lines of
        space-separated tokens. Each token is either a displayable character
        or a field attribute marker like SF(c0) or SFE(...).
        """
        fields = []
        if not raw_buffer:
            return fields

        # Normalize buffer to string
        text = normalize_screen_text(raw_buffer)
        tokens = text.split()

        current_pos = 0
        current_field_start = None
        current_field_attr = None
        current_field_content = []

        for token in tokens:
            # Check for SF (Start Field) markers
            sf_match = re.match(r'SF\(([0-9a-fA-F]+)\)', token)
            sfe_match = re.match(r'SFE\(([^)]+)\)', token)

            if sf_match or sfe_match:
                # Save previous field if it was hidden
                if current_field_attr is not None:
                    fields.append({
                        "start_pos": current_field_start,
                        "attr": current_field_attr,
                        "content": "".join(current_field_content),
                    })

                if sf_match:
                    attr_byte = int(sf_match.group(1), 16)
                else:
                    # SFE has multiple pairs; first pair is usually the basic attribute
                    pairs = sfe_match.group(1).split(",")
                    try:
                        attr_byte = int(pairs[0].strip(), 16) if pairs else 0
                    except ValueError:
                        attr_byte = 0

                current_field_start = current_pos
                current_field_attr = attr_byte
                current_field_content = []
            else:
                # Regular character
                if len(token) == 2 and all(c in "0123456789abcdefABCDEF" for c in token):
                    # Hex-encoded character
                    try:
                        current_field_content.append(chr(int(token, 16)))
                    except ValueError:
                        current_field_content.append(".")
                else:
                    current_field_content.append(token)

            current_pos += 1

        # Save last field
        if current_field_attr is not None:
            fields.append({
                "start_pos": current_field_start,
                "attr": current_field_attr,
                "content": "".join(current_field_content),
            })

        return fields

    def _is_hidden(self, attr_byte: int) -> bool:
        """Check if field attribute indicates non-display."""
        display_bits = (attr_byte & self.NON_DISPLAY_BITS)
        return display_bits == self.NON_DISPLAY_VALUE

    def detect(self) -> list[dict]:
        """Scan current screen for hidden fields.

        Returns:
            List of {row, col, content, length, field_type} dicts.
        """
        if not self._check_connected():
            return [{"row": 0, "col": 0, "content": "",
                     "length": 0, "field_type": "error",
                     "message": "Not connected"}]

        self.results = []

        # Get raw buffer
        try:
            response = exec_emulator_command(b'ReadBuffer(Ascii)', timeout=6)
            raw_buffer = response.data if response else ""
        except Exception:
            return []

        # Also get printable screen for fallback analysis
        screen_text = read_screen()
        cols = connection.screen_cols or 80

        fields = self._parse_buffer_fields(raw_buffer)

        for field_info in fields:
            attr = field_info["attr"]
            content = field_info["content"].strip()

            if self._is_hidden(attr) and content:
                pos = field_info["start_pos"]
                row = (pos // cols) + 1
                col = (pos % cols) + 1

                is_protected = bool(attr & self.PROTECTED_BIT)
                field_type = "hidden_protected" if is_protected else "hidden_input"

                self.results.append({
                    "row": row,
                    "col": col,
                    "content": content,
                    "length": len(content),
                    "field_type": field_type,
                    "attr_hex": f"0x{attr:02x}",
                })

        # Fallback: scan screen text for password-like hidden patterns
        if not self.results:
            lines = screen_text.split("\n")
            for row_idx, line in enumerate(lines, 1):
                # Look for password fields that might be hidden
                pw_match = re.search(
                    r'(PASSWORD|PASSCODE|PASSWD)\s*[=:.]?\s*$',
                    line, re.IGNORECASE
                )
                if pw_match:
                    self.results.append({
                        "row": row_idx,
                        "col": pw_match.start() + 1,
                        "content": "(password field detected)",
                        "length": 0,
                        "field_type": "hidden_input_likely",
                        "attr_hex": "n/a",
                    })

        return self.results


# =============================================================================
# ScreenAnalyzer
# =============================================================================

class ScreenAnalyzer:
    """Regex-based screen content analyzer for security findings.

    Scans screen text for credentials, sensitive data, error codes,
    and access control indicators. Pure Python, no emulator needed.

    Reimplements SecurityScanner pattern detection from scanner.py.
    """

    PATTERNS = {
        "userid_field": {
            "patterns": [
                r'USERID\s*[=:.]?\s*(\S+)',
                r'USER\s*ID\s*[=:.]?\s*(\S+)',
                r'LOGON\s+(\S+)',
                r'TSS7102E\s+(\S+)',
                r'ICH70001I\s+(\S+)',
            ],
            "severity": "medium",
            "description": "Userid reference detected",
        },
        "password_field": {
            "patterns": [
                r'PASSWORD\s*[=:.]?\s*(\S+)',
                r'PASSCODE\s*[=:.]?\s*(\S+)',
                r'PASSWD\s*[=:.]?\s*(\S+)',
            ],
            "severity": "critical",
            "description": "Password or credential reference",
        },
        "ssn": {
            "patterns": [
                r'\b\d{3}-\d{2}-\d{4}\b',
            ],
            "severity": "critical",
            "description": "Possible SSN detected",
        },
        "credit_card": {
            "patterns": [
                r'\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b',
            ],
            "severity": "critical",
            "description": "Possible credit card number",
        },
        "api_key": {
            "patterns": [
                r'API[_-]?KEY\s*[=:.]?\s*(\S+)',
                r'TOKEN\s*[=:.]?\s*(\S+)',
                r'SECRET\s*[=:.]?\s*(\S+)',
            ],
            "severity": "high",
            "description": "API key or token reference",
        },
        "abend_code": {
            "patterns": [
                r'\bS[0-9A-F]{3}\b',
                r'\bU\d{4}\b',
                r'ABEND\s*=?\s*([A-Z0-9]+)',
            ],
            "severity": "medium",
            "description": "ABEND code detected",
        },
        "racf_message": {
            "patterns": [
                r'ICH\d{5}[A-Z]',
                r'IRR\d{5}[A-Z]',
                r'RACF\s+\S+',
            ],
            "severity": "medium",
            "description": "RACF security message",
        },
        "topsecret_message": {
            "patterns": [
                r'TSS\d{4}[A-Z]',
                r'TSS7\d{3}[A-Z]',
            ],
            "severity": "medium",
            "description": "Top Secret security message",
        },
        "access_denied": {
            "patterns": [
                r'NOT\s+AUTHORIZED',
                r'ACCESS\s+DENIED',
                r'VIOLATION',
                r'PERMISSION\s+DENIED',
                r'INSUFFICIENT\s+AUTH',
                r'SECURITY\s+FAILURE',
            ],
            "severity": "high",
            "description": "Access control indicator",
        },
        "privilege_indicator": {
            "patterns": [
                r'SPECIAL\s+ATTRIBUTE',
                r'OPERATIONS\s+ATTRIBUTE',
                r'AUDITOR\s+ATTRIBUTE',
                r'SYSTEM\s+HIGH',
                r'TRUSTED',
            ],
            "severity": "high",
            "description": "Privilege level indicator",
        },
    }

    def __init__(self):
        self.results: list[dict] = []

    def analyze(self, screen_text: str) -> list[dict]:
        """Analyze screen text for security-relevant patterns.

        Args:
            screen_text: The screen content to analyze.

        Returns:
            List of {finding_type, severity, description, location, match} dicts.
        """
        self.results = []

        lines = screen_text.split("\n")

        for finding_type, config in self.PATTERNS.items():
            severity = config["severity"]
            desc = config["description"]

            for pattern in config["patterns"]:
                for row_idx, line in enumerate(lines, 1):
                    for match in re.finditer(pattern, line, re.IGNORECASE):
                        self.results.append({
                            "finding_type": finding_type,
                            "severity": severity,
                            "description": desc,
                            "location": f"Row {row_idx}, Col {match.start() + 1}",
                            "match": match.group(0)[:80],
                        })

        # De-duplicate by (finding_type, match)
        seen = set()
        unique = []
        for r in self.results:
            key = (r["finding_type"], r["match"])
            if key not in seen:
                seen.add(key)
                unique.append(r)
        self.results = unique

        return self.results

    def analyze_current_screen(self) -> list[dict]:
        """Convenience: read current screen and analyze it."""
        screen_text = read_screen()
        return self.analyze(screen_text)


# =============================================================================
# ApplicationMapper
# =============================================================================

class ApplicationMapper:
    """Depth-first screen crawler that maps application structure.

    Starting from the current screen, tries menu options (1-9, A-Z)
    and records resulting screens. Uses PF3 to navigate back.
    Deduplicates screens by content hash.

    Reimplements AutomatedCrawler from scanner.py.
    """

    def __init__(self, max_depth: int = 3):
        self.max_depth = max_depth
        self.visited: set[str] = set()
        self.tree: list[dict] = []
        self.running = False
        self.stats = {
            "screens_found": 0,
            "unique_screens": 0,
            "max_depth_reached": 0,
        }

    def _check_connected(self) -> bool:
        return connection.connected and connection.emulator is not None

    def _hash_screen(self, text: str) -> str:
        """Generate content hash for deduplication."""
        # Strip variable content (timestamps, cursor artifacts)
        cleaned = re.sub(r'\d{2}[:/]\d{2}[:/]\d{2}', '', text)
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()
        return hashlib.md5(cleaned.encode()).hexdigest()[:12]

    def _extract_title(self, screen_text: str) -> str:
        """Try to extract a panel title from the screen."""
        lines = screen_text.split("\n")
        for line in lines[:5]:
            stripped = line.strip()
            if stripped and len(stripped) > 3 and not stripped.startswith("*"):
                # Remove leading/trailing dashes and spaces
                title = stripped.strip("-= ").strip()
                if title and len(title) < 60:
                    return title
        return "(untitled)"

    def _get_menu_options(self) -> list[str]:
        """Return list of menu options to try."""
        options = [str(i) for i in range(1, 10)]
        options.extend([chr(c) for c in range(ord('A'), ord('Z') + 1)])
        return options

    def map(self, callback=None) -> list[dict]:
        """Run the application mapper.

        Args:
            callback: Optional callable(stats_dict) for progress.

        Returns:
            List of screen node dicts forming a tree.
        """
        if not self._check_connected():
            return [{"screen_hash": "", "title": "Error",
                     "children": [], "fields": [],
                     "depth": 0, "error": "Not connected"}]

        self.visited = set()
        self.tree = []
        self.running = True
        self.stats = {"screens_found": 0, "unique_screens": 0,
                      "max_depth_reached": 0}

        root = self._crawl(depth=0, callback=callback)
        if root:
            self.tree = [root]

        self.running = False
        return self.tree

    def _crawl(self, depth: int, callback=None) -> Optional[dict]:
        """Recursive crawl from current screen."""
        if not self.running or depth > self.max_depth:
            return None

        screen_text = read_screen()
        screen_hash = self._hash_screen(screen_text)

        self.stats["screens_found"] += 1
        if depth > self.stats["max_depth_reached"]:
            self.stats["max_depth_reached"] = depth

        if screen_hash in self.visited:
            return None

        self.visited.add(screen_hash)
        self.stats["unique_screens"] += 1

        title = self._extract_title(screen_text)

        node = {
            "screen_hash": screen_hash,
            "title": title,
            "depth": depth,
            "screen_text": screen_text[:1000],
            "children": [],
        }

        if callback:
            callback(self.stats)

        if depth >= self.max_depth:
            return node

        # Try menu options
        for option in self._get_menu_options():
            if not self.running:
                break

            _fast_key("string", option)
            _fast_key("enter", wait=True)
            time.sleep(0.8)

            new_screen = read_screen()
            new_hash = self._hash_screen(new_screen)

            if new_hash != screen_hash and new_hash not in self.visited:
                child = self._crawl(depth + 1, callback)
                if child:
                    child["option"] = option
                    node["children"].append(child)

            # Navigate back
            _fast_key("pf", "3", wait=True)
            time.sleep(0.5)

            # Verify we're back
            back_screen = read_screen()
            back_hash = self._hash_screen(back_screen)
            if back_hash != screen_hash:
                # Try clear as fallback
                _fast_key("clear")
                time.sleep(0.3)
                break

        return node

    def stop(self):
        self.running = False


# =============================================================================
# Report Generator
# =============================================================================

def generate_report(enumerate_results: list[dict],
                    hidden_fields: list[dict],
                    screen_findings: list[dict],
                    map_tree: list[dict],
                    fmt: str = "json") -> str:
    """Generate an assessment report in the requested format.

    Args:
        enumerate_results: Combined results from TSO/CICS/VTAM enumeration.
        hidden_fields: Results from HiddenFieldDetector.
        screen_findings: Results from ScreenAnalyzer.
        map_tree: Results from ApplicationMapper.
        fmt: Output format -- "json", "html", or "markdown".

    Returns:
        Report string in requested format.
    """
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Count severity levels across all findings
    severity_counts = {"critical": 0, "high": 0, "medium": 0, "low": 0, "info": 0}
    for f in screen_findings:
        sev = f.get("severity", "info")
        severity_counts[sev] = severity_counts.get(sev, 0) + 1

    # Count enumeration stats
    valid_count = sum(1 for r in enumerate_results
                      if r.get("status") in ("valid", "auth_required", "locked"))
    invalid_count = sum(1 for r in enumerate_results
                        if r.get("status") == "invalid")

    report_data = {
        "title": "TN3270 Recon Assessment Report",
        "timestamp": timestamp,
        "summary": {
            "total_enumerated": len(enumerate_results),
            "valid_found": valid_count,
            "invalid": invalid_count,
            "hidden_fields": len(hidden_fields),
            "screen_findings": len(screen_findings),
            "severity": severity_counts,
            "screens_mapped": sum(1 for _ in _flatten_tree(map_tree)),
        },
        "enumeration": enumerate_results,
        "hidden_fields": hidden_fields,
        "screen_findings": screen_findings,
        "application_map": map_tree,
    }

    if fmt == "json":
        import json
        return json.dumps(report_data, indent=2, default=str)

    elif fmt == "markdown":
        return _render_markdown(report_data)

    elif fmt == "html":
        return _render_html(report_data)

    elif fmt == "csv":
        return _render_csv(report_data)

    return ""


def _render_csv(data: dict) -> str:
    """Render report as CSV for spreadsheet analysis."""
    import csv
    import io

    output = io.StringIO()

    # Summary section
    output.write("# SUMMARY\n")
    output.write("Metric,Value\n")
    s = data["summary"]
    output.write(f"Timestamp,{data['timestamp']}\n")
    output.write(f"Targets Enumerated,{s['total_enumerated']}\n")
    output.write(f"Valid Found,{s['valid_found']}\n")
    output.write(f"Invalid,{s['invalid']}\n")
    output.write(f"Hidden Fields,{s['hidden_fields']}\n")
    output.write(f"Screen Findings,{s['screen_findings']}\n")
    output.write(f"Screens Mapped,{s['screens_mapped']}\n")
    for sev, count in s["severity"].items():
        output.write(f"Severity {sev.upper()},{count}\n")
    output.write("\n")

    # Enumeration results
    if data["enumeration"]:
        output.write("# ENUMERATION RESULTS\n")
        output.write("Target,Status,Message\n")
        for r in data["enumeration"]:
            name = r.get("userid") or r.get("transaction_id") or r.get("applid") or r.get("id", "?")
            msg = r.get("message", "").replace(",", ";").replace("\n", " ")[:100]
            output.write(f"{name},{r.get('status', 'unknown')},{msg}\n")
        output.write("\n")

    # Hidden fields
    if data["hidden_fields"]:
        output.write("# HIDDEN FIELDS\n")
        output.write("Row,Col,Type,Content\n")
        for f in data["hidden_fields"]:
            content = f.get("content", "").replace(",", ";").replace("\n", " ")[:50]
            output.write(f"{f.get('row', 0)},{f.get('col', 0)},{f.get('field_type', 'unknown')},{content}\n")
        output.write("\n")

    # Screen findings
    if data["screen_findings"]:
        output.write("# SCREEN FINDINGS\n")
        output.write("Severity,Type,Description,Match\n")
        for f in data["screen_findings"]:
            match = f.get("match", "").replace(",", ";").replace("\n", " ")[:50]
            output.write(f"{f.get('severity', 'info')},{f.get('finding_type', 'unknown')},{f.get('description', '')},{match}\n")

    return output.getvalue()


def _flatten_tree(tree: list[dict]) -> list[dict]:
    """Flatten tree nodes into a list."""
    for node in tree:
        yield node
        yield from _flatten_tree(node.get("children", []))


def _render_markdown(data: dict) -> str:
    s = data["summary"]
    lines = [
        f"# {data['title']}",
        f"**Generated:** {data['timestamp']}",
        "",
        "## Summary",
        f"- Targets enumerated: {s['total_enumerated']}",
        f"- Valid entries found: {s['valid_found']}",
        f"- Invalid: {s['invalid']}",
        f"- Hidden fields: {s['hidden_fields']}",
        f"- Screen findings: {s['screen_findings']}",
        f"- Screens mapped: {s['screens_mapped']}",
        "",
        "### Severity Breakdown",
    ]
    for sev, count in s["severity"].items():
        if count > 0:
            lines.append(f"- **{sev.upper()}**: {count}")

    # Enumeration results
    if data["enumeration"]:
        lines.append("")
        lines.append("## Enumeration Results")
        lines.append("")
        lines.append("| Target | Status | Message |")
        lines.append("|--------|--------|---------|")
        for r in data["enumeration"]:
            name = r.get("userid") or r.get("transaction_id") or r.get("applid", "?")
            lines.append(f"| {name} | {r['status']} | {r['message']} |")

    # Hidden fields
    if data["hidden_fields"]:
        lines.append("")
        lines.append("## Hidden Fields")
        lines.append("")
        lines.append("| Row | Col | Type | Content |")
        lines.append("|-----|-----|------|---------|")
        for f in data["hidden_fields"]:
            lines.append(
                f"| {f['row']} | {f['col']} | {f['field_type']} | `{f['content'][:40]}` |"
            )

    # Screen findings
    if data["screen_findings"]:
        lines.append("")
        lines.append("## Screen Findings")
        lines.append("")
        for f in data["screen_findings"]:
            sev = f["severity"].upper()
            lines.append(f"- **[{sev}]** {f['description']}: `{f['match']}` at {f['location']}")

    lines.append("")
    lines.append("---")
    lines.append("*Generated by Mainframe AI Assistant - Recon Engine*")
    return "\n".join(lines)


def _render_html(data: dict) -> str:
    s = data["summary"]
    sev_html = ""
    for sev, count in s["severity"].items():
        if count > 0:
            color = {"critical": "#f85149", "high": "#ff6b6b",
                     "medium": "#ffb020", "low": "#63a7ff",
                     "info": "#888"}.get(sev, "#888")
            sev_html += (
                f'<span style="background:{color};color:#000;padding:2px 8px;'
                f'margin-right:6px;font-weight:700;font-size:12px;">'
                f'{sev.upper()}: {count}</span>'
            )

    enum_rows = ""
    for r in data.get("enumeration", []):
        name = r.get("userid") or r.get("transaction_id") or r.get("applid", "?")
        status = r["status"]
        badge_color = {
            "valid": "#39d98a", "auth_required": "#ffb020",
            "locked": "#ff6b6b", "invalid": "#555",
            "error": "#f85149", "unknown": "#888",
            "valid_blank": "#39d98a",
        }.get(status, "#888")
        enum_rows += (
            f'<tr><td>{name}</td>'
            f'<td><span style="background:{badge_color};color:#000;'
            f'padding:2px 8px;font-size:12px;">{status}</span></td>'
            f'<td>{r["message"]}</td></tr>\n'
        )

    hidden_rows = ""
    for f in data.get("hidden_fields", []):
        hidden_rows += (
            f'<tr><td>{f["row"]}</td><td>{f["col"]}</td>'
            f'<td>{f["field_type"]}</td>'
            f'<td><code>{f["content"][:60]}</code></td></tr>\n'
        )

    findings_html = ""
    for f in data.get("screen_findings", []):
        sev = f["severity"]
        color = {"critical": "#f85149", "high": "#ff6b6b",
                 "medium": "#ffb020", "low": "#63a7ff",
                 "info": "#888"}.get(sev, "#888")
        findings_html += (
            f'<div style="border-left:3px solid {color};padding:8px 12px;'
            f'margin-bottom:8px;background:rgba(255,255,255,0.03);">'
            f'<strong style="color:{color};">[{sev.upper()}]</strong> '
            f'{f["description"]}: <code>{f["match"]}</code>'
            f'<br><small>{f["location"]}</small></div>\n'
        )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>{data['title']}</title>
<style>
body {{ font-family: 'IBM Plex Mono', monospace; background: #0b0f14; color: #e8edf4; padding: 2rem; }}
h1 {{ color: #63a7ff; border-bottom: 1px solid #333; padding-bottom: 1rem; }}
h2 {{ color: #e8edf4; margin-top: 2rem; }}
table {{ border-collapse: collapse; width: 100%; margin-top: 1rem; }}
th, td {{ border: 1px solid #333; padding: 8px 12px; text-align: left; font-size: 13px; }}
th {{ background: #1a2030; color: #63a7ff; }}
tr:nth-child(even) {{ background: rgba(255,255,255,0.02); }}
code {{ background: rgba(255,255,255,0.06); padding: 2px 6px; }}
.summary-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 1rem; margin: 1rem 0; }}
.summary-card {{ background: #141a22; border: 1px solid #333; padding: 1rem; text-align: center; }}
.summary-card .num {{ font-size: 2rem; font-weight: 700; color: #63a7ff; }}
.summary-card .label {{ font-size: 0.8rem; color: #888; margin-top: 4px; }}
</style>
</head>
<body>
<h1>{data['title']}</h1>
<p>Generated: {data['timestamp']}</p>

<div class="summary-grid">
<div class="summary-card"><div class="num">{s['total_enumerated']}</div><div class="label">Targets Tested</div></div>
<div class="summary-card"><div class="num" style="color:#39d98a;">{s['valid_found']}</div><div class="label">Valid Found</div></div>
<div class="summary-card"><div class="num">{s['hidden_fields']}</div><div class="label">Hidden Fields</div></div>
<div class="summary-card"><div class="num">{s['screen_findings']}</div><div class="label">Findings</div></div>
<div class="summary-card"><div class="num">{s['screens_mapped']}</div><div class="label">Screens Mapped</div></div>
</div>

<div style="margin:1rem 0;">{sev_html}</div>

<h2>Enumeration Results</h2>
<table>
<thead><tr><th>Target</th><th>Status</th><th>Message</th></tr></thead>
<tbody>{enum_rows}</tbody>
</table>

<h2>Hidden Fields</h2>
<table>
<thead><tr><th>Row</th><th>Col</th><th>Type</th><th>Content</th></tr></thead>
<tbody>{hidden_rows}</tbody>
</table>

<h2>Screen Findings</h2>
{findings_html}

<hr style="border-color:#333;margin-top:2rem;">
<p style="color:#555;font-size:12px;">Generated by Mainframe AI Assistant - Recon Engine</p>
</body>
</html>"""


# =============================================================================
# SystemEnumerator — Live TSO-based system enumeration
# Adapted from mainframed/pentesting/ENUM_REFACTORED
# =============================================================================

class SystemEnumerator:
    """Run live TSO commands on a connected mainframe to enumerate
    system configuration, RACF settings, APF libraries, datasets,
    and user authority.

    This is the core enumeration engine. It:
      1. Detects the current terminal state
      2. Logs into TSO automatically if not already logged in
      3. Verifies READY prompt before EVERY command
      4. Handles multi-screen output (*** MORE paging)
      5. Recovers from mid-command errors (REENTER, timeouts)
      6. Returns structured results with severity-tagged findings
    """

    # Commands to run and their categories
    # Mirrors mainframed/Enumeration ENUM args: JOB, WHO, VERS, SEC, APF, PATH, TSOT, TSTA, CAT
    ENUM_COMMANDS = [
        # ── VERS ── Operating system / JES / TSO version info
        {
            "id": "vers_status",
            "label": "VERS: System Status",
            "command": "STATUS",
            "description": "Current job name, TSO session info (ENUM VERS / JOB equivalent)",
            "finding_patterns": {
                "critical": [],
                "warning": [],
                "info": ["JOB", "TSO", "LOGON", "USER"],
            },
        },
        {
            "id": "vers_time",
            "label": "VERS: System Time",
            "command": "TIME",
            "description": "CPU time, elapsed time, LPAR/system clock",
            "finding_patterns": {
                "critical": [],
                "warning": [],
                "info": ["TIME", "CPU", "SERVICE"],
            },
        },
        # ── SEC ── Security manager (RACF on MVS 3.8j TK5)
        {
            "id": "sec_identity",
            "label": "SEC: User Profile (LU)",
            "command": "LU {userid}",
            "description": "RACF LISTUSER — attributes, groups, special authority (ENUM SEC)",
            "finding_patterns": {
                "critical": ["SPECIAL", "OPERATIONS", "AUDITOR"],
                "warning": ["REVOKED", "NO-PASSWORD", "EXPIRED"],
                "info": ["DEFAULT-GROUP", "PASSDATE", "PASS-INTERVAL", "GROUP"],
            },
        },
        {
            "id": "sec_racf_dataset",
            "label": "SEC: RACF Dataset",
            "command": "LISTDS 'SYS1.RACF'",
            "description": "Check RACF primary database dataset — UACC exposure is critical",
            "finding_patterns": {
                "critical": ["NOT IN CATALOG", "NOT FOUND"],
                "warning": ["WARNING"],
                "info": ["DSORG", "RECFM", "LRECL", "BLKSIZE", "VOLUMES"],
            },
        },
        # ── WHO ── Logged-on users (LISTBC is the TSO equivalent on MVS 3.8j)
        {
            "id": "who_listbc",
            "label": "WHO: Broadcast Messages / Active Users",
            "command": "LISTBC",
            "description": "LISTBC shows pending TSO broadcast messages — confirms active TSO sessions (ENUM WHO equivalent)",
            "finding_patterns": {
                "critical": [],
                "warning": [],
                "info": ["MESSAGE", "BROADCAST", "USER", "NOTIFY"],
            },
        },
        # ── PATH ── Dataset concatenations (SYSPROC / SYSEXEC = executable search path)
        {
            "id": "path_listalc",
            "label": "PATH: DD Concatenations (LISTALC)",
            "command": "LISTALC STATUS",
            "description": "All allocated DDNAMEs — SYSPROC/SYSEXEC are the TSO executable path (ENUM PATH)",
            "finding_patterns": {
                "critical": ["SYS1.CMDLIB", "SYS1.LINKLIB"],
                "warning": ["USER.", "HERC"],
                "info": ["STEPLIB", "SYSPROC", "SYSEXEC", "ISPLLIB", "SYSLIB"],
            },
        },
        # ── APF ── APF-authorized libraries
        {
            "id": "apf_linklib",
            "label": "APF: SYS1.LINKLIB",
            "command": "LISTDS 'SYS1.LINKLIB' MEMBERS",
            "description": "Primary APF-authorized load library — members are privileged programs (ENUM APF)",
            "finding_patterns": {
                "critical": ["NOT IN CATALOG", "NOT FOUND", "VSAM"],
                "warning": ["WARNING"],
                "info": ["DSORG", "RECFM", "LRECL", "BLKSIZE", "VOLUMES", "MEMBERS"],
            },
        },
        {
            "id": "apf_svclib",
            "label": "APF: SYS1.SVCLIB",
            "command": "LISTDS 'SYS1.SVCLIB'",
            "description": "SVC library — unauthorized SVC replacement = privilege escalation path",
            "finding_patterns": {
                "critical": ["NOT IN CATALOG", "NOT FOUND", "VSAM"],
                "warning": ["WARNING"],
                "info": ["DSORG", "RECFM", "LRECL", "BLKSIZE", "VOLUMES"],
            },
        },
        {
            "id": "apf_cmdlib",
            "label": "APF: SYS1.CMDLIB",
            "command": "LISTDS 'SYS1.CMDLIB'",
            "description": "APF-authorized TSO command library — writable = inject privileged commands",
            "finding_patterns": {
                "critical": ["NOT IN CATALOG", "NOT FOUND", "VSAM"],
                "warning": ["WARNING"],
                "info": ["DSORG", "RECFM", "LRECL", "BLKSIZE", "VOLUMES"],
            },
        },
        {
            "id": "apf_sysc_linklib",
            "label": "APF: SYSC.LINKLIB",
            "command": "LISTDS 'SYSC.LINKLIB'",
            "description": "System catalog link library — alternate APF lib on some TK5 configs",
            "finding_patterns": {
                "critical": ["NOT IN CATALOG", "NOT FOUND", "VSAM"],
                "warning": ["WARNING"],
                "info": ["DSORG", "RECFM", "LRECL", "BLKSIZE", "VOLUMES"],
            },
        },
        {
            "id": "apf_nucleus",
            "label": "APF: SYS1.NUCLEUS",
            "command": "LISTDS 'SYS1.NUCLEUS'",
            "description": "MVS nucleus — contains IPL text and supervisor modules",
            "finding_patterns": {
                "critical": ["NOT IN CATALOG", "NOT FOUND"],
                "warning": ["WARNING"],
                "info": ["DSORG", "RECFM", "BLKSIZE", "VOLUMES"],
            },
        },
        # ── TSOT ── TSO auth tables (IKJEFTE2=AUTHCMD, IKJEFTE8=AUTHPGM)
        {
            "id": "tsot_authcmd",
            "label": "TSOT: TSO Auth Cmd Table (IKJEFTE2)",
            "command": "LISTDS 'SYS1.PARMLIB' MEMBERS",
            "description": "PARMLIB members — IKJTSO00/IKJTSO1x define AUTHCMD/AUTHPGM tables (ENUM TSOT)",
            "finding_patterns": {
                "critical": ["IEAAPF"],
                "warning": ["IKJTSO", "SMFPRM", "COMMND"],
                "info": ["IEASYS", "MEMBERS", "LNKAUTH", "PAGESCIN"],
            },
        },
        {
            "id": "tsot_authpgm",
            "label": "TSOT: TSO Authorized Programs",
            "command": "LISTDS 'SYS1.UADS'",
            "description": "User Attribute Dataset — TSO user definitions, authorized programs",
            "finding_patterns": {
                "critical": ["NOT IN CATALOG", "NOT FOUND"],
                "warning": ["WARNING"],
                "info": ["DSORG", "RECFM", "BLKSIZE", "VOLUMES"],
            },
        },
        # ── TSTA ── TESTAUTH authorization check
        {
            "id": "tsta_testauth",
            "label": "TSTA: TESTAUTH Check",
            "command": "TESTAUTH EXEC",
            "description": "Test if current user can run TESTAUTH — confirms APF-auth status (ENUM TSTA)",
            "finding_patterns": {
                "critical": ["AUTHORIZED", "IKJ56711I"],
                "warning": ["IKJ56712I"],
                "info": ["TESTAUTH", "NOT AUTHORIZED"],
            },
        },
        # ── CAT ── Master catalog
        {
            "id": "cat_listcat",
            "label": "CAT: Master Catalog",
            "command": "LISTCAT",
            "description": "Master catalog root — alias and dataset namespace (ENUM CAT)",
            "finding_patterns": {
                "critical": [],
                "warning": [],
                "info": ["IN-CAT", "NONVSAM", "ALIAS", "CLUSTER", "USERCATALOG"],
            },
        },
        {
            "id": "cat_user",
            "label": "CAT: User Datasets",
            "command": "LISTCAT ENTRIES('{userid}.*')",
            "description": "All datasets owned by this userid — reveals accessible data",
            "finding_patterns": {
                "critical": [],
                "warning": [],
                "info": ["NONVSAM", "ALIAS", "IN-CAT"],
            },
        },
        # ── SVC ── SVC table (no direct TSO cmd on MVS 3.8j — check auth programs instead)
        {
            "id": "svc_proclib",
            "label": "SVC: SYS1.PROCLIB Members",
            "command": "LISTDS 'SYS1.PROCLIB' MEMBERS",
            "description": "Started-task procedures — JES, VTAM, RACF started tasks (ENUM SVC context)",
            "finding_patterns": {
                "critical": [],
                "warning": ["RACF", "BACKDOOR"],
                "info": ["MEMBERS", "JES", "TSO", "VTAM", "NET", "TCPIP"],
            },
        },
        # ── Extra APF-adjacent datasets worth checking ──
        {
            "id": "apf_lpalib",
            "label": "APF: SYS1.LPALIB",
            "command": "LISTDS 'SYS1.LPALIB'",
            "description": "Link Pack Area library — modules loaded at IPL into shared memory",
            "finding_patterns": {
                "critical": ["NOT IN CATALOG", "NOT FOUND"],
                "warning": ["WARNING"],
                "info": ["DSORG", "RECFM", "BLKSIZE", "VOLUMES"],
            },
        },
        {
            "id": "apf_linklist",
            "label": "APF: SYS1.LNKLIB",
            "command": "LISTDS 'SYS1.LNKLIB'",
            "description": "Linklist library — searched for all programs without explicit DD",
            "finding_patterns": {
                "critical": ["NOT IN CATALOG", "NOT FOUND"],
                "warning": ["WARNING"],
                "info": ["DSORG", "RECFM", "BLKSIZE", "VOLUMES"],
            },
        },
    ]

    def __init__(self, userid: str = "HERC01", password: str = "CUL8TR",
                 commands: Optional[List[str]] = None):
        self.userid = userid
        self.password = password
        self.selected_commands = commands  # None = all
        self.results: list[dict] = []
        self.running = False
        self.progress = 0
        self.total = 0

    def _check_connected(self) -> bool:
        return connection.connected and connection.emulator is not None

    def _ensure_ready(self) -> bool:
        """Verify we are at the TSO READY prompt. If not, navigate there.

        Called before EVERY command to guarantee correct state.
        Handles: not logged in, ISPF, MORE prompts, REENTER, unknown states.
        Returns True if at READY, False if recovery failed.
        """
        _clear_screen_state()
        state = _detect_state()

        if state == STATE_TSO_READY:
            return True

        _log.info("Not at TSO READY (state=%s), navigating...", state)
        return _go_to_tso_ready(self.userid, self.password)

    def _run_tso_command(self, command: str) -> str:
        """Send a TSO command and capture multi-screen output.

        Handles:
          - Clearing pending input before sending
          - Multi-screen *** MORE paging (up to 20 pages)
          - IKJ56703A REENTER prompts (invalid command recovery)
          - Deduplicating repeated screen reads
        """
        # Clear input field before typing command
        _clear_input_field()

        # Send the command
        _fast_key("string", command)
        _fast_key("enter", wait=True)
        time.sleep(0.5)

        # Capture first screen
        first_screen = read_screen()
        output_parts = [first_screen]
        seen_hashes = {hash(first_screen)}

        # Check for REENTER prompt (command was rejected)
        upper = first_screen.upper()
        if "IKJ56703A" in upper:
            _log.warning("Command rejected (REENTER): %s", command)
            # Clear the error and return what we got
            _fast_key("pa", "1", wait=True)
            time.sleep(0.3)
            _fast_key("clear")
            time.sleep(0.3)
            return first_screen

        # Page through MORE indicators — up to 20 pages for large outputs
        # (LISTDS MEMBERS, LISTCAT, etc. can produce many screens)
        for page in range(20):
            screen = read_screen()
            screen_upper = screen.upper()

            # Check for *** (MORE indicator) — common on TK5
            has_more = "***" in screen and "READY" not in screen_upper
            if not has_more:
                break

            _fast_key("enter", wait=True)
            time.sleep(0.8)

            new_screen = read_screen()
            h = hash(new_screen)
            if h not in seen_hashes:
                seen_hashes.add(h)
                output_parts.append(new_screen)

        # Final screen may contain READY + last output lines
        final = read_screen()
        h = hash(final)
        if h not in seen_hashes:
            output_parts.append(final)

        return "\n".join(output_parts)

    def _analyze_output(self, output: str, patterns: dict) -> list[dict]:
        """Analyze command output for security-relevant patterns."""
        findings = []
        upper = output.upper()

        for severity, pattern_list in patterns.items():
            for pattern in pattern_list:
                if pattern in upper:
                    for line in output.splitlines():
                        if pattern in line.upper():
                            findings.append({
                                "severity": severity,
                                "pattern": pattern,
                                "line": line.strip()[:200],
                            })
                            break

        return findings

    def enumerate(self, callback=None) -> list[dict]:
        """Run all selected enumeration commands on the live system.

        For each command:
          1. Verify TSO READY (auto-login if needed)
          2. Send command and capture output
          3. Analyze output for security findings
          4. If command failed, record error and continue

        Returns list of {id, label, command, output, findings, description} dicts.
        """

        if not self._check_connected():
            return [{"id": "error", "label": "Error", "command": "",
                     "output": "Not connected to mainframe. Use the Connect "
                               "button to connect first.",
                     "findings": [], "description": ""}]

        # Verify connection is healthy before starting
        if not _ensure_connection():
            return [{"id": "error", "label": "Error", "command": "",
                     "output": "Connection to mainframe is not responsive. "
                               "Try reconnecting.",
                     "findings": [], "description": ""}]

        # Reset terminal to clean state before starting
        _reset_terminal()

        # Initial login — navigate to TSO READY
        if not self._ensure_ready():
            return [{"id": "error", "label": "Error", "command": "",
                     "output": "Could not log into TSO. Verify the mainframe "
                               "is running and credentials are correct.\n\n"
                               f"Userid: {self.userid}\n"
                               f"Terminal state: {_detect_state()}",
                     "findings": [], "description": ""}]


        commands = self.ENUM_COMMANDS
        if self.selected_commands:
            commands = [c for c in commands if c["id"] in self.selected_commands]


        self.results = []
        self.running = True
        self.progress = 0
        self.total = len(commands)
        consecutive_failures = 0

        for i, cmd_def in enumerate(commands):
            if not self.running:
                break

            self.progress = i + 1

            # === KEY: verify READY before every command ===
            if not self._ensure_ready():
                _log.error("Lost TSO session before command %s", cmd_def["id"])
                consecutive_failures += 1
                result = {
                    "id": cmd_def["id"],
                    "label": cmd_def["label"],
                    "command": cmd_def["command"],
                    "description": cmd_def["description"],
                    "output": f"[ERROR] Could not reach TSO READY prompt. "
                              f"State: {_detect_state()}",
                    "findings": [],
                }
                self.results.append(result)
                if consecutive_failures >= 3:
                    _log.error("3 consecutive failures — aborting enumeration")
                    break
                continue

            consecutive_failures = 0

            # Substitute userid if needed
            command = cmd_def["command"].replace("{userid}", self.userid)

            # Run the command
            _log.info("Running: %s", command)
            try:
                output = self._run_tso_command(command)
            except Exception as e:
                _log.exception("Exception running %s", command)
                output = f"[ERROR] Exception: {e}"

            # Analyze for findings
            findings = self._analyze_output(output, cmd_def["finding_patterns"])

            result = {
                "id": cmd_def["id"],
                "label": cmd_def["label"],
                "command": command,
                "description": cmd_def["description"],
                "output": output[:5000],
                "findings": findings,
            }
            self.results.append(result)

            if callback:
                callback(self.progress, self.total, result)

        self.running = False
        return self.results

    def stop(self):
        self.running = False
