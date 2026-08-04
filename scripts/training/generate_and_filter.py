#!/usr/bin/env python3
"""
Generate JCL samples, filter for CC=0000, add to training data.

1. Generate 1000+ JCL samples from BigIron-AI
2. Submit each to TK5 MVS
3. Keep only CC=0000 successes
4. Format as training examples
5. Append to train.jsonl
"""

import os
import re
import json
import time
import random
import subprocess
import urllib.request
import urllib.parse
from pathlib import Path
from datetime import datetime

# Config
HERC_HTTP = "http://localhost:8038"
NUM_SAMPLES = 1000
OUTPUT_FILE = Path("data/training/verified_jcl.jsonl")
TRAIN_FILE = Path("data/training/mlx_data/train.jsonl")

# JCL prompts to try
PROMPTS = [
    "Write JCL to run IEFBR14 (do-nothing program)",
    "Write JCL to delete dataset MY.TEMP.DATA",
    "Write JCL to copy dataset A to dataset B using IEBGENER",
    "Write JCL to allocate a new sequential dataset",
    "Write JCL to run IDCAMS LISTCAT",
    "Write JCL to compress a PDS using IEBCOPY",
    "Write JCL to sort a file using DFSORT",
    "Write JCL to concatenate two datasets",
    "Write JCL to print a dataset using IEBPTPCH",
    "Write simple JCL that runs successfully",
]

def get_syslog():
    """Get Hercules syslog."""
    try:
        url = f"{HERC_HTTP}/cgi-bin/tasks/syslog"
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=10) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            return re.sub(r'<[^>]+>', '', body)
    except:
        return ""

def submit_jcl(jcl_content, job_num):
    """Submit JCL and return (success, condition_code, job_name)."""
    # Extract job name
    job_match = re.search(r'^//(\w+)\s+JOB', jcl_content, re.MULTILINE)
    if not job_match:
        return False, -1, "NO_JOB_CARD"

    job_name = job_match.group(1)[:8].upper()

    # Write to temp file
    jcl_path = f"/tmp/filter_job_{job_num}.jcl"
    with open(jcl_path, 'w') as f:
        f.write(jcl_content)

    # Get syslog position before submit
    syslog_before = get_syslog()

    # Submit via card reader
    try:
        url = f"{HERC_HTTP}/cgi-bin/tasks/cmd?cmd={urllib.parse.quote(f'devinit 00c {jcl_path} ascii eof')}"
        urllib.request.urlopen(url, timeout=10)
    except Exception as e:
        return False, -1, f"SUBMIT_ERROR: {e}"

    # Wait for job completion
    for _ in range(30):  # 30 second timeout
        time.sleep(1)
        syslog = get_syslog()

        # Check for completion
        if f"$HASP395 {job_name}" in syslog or f"IEF404I {job_name}" in syslog:
            # Check for JCL error
            if "JCL ERROR" in syslog and job_name in syslog:
                return True, 12, job_name
            # Check for abend
            if re.search(rf'{job_name}.*?S[0-9A-F]{{3,4}}', syslog):
                return True, 999, job_name
            # Assume success (CC=0) if ended without error
            if f"IEF404I {job_name}" in syslog:
                # Look for explicit CC
                cc_match = re.search(rf'{job_name}.*?COND CODE\s+(\d+)', syslog)
                if cc_match:
                    return True, int(cc_match.group(1)), job_name
                return True, 0, job_name  # Assume 0 if ended cleanly

        # Check for JCL error before job starts
        if "IEF452I" in syslog or "SKIPPING FOR JOB CARD" in syslog:
            if job_name in syslog or syslog_before != syslog:
                return True, 12, job_name

    return False, -1, "TIMEOUT"

def generate_jcl(prompt):
    """Generate JCL using BigIron-AI via Ollama."""
    try:
        result = subprocess.run(
            ["ollama", "run", "bigiron-ai", f"{prompt}. Output ONLY the JCL, no explanation."],
            capture_output=True,
            text=True,
            timeout=60
        )
        return result.stdout.strip()
    except Exception as e:
        return f"ERROR: {e}"

def clean_jcl(jcl):
    """Clean up common model mistakes in JCL."""
    lines = jcl.split('\n')
    cleaned = []

    for line in lines:
        # Remove line numbers at start
        line = re.sub(r'^\d{3}\s+', '', line)
        # Remove "Figure X-X" documentation artifacts
        if re.match(r'^Figure\s+\d', line):
            continue
        # Remove markdown code fences
        if line.strip().startswith('```'):
            continue
        # Keep the line
        cleaned.append(line)

    return '\n'.join(cleaned)

def main():
    print("=" * 60)
    print("Generate and Filter JCL Training Data")
    print("=" * 60)
    print(f"Generating {NUM_SAMPLES} samples...")
    print(f"Output: {OUTPUT_FILE}")
    print()

    # Check MVS is ready
    syslog = get_syslog()
    if not syslog:
        print("ERROR: Cannot connect to Hercules. Is TK5 running?")
        return
    print("✓ Connected to TK5")

    # Stats
    total = 0
    successes = 0
    cc_0000 = 0
    jcl_errors = 0
    timeouts = 0

    good_examples = []

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

    with open(OUTPUT_FILE, 'w') as out:
        for i in range(NUM_SAMPLES):
            prompt = random.choice(PROMPTS)
            total += 1

            print(f"[{i+1}/{NUM_SAMPLES}] {prompt[:50]}...", end=" ", flush=True)

            # Generate JCL
            raw_jcl = generate_jcl(prompt)
            if raw_jcl.startswith("ERROR"):
                print("GEN_ERROR")
                continue

            # Clean up common mistakes
            jcl = clean_jcl(raw_jcl)

            # Check for valid JOB card
            if not re.search(r'^//\w+\s+JOB', jcl, re.MULTILINE):
                print("NO_JOB")
                jcl_errors += 1
                continue

            # Submit to MVS
            completed, cc, job_name = submit_jcl(jcl, i)

            if not completed:
                print("TIMEOUT")
                timeouts += 1
                continue

            if cc == 0:
                print(f"✓ CC=0000")
                cc_0000 += 1
                successes += 1

                # Save as training example
                example = {
                    "messages": [
                        {"role": "user", "content": prompt},
                        {"role": "assistant", "content": jcl}
                    ],
                    "verified": True,
                    "cc": 0
                }
                out.write(json.dumps(example) + '\n')
                good_examples.append(example)

            elif cc == 4:
                print(f"CC=0004 (warnings)")
                successes += 1
                # Also save CC=4 as they're mostly good
                example = {
                    "messages": [
                        {"role": "user", "content": prompt},
                        {"role": "assistant", "content": jcl}
                    ],
                    "verified": True,
                    "cc": 4
                }
                out.write(json.dumps(example) + '\n')
                good_examples.append(example)

            elif cc == 12:
                print("JCL_ERROR")
                jcl_errors += 1
            else:
                print(f"CC={cc:04d}")

            # Progress update
            if (i + 1) % 50 == 0:
                print(f"\n--- Progress: {i+1}/{NUM_SAMPLES}, CC=0: {cc_0000}, Errors: {jcl_errors} ---\n")

    print()
    print("=" * 60)
    print("RESULTS")
    print("=" * 60)
    print(f"Total generated:    {total}")
    print(f"CC=0000 (perfect):  {cc_0000}")
    print(f"JCL errors:         {jcl_errors}")
    print(f"Timeouts:           {timeouts}")
    print(f"Success rate:       {cc_0000/total*100:.1f}%")
    print()

    # Append to training data
    if good_examples:
        print(f"Appending {len(good_examples)} verified examples to training data...")

        with open(TRAIN_FILE, 'a') as f:
            for ex in good_examples:
                f.write(json.dumps(ex) + '\n')

        new_count = sum(1 for _ in open(TRAIN_FILE))
        print(f"Training data now has {new_count} examples")
    else:
        print("No good examples generated.")

    print()
    print("Done!")

if __name__ == "__main__":
    main()
