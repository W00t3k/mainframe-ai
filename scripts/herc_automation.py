#!/usr/bin/env python3
"""
herc_automation.py — Reusable Hercules/MVS automation for TK5.

Derived from MVS-sysgen/sysgen (GPLv3) and DC30_Workshop patterns,
adapted for TK5: correct paths, ports, proc names, and RAKF users.

Key methods:
  submit(jcl)            Submit JCL string via TCP to port 3505 (card reader)
  submit_file(path)      Submit a JCL file by path
  wait_for_string(s)     Poll hardcopy.log until string appears
  check_maxcc(jobname)   Parse prt00e.txt for job step return codes
  send_oper(cmd)         Send MVS operator command via Hercules HTTP console
  start_ftpd()           Start FTPD on port 2121
  start_kicks()          Start KICKS CICS
  submit_and_wait(jcl, jobname)  Submit + wait for purge + check RC

Usage:
  from scripts.herc_automation import HercAutomation
  h = HercAutomation()
  h.submit_file('jcl/ftpd.jcl')
  h.wait_for_string('HASP250 FTPDSTRT IS PURGED')
  h.check_maxcc('FTPDSTRT')
"""

import os
import sys
import time
import socket
import subprocess
import threading
import queue
import logging
import urllib.request
import urllib.parse
from pathlib import Path

ROOT        = Path(__file__).parent.parent
TK5_DIR     = ROOT / "tk5" / "mvs-tk5"
PRINTER     = TK5_DIR / "prt" / "prt00e.txt"
HARDCOPY    = TK5_DIR / "log" / "hardcopy.log"

CARD_PORT   = 3505
TN3270_PORT = 3270
HERC_HTTP   = 8038
WEBAPP_PORT = 8080

FATAL = [
    "open error",
    "Creating crash dump",
    "DISASTROUS ERROR",
    "disabled wait state 00020000 80000005",
    "HHC01023W Waiting for port 3270 to become free",
    "PROCESSOR CP00 APPEARS TO BE HUNG",
]

logging.basicConfig(format="%(asctime)s [%(levelname)s] %(message)s",
                    datefmt="%H:%M:%S", level=logging.INFO)
log = logging.getLogger("herc_automation")


class HercAutomation:
    """Automation interface for a running TK5 Hercules instance."""

    def __init__(self, timeout=300, printer_file=None, hardcopy_file=None):
        self.timeout      = timeout
        self.printer      = Path(printer_file) if printer_file else PRINTER
        self.hardcopy     = Path(hardcopy_file) if hardcopy_file else HARDCOPY
        self._log_q       = queue.Queue()
        self._stop        = threading.Event()
        self._tail_thread = None
        self._start_log_tail()

    # ── Internal: tail hardcopy.log ────────────────────────────────────────

    def _start_log_tail(self):
        def _tail():
            try:
                with open(self.hardcopy, "r", errors="ignore") as f:
                    f.seek(0, 2)
                    while not self._stop.is_set():
                        line = f.readline()
                        if line:
                            self._log_q.put(line)
                            for err in FATAL:
                                if err in line:
                                    log.error(f"FATAL Hercules error: {line.strip()}")
                        else:
                            time.sleep(0.2)
            except FileNotFoundError:
                log.warning(f"hardcopy.log not found: {self.hardcopy}")
            except Exception as e:
                log.warning(f"Log tail error: {e}")

        self._tail_thread = threading.Thread(target=_tail, daemon=True, name="log-tail")
        self._tail_thread.start()

    def close(self):
        self._stop.set()

    # ── Submit JCL via port 3505 ───────────────────────────────────────────

    def submit(self, jcl: str, host="localhost", port=CARD_PORT) -> bool:
        """Submit JCL string to Hercules card reader via TCP socket."""
        clean = "\n".join(
            "".join(c if ord(c) < 128 else " " for c in line)[:80]
            for line in jcl.splitlines()
        ) + "\n"
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(10)
            s.connect((host, port))
            s.sendall(clean.encode("ascii"))
            s.close()
            log.info(f"Submitted {len(jcl.splitlines())} lines to {host}:{port}")
            return True
        except Exception as e:
            log.error(f"Submit failed: {e}")
            return False

    def submit_file(self, path, host="localhost", port=CARD_PORT) -> bool:
        """Submit a JCL file by path."""
        p = Path(path)
        if not p.is_absolute():
            p = ROOT / p
        if not p.exists():
            log.error(f"JCL file not found: {p}")
            return False
        jcl = p.read_text(errors="replace")
        log.info(f"Submitting {p.name} ({len(jcl.splitlines())} lines)")
        return self.submit(jcl, host, port)

    # ── Wait for string in hardcopy.log ───────────────────────────────────

    def wait_for_string(self, string: str, timeout=None, stderr=False) -> bool:
        """Block until string appears in hardcopy.log. Returns True on match."""
        timeout = timeout or self.timeout
        start   = time.time()
        log.info(f"Waiting for: {string!r}")
        while time.time() - start < timeout:
            try:
                line = self._log_q.get(timeout=1)
                if string in line:
                    log.info(f"Found: {string!r}")
                    return True
            except queue.Empty:
                continue
        log.warning(f"Timeout waiting for: {string!r}")
        return False

    def wait_for_job_purge(self, jobname: str, timeout=None) -> bool:
        """Wait for HASP250 <JOBNAME> IS PURGED."""
        return self.wait_for_string(
            f"HASP250 {jobname.upper():<8} IS PURGED", timeout=timeout
        )

    # ── Check job return codes ─────────────────────────────────────────────

    def check_maxcc(self, jobname: str, steps_cc: dict = None,
                    printer_file=None) -> bool:
        """
        Parse prt00e.txt for IEF142I lines matching jobname.
        steps_cc = {'STEPNAME': '0000'} overrides expected RC per step.
        Returns True if all steps passed.
        """
        steps_cc    = steps_cc or {}
        pfile       = Path(printer_file) if printer_file else self.printer
        jobname     = jobname.upper()
        found_job   = False
        failed_step = False

        if not pfile.exists():
            log.warning(f"Printer file not found: {pfile}")
            return False

        with open(pfile, "r", errors="ignore") as f:
            for line in f:
                if "IEF142I" not in line or jobname not in line:
                    continue
                found_job = True
                parts = line.strip().split()
                try:
                    idx = parts.index("IEF142I")
                    j   = parts[idx:]
                    if j[3] != "-":
                        stepname = j[3]
                        maxcc    = j[11]
                    else:
                        stepname = j[2]
                        maxcc    = j[10]
                    expected = steps_cc.get(stepname, "0000")
                    status   = "OK" if maxcc == expected else "FAIL"
                    log.info(f"  {jobname} / {stepname}: RC={maxcc} (expected {expected}) [{status}]")
                    if maxcc != expected:
                        failed_step = True
                except (ValueError, IndexError):
                    continue

        if not found_job:
            log.warning(f"Job {jobname} not found in {pfile}")
            return False
        return not failed_step

    # ── Operator commands via Hercules HTTP console ────────────────────────

    def send_oper(self, command: str) -> bool:
        """Send MVS operator command via Hercules HTTP console (port 8038)."""
        return self._herc_http_cmd(f"/{command}")

    def send_herc(self, command: str) -> bool:
        """Send raw Hercules command via HTTP console."""
        return self._herc_http_cmd(command)

    def _herc_http_cmd(self, command: str) -> bool:
        try:
            url  = f"http://localhost:{HERC_HTTP}/cgi-bin/tasks/syslog"
            data = urllib.parse.urlencode({"command": command}).encode()
            req  = urllib.request.Request(url, data=data, method="POST")
            urllib.request.urlopen(req, timeout=5)
            log.info(f"Herc cmd: {command}")
            return True
        except Exception as e:
            log.debug(f"HTTP console unavailable ({e}), trying stdin...")
            return self._herc_stdin_cmd(command)

    def _herc_stdin_cmd(self, command: str) -> bool:
        """Fallback: write command to Hercules process stdin via /proc."""
        try:
            result = subprocess.run(
                ["pgrep", "-x", "hercules"], capture_output=True, text=True
            )
            pid = result.stdout.strip().split("\n")[0]
            if not pid:
                return False
            stdin_path = f"/proc/{pid}/fd/0"
            if os.path.exists(stdin_path):
                with open(stdin_path, "w") as f:
                    f.write(command + "\n")
                return True
        except Exception as e:
            log.debug(f"stdin cmd failed: {e}")
        return False

    # ── High-level operations ──────────────────────────────────────────────

    def submit_and_wait(self, jcl: str, jobname: str,
                        steps_cc: dict = None, timeout=None) -> bool:
        """Submit JCL, wait for purge, check return codes."""
        if not self.submit(jcl):
            return False
        if not self.wait_for_job_purge(jobname, timeout=timeout):
            log.warning(f"{jobname}: timed out waiting for purge")
            return False
        return self.check_maxcc(jobname, steps_cc)

    def submit_file_and_wait(self, path, jobname: str,
                             steps_cc: dict = None, timeout=None) -> bool:
        """Submit a JCL file, wait for purge, check return codes."""
        if not self.submit_file(path):
            return False
        if not self.wait_for_job_purge(jobname, timeout=timeout):
            log.warning(f"{jobname}: timed out waiting for purge")
            return False
        return self.check_maxcc(jobname, steps_cc)

    def start_ftpd(self, port=2121) -> bool:
        """Start FTPD server via MVS operator START command."""
        log.info(f"Starting FTPD on port {port}...")
        return self.send_oper(f"S FTPD,SRVPORT={port}")

    def stop_ftpd(self) -> bool:
        """Stop FTPD server."""
        return self.send_oper("P FTPD")

    def start_kicks(self) -> bool:
        """Start KICKS CICS subsystem."""
        log.info("Starting KICKS...")
        return self.send_oper("S KICKS")

    def stop_kicks(self) -> bool:
        """Stop KICKS CICS subsystem."""
        return self.send_oper("P KICKS")

    def activate_vtam_node(self, node_id: str) -> bool:
        """Activate a VTAM node (e.g. USS table, terminal group)."""
        return self.send_oper(f"V NET,ACT,ID={node_id}")

    def is_port_open(self, port: int, host="localhost") -> bool:
        """Check if a TCP port is open."""
        try:
            s = socket.socket()
            s.settimeout(2)
            s.connect((host, port))
            s.close()
            return True
        except Exception:
            return False

    def status(self) -> dict:
        """Return dict of service status."""
        return {
            "hercules":  self.is_port_open(TN3270_PORT),
            "tn3270":    self.is_port_open(TN3270_PORT),
            "card_reader": self.is_port_open(CARD_PORT),
            "herc_http": self.is_port_open(HERC_HTTP),
            "webapp":    self.is_port_open(WEBAPP_PORT),
            "ftp":       self.is_port_open(2121),
        }

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()


# ── CLI convenience ────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser(description="TK5 Hercules automation CLI")
    p.add_argument("--submit",  metavar="JCL_FILE", help="Submit a JCL file")
    p.add_argument("--wait",    metavar="JOBNAME",  help="Wait for job purge")
    p.add_argument("--maxcc",   metavar="JOBNAME",  help="Check job return codes")
    p.add_argument("--oper",    metavar="CMD",       help="Send operator command")
    p.add_argument("--status",  action="store_true", help="Show service status")
    p.add_argument("--ftpd",    action="store_true", help="Start FTPD on port 2121")
    p.add_argument("--kicks",   action="store_true", help="Start KICKS")
    args = p.parse_args()

    h = HercAutomation()

    if args.status:
        s = h.status()
        for k, v in s.items():
            print(f"  {'UP' if v else 'DOWN':4}  {k}")

    if args.submit:
        ok = h.submit_file(args.submit)
        print(f"Submit: {'OK' if ok else 'FAILED'}")

    if args.wait:
        ok = h.wait_for_job_purge(args.wait)
        print(f"Wait: {'PURGED' if ok else 'TIMEOUT'}")

    if args.maxcc:
        ok = h.check_maxcc(args.maxcc)
        print(f"MaxCC: {'PASS' if ok else 'FAIL'}")

    if args.oper:
        ok = h.send_oper(args.oper)
        print(f"Oper: {'OK' if ok else 'FAILED'}")

    if args.ftpd:
        ok = h.start_ftpd()
        print(f"FTPD: {'started' if ok else 'failed'}")

    if args.kicks:
        ok = h.start_kicks()
        print(f"KICKS: {'started' if ok else 'failed'}")

    h.close()
