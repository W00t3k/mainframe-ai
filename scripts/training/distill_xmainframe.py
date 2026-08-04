#!/usr/bin/env python3
"""
Distill knowledge from XMainframe-7B into training data for BigIron-AI.
Downloads the model, generates Q&A pairs, deduplicates, outputs JSONL.
"""

import os
import json
import hashlib
import random
from pathlib import Path
from datetime import datetime

# Prompts to ask the model - covers mainframe domains
PROMPT_TEMPLATES = {
    "jcl": [
        "Write JCL to copy a PDS member {src} to {dst}",
        "Create a JCL job to run a COBOL program named {prog}",
        "Write JCL to sort a file by columns {col1}-{col2}",
        "Create JCL to concatenate datasets {ds1} and {ds2}",
        "Write JCL to delete and recreate dataset {dsn}",
        "Create a JCL procedure for compiling COBOL with DB2",
        "Write JCL to submit a job with TYPRUN=SCAN",
        "Create JCL to IEBGENER copy with record reformatting",
        "Write JCL for IDCAMS REPRO from VSAM to sequential",
        "Create JCL to run IKJEFT01 with TSO commands",
        "Write JCL to allocate a GDG base and first generation",
        "Create JCL for IEBCOPY to compress a PDS",
        "Write JCL to run DFSORT with INCLUDE/OMIT logic",
        "Create JCL with COND parameter for conditional execution",
        "Write JCL to catalog a dataset with specific DCB attributes",
    ],
    "cobol": [
        "Write a COBOL paragraph to read a file until EOF",
        "Create COBOL code to validate a date field YYYYMMDD",
        "Write COBOL to perform a binary search on a table",
        "Create COBOL code to call a CICS program with LINK",
        "Write COBOL to handle DB2 SQLCODE -805",
        "Create COBOL code for string manipulation with UNSTRING",
        "Write COBOL to compute compound interest",
        "Create COBOL code to format a numeric field with commas",
        "Write COBOL EVALUATE statement for status code handling",
        "Create COBOL code to perform file matching logic",
        "Write COBOL to handle VSAM file status 35",
        "Create COBOL code for packed decimal arithmetic",
        "Write COBOL to implement a control break report",
        "Create COBOL code to call an assembler subroutine",
        "Write COBOL to parse a delimited input record",
    ],
    "racf": [
        "RACF command to create a new user {userid}",
        "Show RACF command to grant READ access to dataset {dsn}",
        "RACF commands to create a group and add members",
        "How to define a RACF general resource profile",
        "RACF command to permit access to a CICS transaction",
        "Show RACF command to set password rules",
        "RACF commands to audit dataset access",
        "How to use RACF RDEFINE for a new class",
        "RACF command to list user's group connections",
        "Show RACF PERMIT with ACCESS(ALTER)",
        "RACF commands to create a started task profile",
        "How to define RACF surrogate user access",
        "RACF command to delete a profile",
        "Show RACF command to refresh a class",
        "RACF commands for program control",
    ],
    "cics": [
        "CICS command to read a VSAM file with RIDFLD",
        "Write CICS RECEIVE MAP for BMS input",
        "CICS command for temporary storage queue operations",
        "Show CICS LINK command with COMMAREA",
        "CICS command to handle ABEND with HANDLE",
        "Write CICS SEND TEXT with cursor positioning",
        "CICS command for interval control START",
        "Show CICS WRITEQ TD for transient data",
        "CICS command to SYNCPOINT after updates",
        "Write CICS GETMAIN for dynamic storage",
        "CICS command to ENQ/DEQ for serialization",
        "Show CICS command for browsing a file",
        "CICS ASSIGN command to get terminal info",
        "Write CICS XCTL to transfer control",
        "CICS command to read from a channel container",
    ],
    "db2": [
        "DB2 SQL to create a table with primary key",
        "Write DB2 cursor logic for batch processing",
        "DB2 SQL for handling SQLCODE -811",
        "Show DB2 LOCK TABLE statement",
        "DB2 SQL to create an index with clustering",
        "Write DB2 stored procedure skeleton",
        "DB2 SQL for MERGE statement (UPSERT)",
        "Show DB2 EXPLAIN for query optimization",
        "DB2 SQL to grant SELECT on a table",
        "Write DB2 trigger for audit logging",
        "DB2 SQL for CASE expression in SELECT",
        "Show DB2 RUNSTATS command",
        "DB2 SQL to handle -904 resource unavailable",
        "Write DB2 SQL with row-level locking hints",
        "DB2 command to display thread status",
    ],
    "vsam": [
        "IDCAMS commands to define a KSDS cluster",
        "Show IDCAMS REPRO with SKIP and COUNT",
        "IDCAMS to define an alternate index",
        "Write IDCAMS to print VSAM catalog info",
        "IDCAMS commands for ESDS definition",
        "Show IDCAMS DELETE with PURGE option",
        "IDCAMS to build alternate index path",
        "Write IDCAMS VERIFY for recovery",
        "IDCAMS commands to alter FREESPACE",
        "Show IDCAMS EXPORT/IMPORT for backup",
        "IDCAMS to define RRDS cluster",
        "Write IDCAMS LISTCAT with ALLOCATION",
        "IDCAMS commands for SHAREOPTIONS",
        "Show IDCAMS to rename a cluster",
        "IDCAMS ALTER to change BUFFERSPACE",
    ],
    "rexx": [
        "REXX script to list PDS members",
        "Write REXX to parse SYSOUT and extract errors",
        "REXX to allocate and write to a dataset",
        "Show REXX OUTTRAP for capturing TSO output",
        "REXX script to check job status via SDSF",
        "Write REXX to call an ISPF service",
        "REXX to process JCL and modify parameters",
        "Show REXX DATE() and TIME() functions",
        "REXX script to FTP files to remote host",
        "Write REXX to send TSO SEND message",
        "REXX to read VSAM via EXECIO",
        "Show REXX LISTDSI for dataset info",
        "REXX script for batch dataset processing",
        "Write REXX to generate JCL dynamically",
        "REXX to call a REXX function library",
    ],
    "assembler": [
        "z/OS assembler macro to save registers",
        "Write assembler to call a COBOL program",
        "Assembler code for GETMAIN/FREEMAIN",
        "Show assembler SVC instruction usage",
        "Assembler macro for WTO message",
        "Write assembler for BLDL/FIND in PDS",
        "Assembler code for ATTACH/DETACH",
        "Show assembler for ENQ/DEQ",
        "Assembler macro for program linkage",
        "Write assembler ESTAE for recovery",
        "Assembler code for timer services",
        "Show assembler for cross-memory POST",
        "Assembler macro to parse PARM field",
        "Write assembler for dynamic allocation",
        "Assembler code using CSVQUERY",
    ],
    "utilities": [
        "IEBGENER to copy with REPRO",
        "Show IEBCOPY COPY with SELECT",
        "DFSORT to remove duplicates",
        "Write ICETOOL to split file by key",
        "IEHPROGM to scratch datasets",
        "Show IEFBR14 use cases",
        "DFSORT OUTFIL for multiple outputs",
        "Write ADRDSSU to dump datasets",
        "IDCAMS to reorganize VSAM",
        "Show SORT JOINKEYS example",
        "IEBUPDTE to update PDS member",
        "Write IEHMOVE for dataset migration",
        "DFSORT IFTHEN for conditional processing",
        "Show IEBPTPCH to print dataset",
        "ICEGENER vs IEBGENER comparison",
    ],
    "security": [
        "How to audit RACF for excessive permissions",
        "Common RACF misconfigurations to check",
        "How to detect privilege escalation in z/OS",
        "RACF profile analysis for security review",
        "How to review APF-authorized libraries",
        "Checking for SPECIAL/OPERATIONS abuse",
        "How to audit started task permissions",
        "Reviewing SURROGAT profiles for risk",
        "How to check UNIX permissions on z/OS",
        "Auditing DB2 SYSADM authorities",
        "How to review SMF records for access",
        "Checking FACILITY class for vulnerabilities",
        "How to audit CICS transaction security",
        "Reviewing DATASET profiles for *",
        "How to check for password policy bypass",
    ],
}

# Variable substitutions
VARIABLES = {
    "src": ["PROD.MASTER", "SYS1.PARMLIB", "USER.SOURCE", "CICS.LOADLIB"],
    "dst": ["BACKUP.MASTER", "TEST.PARMLIB", "USER.TARGET", "PROD.LOADLIB"],
    "prog": ["COBPROG1", "PAYROLL", "ACCT100", "RPTGEN", "BATCHUPD"],
    "col1": ["1", "5", "10", "15"],
    "col2": ["8", "20", "30", "50"],
    "ds1": ["PROD.FILE1", "INPUT.MASTER", "CUST.DATA"],
    "ds2": ["PROD.FILE2", "INPUT.DETAIL", "ACCT.DATA"],
    "dsn": ["USER.DATASET", "PROD.MASTER", "TEST.OUTPUT"],
    "userid": ["USERA01", "BATCH01", "CICSRGN", "DBADMIN"],
}

def fill_template(template):
    """Fill in template variables with random values."""
    result = template
    for var, values in VARIABLES.items():
        placeholder = "{" + var + "}"
        if placeholder in result:
            result = result.replace(placeholder, random.choice(values))
    return result

def generate_prompts(count_per_category=50):
    """Generate list of prompts to ask the model."""
    prompts = []
    for category, templates in PROMPT_TEMPLATES.items():
        for _ in range(count_per_category):
            template = random.choice(templates)
            prompt = fill_template(template)
            prompts.append({
                "category": category,
                "prompt": prompt
            })
    return prompts

def setup_model():
    """Download and setup XMainframe model."""
    print("Setting up XMainframe-7B model...")

    try:
        from mlx_lm import load, generate
        MODEL_ID = "mlx-community/XMainframe-7B-4bit"  # MLX quantized version
        print(f"Loading {MODEL_ID}...")
        model, tokenizer = load(MODEL_ID)
        return model, tokenizer, "mlx"
    except ImportError:
        print("MLX-LM not available, trying transformers...")

    try:
        from transformers import AutoModelForCausalLM, AutoTokenizer
        import torch

        MODEL_ID = "FSoft-AIC/XMainframe-7B"
        print(f"Loading {MODEL_ID}...")
        tokenizer = AutoTokenizer.from_pretrained(MODEL_ID)
        model = AutoModelForCausalLM.from_pretrained(
            MODEL_ID,
            torch_dtype=torch.float16,
            device_map="auto",
            trust_remote_code=True
        )
        return model, tokenizer, "hf"
    except Exception as e:
        print(f"Error loading model: {e}")
        return None, None, None

def generate_response_mlx(model, tokenizer, prompt):
    """Generate response using MLX."""
    from mlx_lm import generate

    system = "You are an expert IBM mainframe systems programmer with deep knowledge of z/OS, JCL, COBOL, CICS, DB2, RACF, and VSAM."
    full_prompt = f"<|system|>\n{system}<|end|>\n<|user|>\n{prompt}<|end|>\n<|assistant|>\n"

    response = generate(
        model,
        tokenizer,
        prompt=full_prompt,
        max_tokens=1024,
        temp=0.7,
    )
    return response

def generate_response_hf(model, tokenizer, prompt):
    """Generate response using HuggingFace transformers."""
    system = "You are an expert IBM mainframe systems programmer with deep knowledge of z/OS, JCL, COBOL, CICS, DB2, RACF, and VSAM."
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": prompt}
    ]

    inputs = tokenizer.apply_chat_template(messages, return_tensors="pt").to(model.device)
    outputs = model.generate(
        inputs,
        max_new_tokens=1024,
        temperature=0.7,
        do_sample=True,
        pad_token_id=tokenizer.eos_token_id
    )
    response = tokenizer.decode(outputs[0][inputs.shape[1]:], skip_special_tokens=True)
    return response

def check_disk_space(min_gb=50):
    """Check if we have enough disk space."""
    import shutil
    total, used, free = shutil.disk_usage("/")
    free_gb = free // (1024**3)
    print(f"Disk space: {free_gb}GB free")
    if free_gb < min_gb:
        print(f"WARNING: Less than {min_gb}GB free!")
        return False
    return True

def main():
    OUTPUT_DIR = Path("data/training/distilled")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE = OUTPUT_DIR / f"xmainframe_distilled_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jsonl"

    print("=" * 60)
    print("XMainframe Knowledge Distillation")
    print("=" * 60)

    # Check disk space before starting
    if not check_disk_space(min_gb=50):
        print("Not enough disk space! Need at least 50GB free.")
        print("Model download: ~4GB (4-bit) or ~14GB (full)")
        print("Clean up old checkpoints or data first.")
        return

    # Setup model
    model, tokenizer, backend = setup_model()
    if model is None:
        print("\nFailed to load model. Install requirements:")
        print("  pip install mlx-lm  # For Apple Silicon")
        print("  OR")
        print("  pip install transformers torch  # For generic")
        return

    print(f"\nUsing backend: {backend}")

    # Generate prompts
    prompts = generate_prompts(count_per_category=100)  # 100 per category = ~1500 total
    random.shuffle(prompts)

    print(f"Generated {len(prompts)} prompts")
    print(f"Output: {OUTPUT_FILE}")
    print()

    # Track deduplication
    seen_hashes = set()
    count = 0
    errors = 0

    generate_fn = generate_response_mlx if backend == "mlx" else generate_response_hf

    with open(OUTPUT_FILE, 'w') as f:
        for i, item in enumerate(prompts):
            try:
                prompt = item["prompt"]
                category = item["category"]

                print(f"[{i+1}/{len(prompts)}] {category}: {prompt[:50]}...")

                response = generate_fn(model, tokenizer, prompt)

                # Skip empty or too short responses
                if not response or len(response) < 50:
                    print("  (skipped - too short)")
                    continue

                # Create training record
                record = {
                    "messages": [
                        {"role": "user", "content": prompt},
                        {"role": "assistant", "content": response}
                    ],
                    "category": category
                }

                # Deduplicate
                record_hash = hashlib.md5(json.dumps(record["messages"]).encode()).hexdigest()
                if record_hash in seen_hashes:
                    print("  (skipped - duplicate)")
                    continue
                seen_hashes.add(record_hash)

                f.write(json.dumps(record) + '\n')
                count += 1

                if count % 100 == 0:
                    print(f"\n  === Saved {count} examples ===\n")

            except KeyboardInterrupt:
                print("\n\nInterrupted! Saving progress...")
                break
            except Exception as e:
                errors += 1
                print(f"  Error: {e}")
                if errors > 50:
                    print("Too many errors, stopping")
                    break

    print()
    print("=" * 60)
    print(f"Distillation complete!")
    print(f"Generated: {count} training examples")
    print(f"Errors: {errors}")
    print(f"Output: {OUTPUT_FILE}")
    print("=" * 60)

    # Merge into main training data
    print("\nTo merge with training data:")
    print(f"  cat {OUTPUT_FILE} >> data/training/mlx_data/train.jsonl")

if __name__ == "__main__":
    main()
