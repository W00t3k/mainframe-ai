#!/usr/bin/env python3
"""
TK5 Verifier for RLVR Training

Verifies LLM-generated JCL/code by:
1. Submitting to TK5 MVS via card reader
2. Waiting for job completion
3. Parsing JES output for success/failure
4. Returning a reward score (0-5)

Reward structure:
- 0: Invalid output format / not parseable
- 1: Parseable but doesn't compile/JCL error
- 2: Compiles but abends
- 3: Runs but wrong output
- 4: Runs with warnings
- 5: Perfect execution (CC 0000)

Usage:
    python tk5_verifier.py --test  # Run self-test

    # In training:
    from tk5_verifier import TK5Verifier
    verifier = TK5Verifier()
    reward = verifier.verify(llm_output, task_type="jcl")
"""

import os
import re
import sys
import time
import tempfile
import urllib.request
import urllib.parse
from dataclasses import dataclass
from typing import Optional, Tuple
from enum import Enum

# Try to import py3270 for TSO interaction
try:
    from py3270 import Emulator
    HAS_PY3270 = True
except ImportError:
    HAS_PY3270 = False
    print("Warning: py3270 not installed. TSO verification disabled.")

# Configuration
HERC_HTTP = os.getenv("HERC_HTTP", "http://localhost:8038")
TN3270_HOST = os.getenv("TN3270_HOST", "localhost")
TN3270_PORT = int(os.getenv("TN3270_PORT", "3270"))
TSO_USER = os.getenv("TSO_USER", "HERC01")
TSO_PASS = os.getenv("TSO_PASS", "CUL8TR")

# Console log path (for reading job results)
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CONSOLE_LOG = os.path.join(PROJECT_ROOT, "tk5/mvs-tk5/log/hercules_console.log")

# Job timeout (seconds)
JOB_TIMEOUT = 30
POLL_INTERVAL = 1


class TaskType(Enum):
    JCL = "jcl"           # Raw JCL to submit
    COBOL = "cobol"       # COBOL source (needs compile JCL)
    REXX = "rexx"         # REXX exec
    TSO_CMD = "tso_cmd"   # TSO command


@dataclass
class VerifyResult:
    reward: float         # 0-5 scale
    success: bool         # Did it work?
    job_id: str          # JOBnnnnn
    condition_code: int  # Return code (0 = success)
    messages: list       # JES messages
    error: str           # Error description if failed


class TK5Verifier:
    """Verifies LLM output by executing on TK5 MVS."""

    def __init__(self, herc_url: str = HERC_HTTP):
        self.herc_url = herc_url
        self.temp_dir = tempfile.mkdtemp(prefix="tk5_verify_")

    def herc_cmd(self, cmd: str) -> str:
        """Send command to Hercules console via HTTP API."""
        try:
            url = f"{self.herc_url}/cgi-bin/tasks/cmd?cmd={urllib.parse.quote(cmd)}"
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=10) as resp:
                body = resp.read().decode("utf-8", errors="replace")
                text = re.sub(r'<[^>]+>', '', body)
                return text.strip()
        except Exception as e:
            return f"ERROR: {e}"

    def _get_syslog(self) -> str:
        """Get current syslog from Hercules HTTP API."""
        try:
            url = f"{self.herc_url}/cgi-bin/tasks/syslog"
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=10) as resp:
                body = resp.read().decode("utf-8", errors="replace")
                # Strip HTML tags
                text = re.sub(r'<[^>]+>', '', body)
                return text
        except Exception as e:
            return ""

    def _get_log_position(self) -> int:
        """Get current syslog length (for tracking new entries)."""
        return len(self._get_syslog())

    def _read_log_from(self, start_pos: int) -> str:
        """Read syslog entries after start position."""
        full_log = self._get_syslog()
        if len(full_log) > start_pos:
            return full_log[start_pos:]
        return full_log[-500:]  # Return last 500 chars if log rotated

    def submit_jcl(self, jcl_content: str) -> Tuple[bool, str]:
        """
        Submit JCL to TK5 via card reader.
        Returns (success, job_name or error).
        """
        # Extract job name from JCL
        job_match = re.search(r'^//(\w+)\s+JOB', jcl_content, re.MULTILINE)
        job_name = job_match.group(1) if job_match else "UNKNOWN"

        # Write JCL to temp file
        jcl_path = os.path.join(self.temp_dir, "verify.jcl")
        with open(jcl_path, "w") as f:
            f.write(jcl_content)

        # Record log position before submit
        log_pos = self._get_log_position()

        # Submit via card reader
        result = self.herc_cmd(f"devinit 00c {jcl_path} ascii eof")

        if "ERROR" in result.upper() and "device initialized" not in result.lower():
            return False, result

        return True, job_name

    def wait_for_job(self, job_name: str, timeout: int = JOB_TIMEOUT) -> Tuple[bool, int, list]:
        """
        Wait for job to complete by watching syslog.
        Returns (completed, condition_code, messages).
        """
        start = time.time()
        messages = []

        # Truncate job name to 8 chars (MVS limit)
        job_name = job_name[:8].upper()

        while (time.time() - start) < timeout:
            time.sleep(POLL_INTERVAL)

            # Read full syslog
            syslog = self._get_syslog()

            # Look for job completion patterns
            # $HASP395 jobname ENDED
            if f"$HASP395 {job_name}" in syslog or f"HASP395 {job_name}" in syslog:
                messages = syslog.split('\n')[-50:]  # Last 50 lines
                cc = self._parse_condition_code(syslog, job_name)
                return True, cc, messages

            # IEF404I jobname - ENDED
            if f"IEF404I {job_name}" in syslog:
                messages = syslog.split('\n')[-50:]
                cc = self._parse_condition_code(syslog, job_name)
                return True, cc, messages

            # Check for JCL error
            if ("JCL ERROR" in syslog or "IEF452I" in syslog or "IEF453I" in syslog) and job_name in syslog:
                return True, 12, ["JCL ERROR"]

            # Check for abend
            abend_match = re.search(rf'{job_name}.*?(S[0-9A-F]{{3,4}})', syslog)
            if abend_match:
                return True, 999, [f"ABEND {abend_match.group(1)}"]

        return False, -1, ["TIMEOUT"]

    def _parse_condition_code(self, log_text: str, job_name: str) -> int:
        """Extract condition code from log output."""
        # Look for IEF142I patterns: jobname stepname procstep COND CODE nnnn
        cc_match = re.search(rf'{job_name}.*?COND CODE\s+(\d+)', log_text)
        if cc_match:
            return int(cc_match.group(1))

        # Look for ENDED - assume success if no error
        if f"IEF404I {job_name}" in log_text:
            # Check for any error indicators
            if "ABEND" in log_text or "ERROR" in log_text:
                return 8
            return 0

        return 0  # Assume success

    def classify_failure(self, log_text: str) -> Tuple[str, str]:
        """
        Classify failure reason from MVS messages.
        Returns (failure_type, description) for training signal.
        """
        failure_patterns = [
            (r'IEF452I', 'jcl_syntax', 'JCL syntax error - missing or invalid statement'),
            (r'IEF212I', 'dataset_not_found', 'Dataset not found or inaccessible'),
            (r'IEF287I', 'dataset_not_found', 'Dataset not cataloged'),
            (r'S0C4', 'abend_protection', 'Protection exception - invalid memory access'),
            (r'S0C7', 'abend_data', 'Data exception - invalid numeric data'),
            (r'S806', 'program_not_found', 'Program not found in load library'),
            (r'S804', 'memory', 'GETMAIN failure - insufficient memory'),
            (r'S722', 'output_limit', 'Output limit exceeded'),
            (r'S837', 'dataset_full', 'Dataset out of space'),
            (r'S913', 'security', 'RACF authorization failure'),
            (r'ICH408I', 'security', 'RACF access denied'),
            (r'IEF861I', 'enqueue', 'Dataset in use by another job'),
            (r'IEF877I', 'job_failed', 'Job failed - check preceding messages'),
            (r'JCL ERROR', 'jcl_syntax', 'JCL statement error'),
        ]

        for pattern, failure_type, description in failure_patterns:
            if re.search(pattern, log_text, re.IGNORECASE):
                return failure_type, description

        return 'unknown', 'Unclassified failure - check job output'

    def parse_llm_output(self, output: str, task_type: TaskType) -> Tuple[bool, str]:
        """
        Parse LLM output to extract code.
        Returns (success, extracted_code).
        """
        # Look for code in various formats

        # XML format (like Dante uses)
        xml_match = re.search(r'<file[^>]*>(.*?)</file>', output, re.DOTALL)
        if xml_match:
            return True, xml_match.group(1).strip()

        # Markdown code blocks
        code_match = re.search(r'```(?:jcl|cobol|rexx)?\n(.*?)```', output, re.DOTALL | re.IGNORECASE)
        if code_match:
            return True, code_match.group(1).strip()

        # Raw JCL (starts with //)
        if task_type == TaskType.JCL:
            jcl_match = re.search(r'(//\w+\s+JOB.*)', output, re.DOTALL)
            if jcl_match:
                return True, jcl_match.group(1).strip()

        return False, ""

    def wrap_cobol_in_jcl(self, cobol_source: str, program_name: str = "TESTPROG") -> str:
        """Wrap COBOL source in compile/link/run JCL."""
        return f"""//COBTEST  JOB (ACCT),'VERIFY',CLASS=A,MSGCLASS=X
//*
//COMPILE  EXEC PGM=IGYCRCTL,PARM='RENT,APOST'
//STEPLIB  DD DSN=IGY.V6R3M0.SIGYCOMP,DISP=SHR
//SYSIN    DD *
{cobol_source}
/*
//SYSLIB   DD DUMMY
//SYSPRINT DD SYSOUT=*
//SYSLIN   DD DSN=&&LOADSET,DISP=(MOD,PASS),UNIT=SYSDA,SPACE=(TRK,(3,3))
//SYSUT1   DD UNIT=SYSDA,SPACE=(CYL,(1,1))
//SYSUT2   DD UNIT=SYSDA,SPACE=(CYL,(1,1))
//SYSUT3   DD UNIT=SYSDA,SPACE=(CYL,(1,1))
//SYSUT4   DD UNIT=SYSDA,SPACE=(CYL,(1,1))
//SYSUT5   DD UNIT=SYSDA,SPACE=(CYL,(1,1))
//SYSUT6   DD UNIT=SYSDA,SPACE=(CYL,(1,1))
//SYSUT7   DD UNIT=SYSDA,SPACE=(CYL,(1,1))
//*
//LINK     EXEC PGM=IEWL,COND=(4,LT)
//SYSLIB   DD DSN=CEE.SCEELKED,DISP=SHR
//SYSLIN   DD DSN=&&LOADSET,DISP=(OLD,DELETE)
//SYSLMOD  DD DSN=&&GOSET({program_name}),DISP=(MOD,PASS),UNIT=SYSDA,SPACE=(TRK,(5,5,1))
//SYSPRINT DD SYSOUT=*
//*
//RUN      EXEC PGM={program_name},COND=(4,LT)
//STEPLIB  DD DSN=&&GOSET,DISP=(OLD,PASS)
//SYSOUT   DD SYSOUT=*
//SYSUDUMP DD SYSOUT=*
"""

    def verify(self, llm_output: str, task_type: str = "jcl",
               expected_output: str = None) -> VerifyResult:
        """
        Main verification entry point.

        Args:
            llm_output: Raw LLM response
            task_type: "jcl", "cobol", "rexx", or "tso_cmd"
            expected_output: Optional expected output for comparison

        Returns:
            VerifyResult with reward score and details
        """
        task = TaskType(task_type)

        # Step 1: Parse LLM output
        parsed, code = self.parse_llm_output(llm_output, task)
        if not parsed or not code:
            return VerifyResult(
                reward=0.0,
                success=False,
                job_id="",
                condition_code=-1,
                messages=["Could not parse LLM output"],
                error="Parse error"
            )

        # Step 2: Prepare JCL
        if task == TaskType.COBOL:
            jcl = self.wrap_cobol_in_jcl(code)
        elif task == TaskType.JCL:
            jcl = code
        else:
            return VerifyResult(
                reward=0.5,
                success=False,
                job_id="",
                condition_code=-1,
                messages=[f"Task type {task_type} not yet implemented"],
                error="Not implemented"
            )

        # Step 3: Submit job
        submitted, job_id = self.submit_jcl(jcl)
        if not submitted:
            return VerifyResult(
                reward=1.0,  # At least it parsed
                success=False,
                job_id="",
                condition_code=-1,
                messages=[job_id],
                error="Submit failed"
            )

        # Step 4: Wait for completion
        completed, cc, messages = self.wait_for_job(job_id)

        if not completed:
            return VerifyResult(
                reward=1.5,  # Submitted but timed out
                success=False,
                job_id=job_id,
                condition_code=-1,
                messages=messages,
                error="Timeout"
            )

        # Step 5: Calculate reward based on condition code
        if cc == 0:
            reward = 5.0  # Perfect
        elif cc < 4:
            reward = 4.5  # Minor warnings
        elif cc == 4:
            reward = 4.0  # Warnings
        elif cc < 8:
            reward = 3.5  # Some issues
        elif cc == 8:
            reward = 3.0  # Errors but completed
        elif cc < 999:
            reward = 2.0  # Serious errors
        else:
            reward = 1.5  # Abend

        return VerifyResult(
            reward=reward,
            success=(cc == 0),
            job_id=job_id,
            condition_code=cc,
            messages=messages,
            error="" if cc == 0 else f"CC={cc}"
        )

    def cleanup(self):
        """Clean up temp files."""
        import shutil
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)


def compute_reward(result: VerifyResult) -> float:
    """
    Compute GRPO-compatible reward from verification result.
    Normalized to [-1, 1] range for training.
    """
    # Map 0-5 reward to -1 to 1
    return (result.reward / 2.5) - 1.0


def test_verifier():
    """Self-test with sample JCL."""
    print("Testing TK5 Verifier...")

    verifier = TK5Verifier()

    # Test 1: Simple JCL
    test_jcl = """//TESTJOB  JOB (ACCT),'VERIFY TEST',CLASS=A,MSGCLASS=X
//STEP1    EXEC PGM=IEFBR14
//SYSPRINT DD SYSOUT=*
"""

    print("\n1. Testing simple JCL (IEFBR14)...")
    result = verifier.verify(test_jcl, task_type="jcl")
    print(f"   Reward: {result.reward}")
    print(f"   Success: {result.success}")
    print(f"   Job ID: {result.job_id}")
    print(f"   CC: {result.condition_code}")

    # Test 2: JCL in markdown
    test_markdown = """Here's JCL to run IEFBR14:

```jcl
//TESTJOB2 JOB (ACCT),'MARKDOWN TEST',CLASS=A,MSGCLASS=X
//STEP1    EXEC PGM=IEFBR14
```

This job does nothing but return CC=0.
"""

    print("\n2. Testing markdown-wrapped JCL...")
    result = verifier.verify(test_markdown, task_type="jcl")
    print(f"   Reward: {result.reward}")
    print(f"   Parsed successfully: {result.reward > 0}")

    verifier.cleanup()
    print("\nTest complete.")


if __name__ == "__main__":
    if "--test" in sys.argv:
        test_verifier()
    else:
        print("Usage: python tk5_verifier.py --test")
        print("\nOr import in training:")
        print("  from tk5_verifier import TK5Verifier, compute_reward")
