#!/bin/bash
# =============================================================================
# Full RLVR Training - All Mainframe Topics
# =============================================================================
# Trains BigIron-AI on ALL mainframe languages and utilities:
#   - JCL (utilities, multi-step, procedures)
#   - COBOL (syntax validation)
#   - REXX (execution via IKJEFT01)
#   - Assembler (compilation)
#   - CICS (syntax validation)
#   - DB2 (syntax validation)
#   - RACF (syntax validation)
#   - VSAM (IDCAMS operations)
# =============================================================================

set -e
cd "$(dirname "$0")/../.."

LOG_FILE="/tmp/rlvr_full.log"
SCORES_FILE="/tmp/rlvr_full_scores.jsonl"
CHECKPOINT_DIR="data/training/rlvr_checkpoints"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}=============================================="
echo "Full RLVR Training - All Mainframe Topics"
echo "=============================================="
echo -e "${NC}"

# Check prerequisites
if ! curl -s "http://localhost:8038/" > /dev/null 2>&1; then
    echo "Starting TK5..."
    cd tk5/mvs-tk5 && ./start_tk5.sh &
    cd ../..
    sleep 60
fi

if ! ollama list | grep -q "bigiron:clean"; then
    echo -e "${RED}ERROR: bigiron:clean not found${NC}"
    exit 1
fi

mkdir -p "$CHECKPOINT_DIR"

# Create the comprehensive RLVR agent
cat > /tmp/rlvr_full_agent.py << 'PYTHON_EOF'
#!/usr/bin/env python3
"""
Full RLVR Agent - All Mainframe Topics

Verification methods:
- JCL: Execute on TK5, check CC
- REXX: Execute via IKJEFT01
- Assembler: Compile via ASMA90
- COBOL: Syntax validation (regex patterns)
- CICS: Syntax validation
- DB2: Syntax validation
- RACF: Syntax validation
- VSAM: IDCAMS operations on TK5
"""

import os
import sys
import json
import time
import random
import re
import subprocess
import urllib.request
import urllib.parse
from datetime import datetime, timedelta
from pathlib import Path

HERC_HTTP = "http://localhost:8038"
SCORES_FILE = "/tmp/rlvr_full_scores.jsonl"
CHECKPOINT_DIR = "/Users/w00tock/code/mainframe-ai-apple-silicon/data/training/rlvr_checkpoints"

# =============================================================================
# TASK DEFINITIONS - All Mainframe Topics
# =============================================================================

TASK_PROMPTS = [
    # --- JCL UTILITIES (TK5 executable) ---
    {"task": "jcl", "verify": "execute", "prompt": "Write JCL to run IEFBR14", "difficulty": 1},
    {"task": "jcl", "verify": "execute", "prompt": "Write JCL to run IDCAMS LISTCAT", "difficulty": 1},
    {"task": "jcl", "verify": "execute", "prompt": "Write JCL to copy a dataset using IEBGENER", "difficulty": 2},
    {"task": "jcl", "verify": "execute", "prompt": "Write JCL to use IEBCOPY to copy a PDS", "difficulty": 2},
    {"task": "jcl", "verify": "execute", "prompt": "Write JCL to sort a dataset using SORT", "difficulty": 2},
    {"task": "jcl", "verify": "execute", "prompt": "Write JCL with IDCAMS DELETE command", "difficulty": 2},
    {"task": "jcl", "verify": "execute", "prompt": "Write JCL with IDCAMS DEFINE CLUSTER for VSAM", "difficulty": 3},
    {"task": "jcl", "verify": "execute", "prompt": "Write JCL with IDCAMS REPRO to copy data", "difficulty": 3},
    {"task": "jcl", "verify": "execute", "prompt": "Write multi-step JCL with COND parameter", "difficulty": 3},
    {"task": "jcl", "verify": "execute", "prompt": "Write JCL procedure (PROC) with parameters", "difficulty": 4},

    # --- REXX (TK5 executable via IKJEFT01) ---
    {"task": "rexx", "verify": "execute", "prompt": "Write REXX to display HELLO WORLD", "difficulty": 1},
    {"task": "rexx", "verify": "execute", "prompt": "Write REXX to parse a string and display parts", "difficulty": 2},
    {"task": "rexx", "verify": "execute", "prompt": "Write REXX with DO loop counting 1 to 10", "difficulty": 2},
    {"task": "rexx", "verify": "execute", "prompt": "Write REXX using OUTTRAP to capture command output", "difficulty": 3},

    # --- ASSEMBLER (TK5 compilable) ---
    {"task": "asm", "verify": "compile", "prompt": "Write assembler program that returns RC=0", "difficulty": 2},
    {"task": "asm", "verify": "compile", "prompt": "Write assembler to display WTO message", "difficulty": 3},

    # --- COBOL (syntax validation) ---
    {"task": "cobol", "verify": "syntax", "prompt": "Write COBOL HELLO WORLD program", "difficulty": 1},
    {"task": "cobol", "verify": "syntax", "prompt": "Write COBOL with WORKING-STORAGE SECTION", "difficulty": 2},
    {"task": "cobol", "verify": "syntax", "prompt": "Write COBOL with PERFORM VARYING loop", "difficulty": 2},
    {"task": "cobol", "verify": "syntax", "prompt": "Write COBOL to read sequential file", "difficulty": 3},
    {"task": "cobol", "verify": "syntax", "prompt": "Write COBOL with EVALUATE statement", "difficulty": 3},
    {"task": "cobol", "verify": "syntax", "prompt": "Write COBOL STRING and UNSTRING operations", "difficulty": 3},
    {"task": "cobol", "verify": "syntax", "prompt": "Write COBOL CALL to subprogram", "difficulty": 4},

    # --- CICS (syntax validation) ---
    {"task": "cics", "verify": "syntax", "prompt": "Write CICS COBOL program with EXEC CICS SEND MAP", "difficulty": 3},
    {"task": "cics", "verify": "syntax", "prompt": "Write CICS EXEC CICS READ FILE command", "difficulty": 3},
    {"task": "cics", "verify": "syntax", "prompt": "Write CICS with EXEC CICS LINK to program", "difficulty": 3},
    {"task": "cics", "verify": "syntax", "prompt": "Write CICS with EXEC CICS HANDLE CONDITION", "difficulty": 4},

    # --- DB2 (syntax validation) ---
    {"task": "db2", "verify": "syntax", "prompt": "Write COBOL with embedded DB2 SELECT statement", "difficulty": 3},
    {"task": "db2", "verify": "syntax", "prompt": "Write DB2 SQL CREATE TABLE statement", "difficulty": 2},
    {"task": "db2", "verify": "syntax", "prompt": "Write COBOL DB2 program with CURSOR", "difficulty": 4},
    {"task": "db2", "verify": "syntax", "prompt": "Write DB2 stored procedure", "difficulty": 4},

    # --- RACF (syntax validation) ---
    {"task": "racf", "verify": "syntax", "prompt": "Write RACF commands to define a user", "difficulty": 2},
    {"task": "racf", "verify": "syntax", "prompt": "Write RACF PERMIT command for dataset access", "difficulty": 2},
    {"task": "racf", "verify": "syntax", "prompt": "Write RACF commands for group management", "difficulty": 3},

    # --- VSAM (IDCAMS on TK5) ---
    {"task": "vsam", "verify": "execute", "prompt": "Write IDCAMS to define KSDS cluster", "difficulty": 3},
    {"task": "vsam", "verify": "execute", "prompt": "Write IDCAMS to define ESDS cluster", "difficulty": 3},
    {"task": "vsam", "verify": "execute", "prompt": "Write IDCAMS to define RRDS cluster", "difficulty": 3},
    {"task": "vsam", "verify": "syntax", "prompt": "Write IDCAMS to define alternate index", "difficulty": 4},
]


class FullRLVRAgent:
    """Comprehensive RLVR Agent for all mainframe topics"""

    def __init__(self):
        self.start_time = datetime.now()
        self.iteration = 0
        self.scores = []
        self.scores_by_task = {}
        self.consecutive_fives = 0
        self.target_per_category = 3  # Need 3 score-5s per category

    def log(self, msg):
        ts = datetime.now().strftime('%H:%M:%S')
        print(f"[{ts}] {msg}", flush=True)

    def herc_cmd(self, cmd):
        try:
            url = f"{HERC_HTTP}/cgi-bin/tasks/cmd?cmd={urllib.parse.quote(cmd)}"
            with urllib.request.urlopen(url, timeout=10) as resp:
                return resp.read().decode('utf-8', errors='replace')
        except:
            return ""

    def get_syslog(self):
        try:
            url = f"{HERC_HTTP}/cgi-bin/tasks/syslog"
            with urllib.request.urlopen(url, timeout=10) as resp:
                body = resp.read().decode('utf-8', errors='replace')
                return re.sub(r'<[^>]+>', '', body)
        except:
            return ""

    def generate_response(self, prompt, task_type):
        full_prompt = f"{prompt}. Output only the {task_type.upper()} code, nothing else."
        try:
            result = subprocess.run(
                ['ollama', 'run', 'bigiron:clean', full_prompt],
                capture_output=True, text=True, timeout=60
            )
            return result.stdout.strip()
        except:
            return ""

    def extract_code(self, response, task_type):
        """Extract code from response"""
        # Try markdown block
        match = re.search(r'```(?:\w+)?\n(.*?)```', response, re.DOTALL)
        if match:
            return match.group(1).strip()
        return response.strip()

    def wrap_jcl(self, code, job_name):
        """Ensure JCL has proper JOB card"""
        if not re.search(r'^//\w+\s+JOB', code, re.MULTILINE):
            code = f"//{job_name}  JOB (ACCT),'RLVR',CLASS=A,MSGCLASS=X\n" + code
        return code

    def wrap_rexx_jcl(self, rexx_code, job_name):
        """Wrap REXX in JCL for execution"""
        return f"""//{job_name}  JOB (ACCT),'REXX',CLASS=A,MSGCLASS=X
//REXX     EXEC PGM=IKJEFT01
//SYSTSPRT DD SYSOUT=*
//SYSTSIN  DD *
%RXTEST
//SYSEXEC  DD *
/* REXX */
{rexx_code}
/*
"""

    def wrap_asm_jcl(self, asm_code, job_name):
        """Wrap assembler in compile JCL"""
        return f"""//{job_name}  JOB (ACCT),'ASM',CLASS=A,MSGCLASS=X
//ASM      EXEC PGM=ASMA90,PARM='DECK,NOOBJECT'
//SYSLIB   DD DSN=SYS1.MACLIB,DISP=SHR
//SYSUT1   DD UNIT=SYSDA,SPACE=(CYL,(1,1))
//SYSPUNCH DD SYSOUT=*
//SYSPRINT DD SYSOUT=*
//SYSIN    DD *
{asm_code}
/*
"""

    def submit_and_wait(self, jcl, job_name, timeout=60):
        """Submit JCL and wait for completion"""
        jcl_path = f"/tmp/rlvr_full_{self.iteration}.jcl"
        with open(jcl_path, 'w') as f:
            f.write(jcl)

        self.herc_cmd(f"devinit 00c {jcl_path} ascii eof")

        start = time.time()
        while (time.time() - start) < timeout:
            time.sleep(2)
            content = self.get_syslog()
            lines = content.split('\n')[-200:]
            content = '\n'.join(lines)

            if re.search(rf'\$HASP395\s+{job_name}\s+ENDED', content):
                if "JCL ERROR" in content and job_name in content:
                    return 12
                if "ABEND" in content and job_name in content:
                    return 999
                cc_match = re.search(rf'{job_name}.*?COND CODE\s+(\d+)', content)
                if cc_match:
                    return int(cc_match.group(1))
                return 0

        return -1  # Timeout

    def validate_cobol_syntax(self, code):
        """Validate COBOL syntax patterns"""
        checks = [
            (r'IDENTIFICATION\s+DIVISION', "Missing IDENTIFICATION DIVISION"),
            (r'PROGRAM-ID\s*\.', "Missing PROGRAM-ID"),
            (r'PROCEDURE\s+DIVISION', "Missing PROCEDURE DIVISION"),
        ]

        for pattern, error in checks:
            if not re.search(pattern, code, re.IGNORECASE):
                return False, error

        # Check for common syntax
        if re.search(r'DISPLAY\s+["\']', code, re.IGNORECASE):
            return True, "Valid COBOL with DISPLAY"
        if re.search(r'PERFORM\s+', code, re.IGNORECASE):
            return True, "Valid COBOL with PERFORM"
        if re.search(r'MOVE\s+', code, re.IGNORECASE):
            return True, "Valid COBOL with MOVE"
        if re.search(r'STOP\s+RUN', code, re.IGNORECASE):
            return True, "Valid COBOL"

        return True, "Valid COBOL structure"

    def validate_cics_syntax(self, code):
        """Validate CICS command syntax"""
        if not re.search(r'EXEC\s+CICS', code, re.IGNORECASE):
            return False, "Missing EXEC CICS"
        if not re.search(r'END-EXEC', code, re.IGNORECASE):
            return False, "Missing END-EXEC"
        return True, "Valid CICS syntax"

    def validate_db2_syntax(self, code):
        """Validate DB2 SQL syntax"""
        if re.search(r'EXEC\s+SQL', code, re.IGNORECASE):
            if not re.search(r'END-EXEC', code, re.IGNORECASE):
                return False, "Missing END-EXEC"
            return True, "Valid embedded SQL"
        if re.search(r'(SELECT|INSERT|UPDATE|DELETE|CREATE|DROP)\s+', code, re.IGNORECASE):
            return True, "Valid SQL"
        return False, "No SQL found"

    def validate_racf_syntax(self, code):
        """Validate RACF command syntax"""
        racf_cmds = ['ADDUSER', 'ALTUSER', 'DELUSER', 'ADDGROUP', 'ALTGROUP',
                     'PERMIT', 'ADDSD', 'ALTDSD', 'SETROPTS', 'RACDCERT']
        for cmd in racf_cmds:
            if cmd in code.upper():
                return True, f"Valid RACF {cmd}"
        return False, "No RACF command found"

    def verify_task(self, task, response):
        """Verify task based on verification method"""
        code = self.extract_code(response, task['task'])
        job_name = f"RLVR{self.iteration % 10000:04d}"

        if task['verify'] == 'execute':
            if task['task'] == 'jcl' or task['task'] == 'vsam':
                jcl = self.wrap_jcl(code, job_name)
                cc = self.submit_and_wait(jcl, job_name)
            elif task['task'] == 'rexx':
                jcl = self.wrap_rexx_jcl(code, job_name)
                cc = self.submit_and_wait(jcl, job_name)
            else:
                cc = -1

            if cc == 0:
                return 5, "CC 0000 - Perfect!"
            elif cc == -1:
                return 1, "Timeout"
            elif cc <= 4:
                return 4, f"CC {cc:04d} - Minor warning"
            elif cc <= 8:
                return 3, f"CC {cc:04d} - Warning"
            elif cc == 12:
                return 1, "JCL Error"
            else:
                return 2, f"CC {cc} - Error"

        elif task['verify'] == 'compile':
            if task['task'] == 'asm':
                jcl = self.wrap_asm_jcl(code, job_name)
                cc = self.submit_and_wait(jcl, job_name)
                if cc == 0:
                    return 5, "Assembly successful!"
                elif cc <= 4:
                    return 4, "Assembled with warnings"
                else:
                    return 2, "Assembly failed"

        elif task['verify'] == 'syntax':
            if task['task'] == 'cobol':
                valid, msg = self.validate_cobol_syntax(code)
            elif task['task'] == 'cics':
                valid, msg = self.validate_cics_syntax(code)
            elif task['task'] == 'db2':
                valid, msg = self.validate_db2_syntax(code)
            elif task['task'] == 'racf':
                valid, msg = self.validate_racf_syntax(code)
            else:
                valid, msg = False, "Unknown task"

            if valid:
                return 5, msg
            else:
                return 2, msg

        return 0, "Unknown verification"

    def update_scores(self, task_type, score):
        """Track scores by category"""
        if task_type not in self.scores_by_task:
            self.scores_by_task[task_type] = []
        self.scores_by_task[task_type].append(score)

        # Track consecutive 5s
        if score == 5:
            self.consecutive_fives += 1
        else:
            self.consecutive_fives = 0

    def save_good_example(self, prompt, response, task_type):
        """Save high-scoring examples"""
        example = {
            "messages": [
                {"role": "user", "content": prompt},
                {"role": "assistant", "content": response}
            ],
            "task_type": task_type
        }
        with open(f"{CHECKPOINT_DIR}/good_examples_full.jsonl", 'a') as f:
            f.write(json.dumps(example) + '\n')

    def get_category_status(self):
        """Get score-5 count per category"""
        status = {}
        for task_type, scores in self.scores_by_task.items():
            fives = sum(1 for s in scores if s == 5)
            status[task_type] = fives
        return status

    def all_categories_passed(self):
        """Check if all categories have enough score-5s"""
        required_categories = {'jcl', 'cobol', 'rexx', 'cics', 'db2', 'racf', 'vsam'}
        status = self.get_category_status()

        for cat in required_categories:
            if status.get(cat, 0) < self.target_per_category:
                return False
        return True

    def train_iteration(self):
        """Single training iteration"""
        self.iteration += 1

        # Pick a task (prioritize categories that need more 5s)
        status = self.get_category_status()
        needs_work = [t for t in TASK_PROMPTS
                      if status.get(t['task'], 0) < self.target_per_category]

        if needs_work:
            task = random.choice(needs_work)
        else:
            task = random.choice(TASK_PROMPTS)

        self.log(f"Iter {self.iteration} [{task['task'].upper()}]: {task['prompt'][:50]}...")

        # Generate and verify
        response = self.generate_response(task['prompt'], task['task'])
        score, reason = self.verify_task(task, response)

        # Update tracking
        self.update_scores(task['task'], score)
        self.scores.append(score)

        # Save good examples
        if score >= 4:
            self.save_good_example(task['prompt'], response, task['task'])

        # Log
        bar = '█' * score + '░' * (5 - score)
        self.log(f"  Score: [{bar}] {score}/5 - {reason}")

        # Show category progress every 10 iterations
        if self.iteration % 10 == 0:
            status = self.get_category_status()
            self.log(f"  Category progress: {status}")

        return score

    def run(self):
        """Main training loop"""
        self.log("Starting Full RLVR Training - All Mainframe Topics")
        self.log(f"Target: {self.target_per_category} score-5s per category")
        self.log("")

        max_iterations = 500

        try:
            while self.iteration < max_iterations:
                self.train_iteration()

                if self.all_categories_passed():
                    self.log("")
                    self.log("=" * 50)
                    self.log("SUCCESS! All categories achieved target!")
                    self.log("=" * 50)
                    break

                time.sleep(1)

        except KeyboardInterrupt:
            self.log("Interrupted")

        # Summary
        elapsed = datetime.now() - self.start_time
        status = self.get_category_status()

        self.log("")
        self.log("=" * 50)
        self.log("TRAINING COMPLETE")
        self.log("=" * 50)
        self.log(f"Iterations: {self.iteration}")
        self.log(f"Elapsed: {elapsed}")
        self.log(f"Category scores (5s achieved):")
        for cat, count in sorted(status.items()):
            check = "✓" if count >= self.target_per_category else " "
            self.log(f"  [{check}] {cat}: {count}/{self.target_per_category}")


if __name__ == "__main__":
    agent = FullRLVRAgent()
    agent.run()
PYTHON_EOF

echo -e "${GREEN}✓ Full RLVR agent created${NC}"
echo ""
echo -e "${YELLOW}Starting full training...${NC}"
echo ""

python3 /tmp/rlvr_full_agent.py 2>&1 | tee "$LOG_FILE"

echo ""
echo -e "${GREEN}Training complete. Log: $LOG_FILE${NC}"
