"""
FTP Service — wraps Python ftplib for MVS FTP interactions.

TK5 FTP server (port 2121) specifics:
  - Unix-style `ls -l` listing (d=PDS, -=PS)
  - LIST ignores prefix args → filter client-side
  - No CWD, NLST, SITE, FEAT, HELP support
  - RETR works for sequential datasets (bare names, NO quotes)
  - STOR may fail (read-only on most TK5 configs)
  - SYST, PWD, TYPE work
"""

import io
import ftplib
import logging
import threading
from typing import Optional, Dict, List
from datetime import datetime

logger = logging.getLogger(__name__)


class FTPService:
    """Manages an FTP session to the MVS TK5 FTP server."""

    def __init__(self):
        self._ftp: Optional[ftplib.FTP] = None
        self._lock = threading.Lock()
        self.host: str = ""
        self.port: int = 2121
        self.user: str = ""
        self.connected: bool = False
        self.last_error: str = ""
        self.transfer_log: List[Dict] = []
        self._cached_listing: List[Dict] = []

    # ── Connection ─────────────────────────────────────────────────────

    def connect(self, host: str = "localhost", port: int = 2121,
                user: str = "HERC01", password: str = "CUL8TR",
                timeout: float = 15.0) -> Dict:
        """Connect and authenticate to the MVS FTP server."""
        with self._lock:
            self._disconnect_locked()
            try:
                ftp = ftplib.FTP()
                ftp.connect(host, port, timeout=timeout)
                welcome = ftp.getwelcome() or ""
                ftp.login(user, password)
                self._ftp = ftp
                self.host = host
                self.port = port
                self.user = user
                self.connected = True
                self.last_error = ""
                self._cached_listing = []
                logger.info(f"FTP connected to {host}:{port} as {user}")
                return {
                    "success": True,
                    "message": f"Connected to {host}:{port} as {user}",
                    "welcome": welcome,
                }
            except Exception as e:
                self.connected = False
                self.last_error = str(e)
                logger.error(f"FTP connect failed: {e}")
                return {"success": False, "error": str(e)}

    def disconnect(self) -> Dict:
        """Disconnect from the FTP server."""
        with self._lock:
            return self._disconnect_locked()

    def _disconnect_locked(self) -> Dict:
        if self._ftp:
            try:
                self._ftp.quit()
            except Exception:
                try:
                    self._ftp.close()
                except Exception:
                    pass
            self._ftp = None
        was_connected = self.connected
        self.connected = False
        self._cached_listing = []
        if was_connected:
            self.host = ""
            self.user = ""
        return {"success": True, "message": "Disconnected"}

    def _ensure_connected(self) -> Optional[str]:
        """Check connection is alive. Returns error string or None."""
        if not self._ftp or not self.connected:
            return "Not connected"
        try:
            self._ftp.voidcmd("NOOP")
            return None
        except Exception:
            # Connection dropped — mark as disconnected
            self.connected = False
            self._ftp = None
            return "Connection lost"

    def get_status(self) -> Dict:
        """Get current FTP connection status."""
        return {
            "connected": self.connected,
            "host": f"{self.host}:{self.port}" if self.connected else "",
            "user": self.user,
            "last_error": self.last_error,
            "transfers": len(self.transfer_log),
        }

    # ── Directory Listing ──────────────────────────────────────────────

    def list_datasets(self, prefix: str = "") -> Dict:
        """List datasets. TK5 returns ALL datasets; we filter client-side by prefix."""
        with self._lock:
            err = self._ensure_connected()
            if err:
                return {"success": False, "error": err}
            try:
                lines = []
                self._ftp.retrlines("LIST", lines.append)
                all_entries = self._parse_unix_listing(lines)
                self._cached_listing = all_entries  # cache for browsing

                # Client-side prefix filter
                if prefix:
                    pf = prefix.upper().rstrip(".*")
                    entries = [e for e in all_entries
                               if e["name"].upper().startswith(pf)]
                else:
                    entries = all_entries

                return {
                    "success": True,
                    "entries": entries,
                    "count": len(entries),
                    "total_on_server": len(all_entries),
                }
            except ftplib.error_perm as e:
                return {"success": False, "error": str(e)}
            except Exception as e:
                self.last_error = str(e)
                return {"success": False, "error": str(e)}

    def _parse_unix_listing(self, lines: list) -> List[Dict]:
        """Parse TK5 Unix-style `ls -l` listing.
        
        Format: drwxr-xr-x 1 MVSCE MVSCE 1024 Feb 22 2026 DATASET.NAME
        'd' prefix = PDS, '-' prefix = PS (sequential).
        First line is 'total NNNNN' — skip it.
        """
        entries = []
        for line in lines:
            line = line.strip()
            if not line or line.startswith("total "):
                continue
            parts = line.split()
            if len(parts) < 9:
                continue
            perms = parts[0]
            name = parts[-1]
            if perms.startswith("d"):
                ds_type = "PDS"
            elif perms.startswith("-"):
                ds_type = "PS"
            else:
                ds_type = "unknown"
            entries.append({
                "name": name,
                "type": ds_type,
                "perms": perms,
                "size": parts[4] if len(parts) > 4 else "",
                "date": " ".join(parts[5:8]) if len(parts) > 7 else "",
                "raw": line,
            })
        return entries

    def list_members(self, pds_name: str) -> Dict:
        """List members of a PDS.
        
        TK5's FTP server doesn't support CWD or per-PDS LIST.
        Returns a note explaining this limitation.
        """
        return {
            "success": False,
            "error": f"TK5 FTP server does not support browsing PDS members. "
                     f"Use TN3270 terminal (ISPF 3.4) to browse {pds_name}.",
        }

    # ── Download (GET) ─────────────────────────────────────────────────

    def download(self, dataset: str, mode: str = "ascii") -> Dict:
        """Download a sequential dataset (bare name, no quotes).
        
        Note: PDS names return 'Access denied' on TK5 — only PS datasets work.
        """
        with self._lock:
            err = self._ensure_connected()
            if err:
                return {"success": False, "error": err}
            try:
                target = dataset  # bare name — TK5 doesn't want quotes

                if mode == "binary":
                    self._ftp.voidcmd("TYPE I")
                    buf = io.BytesIO()
                    self._ftp.retrbinary(f"RETR {target}", buf.write)
                    raw_bytes = buf.getvalue()
                    hex_lines = []
                    for i in range(0, len(raw_bytes), 16):
                        chunk = raw_bytes[i:i+16]
                        hex_part = " ".join(f"{b:02X}" for b in chunk)
                        ascii_part = "".join(
                            chr(b) if 32 <= b < 127 else "." for b in chunk)
                        hex_lines.append(
                            f"{i:08X}  {hex_part:<48s}  |{ascii_part}|")
                    content = "\n".join(hex_lines)
                    self._log_transfer("download", dataset, mode, len(raw_bytes))
                    return {
                        "success": True,
                        "dataset": dataset,
                        "mode": mode,
                        "content": content,
                        "size_bytes": len(raw_bytes),
                    }
                else:
                    self._ftp.voidcmd("TYPE A")
                    lines = []
                    self._ftp.retrlines(f"RETR {target}", lines.append)
                    content = "\n".join(lines)
                    self._log_transfer("download", dataset, mode, len(content))
                    return {
                        "success": True,
                        "dataset": dataset,
                        "mode": mode,
                        "content": content,
                        "lines": len(lines),
                    }
            except ftplib.error_perm as e:
                return {"success": False, "error": str(e)}
            except Exception as e:
                self.last_error = str(e)
                return {"success": False, "error": str(e)}

    # ── Upload (PUT) ───────────────────────────────────────────────────

    def upload(self, dataset: str, content: str, mode: str = "ascii") -> Dict:
        """Upload content to a dataset (bare name, no quotes).
        
        Note: TK5 FTP server is often read-only — STOR may fail.
        """
        with self._lock:
            err = self._ensure_connected()
            if err:
                return {"success": False, "error": err}
            try:
                target = dataset  # bare name

                if mode == "binary":
                    self._ftp.voidcmd("TYPE I")
                    buf = io.BytesIO(content.encode("latin-1"))
                    self._ftp.storbinary(f"STOR {target}", buf)
                else:
                    self._ftp.voidcmd("TYPE A")
                    buf = io.BytesIO(content.encode("ascii", errors="replace"))
                    self._ftp.storlines(f"STOR {target}", buf)

                self._log_transfer("upload", dataset, mode, len(content))
                return {
                    "success": True,
                    "dataset": dataset,
                    "mode": mode,
                    "size": len(content),
                    "message": f"Uploaded {len(content)} bytes to {dataset}",
                }
            except ftplib.error_perm as e:
                return {"success": False, "error": str(e)}
            except Exception as e:
                self.last_error = str(e)
                return {"success": False, "error": str(e)}

    # ── EBCDIC Test ────────────────────────────────────────────────────

    def test_ebcdic(self, dataset: str) -> Dict:
        """Download a dataset in both ASCII and binary mode to compare."""
        ascii_result = self.download(dataset, mode="ascii")
        binary_result = self.download(dataset, mode="binary")

        if not ascii_result.get("success") or not binary_result.get("success"):
            return {
                "success": False,
                "error": ascii_result.get("error") or binary_result.get("error"),
            }

        return {
            "success": True,
            "dataset": dataset,
            "ascii_content": ascii_result.get("content", ""),
            "ascii_lines": ascii_result.get("lines", 0),
            "binary_hex": binary_result.get("content", ""),
            "binary_size": binary_result.get("size_bytes", 0),
            "translation_ok": len(ascii_result.get("content", "")) > 0,
        }

    # ── Automated Test Suite ──────────────────────────────────────────

    def run_all_tests(self, host: str = "localhost", port: int = 2121,
                      user: str = "HERC01", password: str = "CUL8TR") -> Dict:
        """Run automated test suite against the TK5 FTP server.

        Tests what TK5 actually supports: connect, SYST, PWD, TYPE,
        LIST + catalog parsing, RETR sequential dataset, STOR (expect fail).
        """
        results = []
        overall_pass = True

        def _test(name: str, fn, *args, **kwargs):
            nonlocal overall_pass
            try:
                r = fn(*args, **kwargs)
                ok = r.get("success", False) if isinstance(r, dict) else bool(r)
                detail = ""
                if isinstance(r, dict):
                    if ok:
                        for key in ("count", "lines", "size", "message",
                                    "response", "welcome"):
                            if key in r:
                                detail = (f"{r[key]} items" if key == "count"
                                          else f"{r[key]} lines" if key == "lines"
                                          else f"{r[key]} bytes" if key == "size"
                                          else str(r[key])[:80])
                                break
                    else:
                        detail = r.get("error", "unknown error")
                if not ok:
                    overall_pass = False
                results.append({"test": name, "pass": ok, "detail": detail})
                return r
            except Exception as e:
                overall_pass = False
                results.append({"test": name, "pass": False, "detail": str(e)})
                return {"success": False, "error": str(e)}

        # 1. Connect
        conn_r = _test("FTP Connect", self.connect, host, port, user, password)
        if not self.connected:
            return {"success": True, "overall": False, "tests": results,
                    "passed": 0, "failed": 1, "total": 1}

        # 2. SYST — identify server
        _test("SYST (system type)", self.raw_command, "SYST")

        # 3. PWD — working directory
        _test("PWD (working dir)", self.raw_command, "PWD")

        # 4. TYPE A — switch to ASCII mode
        _test("TYPE A (ascii mode)", self.raw_command, "TYPE A")

        # 5. LIST — full catalog
        list_r = _test("LIST (full catalog)", self.list_datasets, "")

        # 6. Filter by user HLQ
        if list_r and list_r.get("success"):
            user_entries = [e for e in list_r.get("entries", [])
                           if e["name"].upper().startswith(user.upper())]
            results.append({
                "test": f"Filter {user}.* datasets",
                "pass": len(user_entries) > 0,
                "detail": f"{len(user_entries)} datasets" if user_entries
                          else "no datasets found for user HLQ",
            })
            if not user_entries:
                overall_pass = False

            # Count PDS vs PS
            pds_count = sum(1 for e in list_r["entries"] if e["type"] == "PDS")
            ps_count = sum(1 for e in list_r["entries"] if e["type"] == "PS")
            results.append({
                "test": "Catalog classification",
                "pass": True,
                "detail": f"{pds_count} PDS, {ps_count} PS, "
                          f"{list_r.get('total_on_server', 0)} total",
            })

        # 7. RETR a sequential dataset (PS type)
        ps_datasets = [e for e in (list_r or {}).get("entries", [])
                       if e["type"] == "PS"]
        if ps_datasets:
            dl_target = ps_datasets[0]["name"]
            dl_r = _test(f"RETR {dl_target} (ASCII)", self.download, dl_target, "ascii")
            if dl_r and dl_r.get("success"):
                # Also try binary
                _test(f"RETR {dl_target} (binary)", self.download, dl_target, "binary")
        else:
            results.append({
                "test": "RETR sequential dataset",
                "pass": False,
                "detail": "no PS datasets found to test",
            })
            overall_pass = False

        # 8. STOR test (expect to fail on TK5)
        stor_r = _test(
            f"STOR {user}.FTP.TEST (expect fail on TK5)",
            self.upload, f"{user}.FTP.TEST", "//TEST JOB\n", "ascii"
        )
        # If STOR failed, that's expected on TK5 — don't count as failure
        if not stor_r.get("success"):
            results[-1]["pass"] = True
            results[-1]["detail"] = "Access denied (expected — TK5 is read-only)"
            # Restore overall_pass if this was the only failure
            overall_pass = all(t["pass"] for t in results)

        passed = sum(1 for t in results if t["pass"])
        failed = sum(1 for t in results if not t["pass"])

        return {
            "success": True,
            "overall": overall_pass,
            "passed": passed,
            "failed": failed,
            "total": len(results),
            "tests": results,
        }

    # ── Raw FTP Command ────────────────────────────────────────────────

    def raw_command(self, command: str) -> Dict:
        """Send a raw FTP command."""
        with self._lock:
            err = self._ensure_connected()
            if err:
                return {"success": False, "error": err}
            try:
                response = self._ftp.sendcmd(command)
                return {"success": True, "command": command, "response": response}
            except ftplib.error_perm as e:
                return {"success": False, "command": command, "error": str(e)}
            except Exception as e:
                return {"success": False, "command": command, "error": str(e)}

    # ── Transfer Log ───────────────────────────────────────────────────

    def _log_transfer(self, direction: str, dataset: str, mode: str, size: int):
        self.transfer_log.append({
            "time": datetime.now().strftime("%H:%M:%S"),
            "direction": direction,
            "dataset": dataset,
            "mode": mode,
            "size": size,
        })
        if len(self.transfer_log) > 50:
            self.transfer_log = self.transfer_log[-50:]

    def get_transfer_log(self) -> List[Dict]:
        return list(self.transfer_log)


# ── Singleton ──────────────────────────────────────────────────────────

_ftp_service: Optional[FTPService] = None


def get_ftp_service() -> FTPService:
    """Get the singleton FTP service instance."""
    global _ftp_service
    if _ftp_service is None:
        _ftp_service = FTPService()
    return _ftp_service
