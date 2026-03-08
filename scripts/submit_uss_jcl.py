#!/usr/bin/env python3
"""
Submit IBMAI.jcl to live MVS TK5 using py3270 directly.

Strategy:
  1. Connect fresh via py3270 (bypasses web app cursor state issues)
  2. Logon as HERC01 / CUL8TR
  3. Use TSO SUBMIT * to pipe JCL inline (works in TK5)
  4. Activate USS table via VTAM operator command

Usage:
  .venv/bin/python scripts/submit_uss_jcl.py
"""

import sys
import time
from pathlib import Path

try:
    from py3270 import Emulator
except ImportError:
    print("[!] py3270 not installed. Run: pip install py3270")
    sys.exit(1)

JCL_PATH = Path(__file__).parent.parent / "jcl" / "IBMAI.jcl"
HOST = "localhost"
PORT = 3270
USER = "HERC01"
PASS = "CUL8TR"


def wait_for_screen(em, text, timeout=60, interval=1):
    start = time.time()
    while time.time() - start < timeout:
        try:
            em.exec_command(b"Wait(1,Output)")
        except Exception:
            pass
        try:
            screen = em.exec_command(b"Ascii()").data
            full = " ".join(
                line.decode("utf-8", errors="ignore") if isinstance(line, bytes) else line
                for line in screen
            )
            if text.upper() in full.upper():
                return True
        except Exception:
            pass
        time.sleep(interval)
    return False


def get_screen_text(em):
    try:
        result = em.exec_command(b"Ascii()")
        lines = result.data
        return "\n".join(
            line.decode("utf-8", errors="ignore") if isinstance(line, bytes) else line
            for line in lines
        )
    except Exception:
        return ""


def send(em, text):
    em.exec_command(f'String("{text}")'.encode())
    time.sleep(0.2)


def enter(em):
    em.exec_command(b"Enter()")
    time.sleep(0.5)


def pf(em, n):
    em.exec_command(f"PF({n})".encode())
    time.sleep(0.5)


def main():
    print("=" * 60)
    print("  IBM AI USS Screen — JCL Submitter")
    print("=" * 60)

    if not JCL_PATH.exists():
        print(f"[!] JCL not found: {JCL_PATH}")
        sys.exit(1)

    jcl_lines = JCL_PATH.read_text().splitlines()
    print(f"[*] Loaded {len(jcl_lines)} lines from {JCL_PATH.name}")

    print(f"[*] Connecting to {HOST}:{PORT}...")
    em = Emulator(visible=False, args=["-model", "3279-2"])

    try:
        em.connect(f"{HOST}:{PORT}")
        time.sleep(3)

        # ── Wait for VTAM logon screen ──────────────────────────
        print("[*] Waiting for VTAM logon screen...")
        if not wait_for_screen(em, "Logon", timeout=30):
            print("[!] Timeout waiting for VTAM screen")
            print(get_screen_text(em))
            sys.exit(1)

        print("[+] At VTAM screen")
        print(get_screen_text(em)[:300])

        # ── Logon ───────────────────────────────────────────────
        print(f"[*] Logging in as {USER}...")
        send(em, USER)
        enter(em)
        time.sleep(3)

        screen = get_screen_text(em)
        print(f"[*] Screen after logon:\n{screen[:300]}")

        # Password prompt (screen goes blank — password field is hidden)
        if "PASSWORD" in screen.upper() or len(screen.strip()) < 10:
            print("[*] Sending password...")
            send(em, PASS)
            enter(em)
            time.sleep(4)

        # Press through broadcast / ICH70001I messages
        print("[*] Pressing through broadcast messages...")
        for i in range(8):
            screen = get_screen_text(em)
            if "READY" in screen.upper():
                break
            enter(em)
            time.sleep(1.5)

        screen = get_screen_text(em)
        if "READY" not in screen.upper():
            print(f"[!] Could not reach TSO READY. Screen:\n{screen}")
            sys.exit(1)

        print("[+] At TSO READY prompt")

        # ── Submit JCL inline via TSO SUBMIT * ──────────────────
        # TSO SUBMIT * reads from the terminal until a /* delimiter
        # We type each line then hit enter, then /* + enter to end
        print(f"[*] Submitting JCL ({len(jcl_lines)} lines)...")
        send(em, "SUBMIT *")
        enter(em)
        time.sleep(2)

        screen = get_screen_text(em)
        print(f"[*] After SUBMIT *:\n{screen[:200]}")

        # Type each JCL line
        for i, line in enumerate(jcl_lines, 1):
            # Truncate to 72 chars (JCL standard), skip pure comment lines
            safe = line[:72].rstrip()
            send(em, safe)
            enter(em)
            time.sleep(0.1)
            if i % 50 == 0:
                print(f"    ... {i}/{len(jcl_lines)} lines")

        # End of inline JCL
        send(em, "/*")
        enter(em)
        time.sleep(5)

        screen = get_screen_text(em)
        print(f"[*] After submit:\n{screen[:400]}")

        if "JOB" in screen.upper() or "SUBMITTED" in screen.upper():
            print("[+] JCL submitted!")
            for word in screen.split():
                if word.startswith("JOB") and len(word) > 5:
                    print(f"[+] Job: {word}")
        else:
            print("[!] Submit may have failed — check output above")

        # ── Wait for job completion ──────────────────────────────
        print("[*] Waiting up to 120s for job to complete...")
        if wait_for_screen(em, "READY", timeout=120):
            print("[+] Job done — back at READY")
        else:
            print("[!] Timeout — job may still be running")

        screen = get_screen_text(em)
        print(f"[*] Final screen:\n{screen[:400]}")

        # ── Activate USS table ───────────────────────────────────
        print("[*] Activating USS table via VTAM operator command...")
        send(em, "OPERATOR 'V NET,ACT,ID=USSN'")
        enter(em)
        time.sleep(3)
        screen = get_screen_text(em)
        print(f"[*] Operator response:\n{screen[:300]}")

    finally:
        try:
            em.terminate()
        except Exception:
            pass

    print()
    print("=" * 60)
    print("  DONE!")
    print("  New USS logon screen should be active.")
    print("  To verify: disconnect and reconnect to port 3270")
    print("=" * 60)


if __name__ == "__main__":
    main()
