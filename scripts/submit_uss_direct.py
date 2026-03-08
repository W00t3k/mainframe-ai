#!/usr/bin/env python3
"""
Submit IBMAI.jcl directly via s3270 subprocess using HERC02.
Bypasses the web app entirely to avoid HERC01 session conflict.
"""

import sys
import time
import subprocess
import threading
from pathlib import Path

JCL_PATH = Path(__file__).parent.parent / "jcl" / "IBMAI.jcl"
S3270 = "/opt/homebrew/bin/s3270"
HOST = "localhost:3270"
USER = "HERC02"
PASS = "CUL8TR"


class S3270Session:
    def __init__(self):
        self.proc = subprocess.Popen(
            [S3270, "-xrm", "s3270.unlockDelay: False", HOST],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )
        self._lock = threading.Lock()

    def cmd(self, command, wait=0.5):
        with self._lock:
            self.proc.stdin.write(command + "\n")
            self.proc.stdin.flush()
            time.sleep(wait)
            return self._read_response()

    def _read_response(self):
        lines = []
        self.proc.stdin.write("Query()\n")
        self.proc.stdin.flush()
        # Read until we get ok or error
        while True:
            line = self.proc.stdout.readline()
            if not line:
                break
            line = line.rstrip()
            lines.append(line)
            if line in ("ok", "error"):
                break
        return lines

    def ascii(self):
        """Get current screen as text."""
        with self._lock:
            self.proc.stdin.write("Ascii()\n")
            self.proc.stdin.flush()
            lines = []
            while True:
                line = self.proc.stdout.readline()
                if not line:
                    break
                line = line.rstrip()
                if line in ("ok", "error"):
                    break
                if line.startswith("data:"):
                    lines.append(line[5:])
            return "\n".join(lines)

    def string(self, text):
        return self.cmd(f'String("{text}")', wait=0.3)

    def enter(self, wait=1.0):
        return self.cmd("Enter()", wait=wait)

    def pf(self, n, wait=0.5):
        return self.cmd(f"PF({n})", wait=wait)

    def wait_output(self, secs=3):
        return self.cmd(f"Wait({secs},Output)", wait=0.2)

    def terminate(self):
        try:
            self.proc.stdin.write("Quit()\n")
            self.proc.stdin.flush()
        except Exception:
            pass
        try:
            self.proc.terminate()
        except Exception:
            pass

    def wait_for(self, text, timeout=60):
        start = time.time()
        while time.time() - start < timeout:
            s = self.ascii()
            if text.upper() in s.upper():
                return True
            time.sleep(1)
        return False


def main():
    print("=" * 60)
    print("  IBM AI USS Screen — Direct s3270 Submitter (HERC02)")
    print("=" * 60)

    if not JCL_PATH.exists():
        print(f"[!] JCL not found: {JCL_PATH}")
        sys.exit(1)

    jcl_lines = JCL_PATH.read_text().splitlines()
    print(f"[*] Loaded {len(jcl_lines)} lines from {JCL_PATH.name}")

    print(f"[*] Spawning s3270 → {HOST} as {USER}...")
    em = S3270Session()
    time.sleep(3)

    try:
        # ── Wait for VTAM logon screen ──────────────────────────
        print("[*] Waiting for VTAM logon screen...")
        if not em.wait_for("Logon", timeout=30):
            print("[!] Timeout — screen:")
            print(em.ascii()[:400])
            sys.exit(1)
        print("[+] At VTAM screen")

        # ── Logon ───────────────────────────────────────────────
        print(f"[*] Logging in as {USER}...")
        em.string(USER)
        em.enter(wait=3)

        screen = em.ascii()
        print(f"[*] After logon:\n{screen[:200]}")

        # Password (blank screen = hidden field)
        if len(screen.strip()) < 10 or "PASSWORD" in screen.upper():
            print("[*] Sending password...")
            em.string(PASS)
            em.enter(wait=4)

        # Press through broadcast / ICH messages to READY
        print("[*] Pressing through messages to READY...")
        for i in range(10):
            screen = em.ascii()
            if "READY" in screen.upper():
                break
            em.enter(wait=1.5)

        screen = em.ascii()
        if "READY" not in screen.upper():
            print(f"[!] Could not reach READY:\n{screen}")
            sys.exit(1)

        print("[+] At TSO READY")

        # ── Allocate dataset and use EDIT ───────────────────────
        # TSO SUBMIT * doesn't work well with 390 lines via string injection
        # Use EDIT to create a PDS member then SUBMIT it
        DS = f"'{USER}.IBMAI.JCL'"

        print(f"[*] Deleting old {DS}...")
        em.string(f"DELETE {DS}")
        em.enter(wait=3)

        print(f"[*] Allocating {DS}...")
        em.string(
            f"ALLOC DA({DS}) NEW CATALOG RECFM(F,B) LRECL(80) "
            f"BLKSIZE(3120) SPACE(5,5) TRACKS"
        )
        em.enter(wait=3)

        screen = em.ascii()
        print(f"[*] After alloc:\n{screen[:200]}")

        # Open EDIT
        print(f"[*] Opening EDIT for {DS}...")
        em.string(f"EDIT {DS} DATA NONUM")
        em.enter(wait=3)

        screen = em.ascii()
        print(f"[*] Edit screen:\n{screen[:200]}")

        if "EDIT" not in screen.upper() and "EMPTY" not in screen.upper() and "INPUT" not in screen.upper():
            print("[!] Did not enter EDIT mode")
            sys.exit(1)

        # Enter JCL lines
        print(f"[*] Entering {len(jcl_lines)} JCL lines...")
        for i, line in enumerate(jcl_lines, 1):
            safe = line[:80].rstrip()
            em.string(safe)
            em.enter(wait=0.12)
            if i % 50 == 0:
                print(f"    ... {i}/{len(jcl_lines)}")

        # Save and exit EDIT
        print("[*] Saving...")
        em.string("SAVE")
        em.enter(wait=2)
        em.string("END")
        em.enter(wait=2)

        screen = em.ascii()
        print(f"[*] After save/end:\n{screen[:200]}")

        # Submit
        print(f"[*] Submitting {DS}...")
        em.string(f"SUBMIT {DS}")
        em.enter(wait=5)

        screen = em.ascii()
        print(f"[*] After submit:\n{screen[:400]}")

        job_id = None
        if "JOB" in screen.upper():
            for word in screen.split():
                if word.upper().startswith("JOB") and len(word) > 5:
                    job_id = word
                    break
            print(f"[+] Submitted! Job: {job_id}")
        else:
            print("[!] Submit may have failed — check output above")

        # Wait for job to complete (assemble + link ~30-60s)
        print("[*] Waiting up to 120s for job completion...")
        if em.wait_for("READY", timeout=120):
            print("[+] Job complete — back at READY")
        else:
            print("[!] Timeout waiting for job")

        screen = em.ascii()
        print(f"[*] Post-job screen:\n{screen[:300]}")

        # ── Activate USS table ───────────────────────────────────
        print("[*] Activating USS table...")
        em.string("OPERATOR 'V NET,ACT,ID=USSN'")
        em.enter(wait=4)
        screen = em.ascii()
        print(f"[*] Operator response:\n{screen[:300]}")

        # Logoff
        em.string("LOGOFF")
        em.enter(wait=2)

    finally:
        em.terminate()

    print()
    print("=" * 60)
    print("  DONE! Disconnect and reconnect to port 3270 to see")
    print("  the new IBM AI USS logon screen.")
    print("=" * 60)


if __name__ == "__main__":
    main()
