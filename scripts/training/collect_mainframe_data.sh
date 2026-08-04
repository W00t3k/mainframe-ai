#!/bin/bash
# Mainframe Training Data Collector
# Downloads and deduplicates training data from multiple sources

set -e
cd "$(dirname "$0")/../.."

DATA_DIR="data/training/collected"
DEDUP_DIR="data/training/deduplicated"
LOG_FILE="/tmp/data_collection.log"

mkdir -p "$DATA_DIR" "$DEDUP_DIR"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

log "========================================"
log "Mainframe Training Data Collection"
log "========================================"

# ============================================
# 1. HuggingFace Datasets
# ============================================
log "Downloading HuggingFace datasets..."

# Activate training venv for huggingface_hub
source .venv-train/bin/activate 2>/dev/null || true

python3 << 'PYTHON'
import os
import json
from pathlib import Path

try:
    from datasets import load_dataset
    HF_AVAILABLE = True
except ImportError:
    print("Installing datasets library...")
    os.system("pip install datasets -q")
    from datasets import load_dataset
    HF_AVAILABLE = True

DATA_DIR = Path("data/training/collected")
DATA_DIR.mkdir(parents=True, exist_ok=True)

datasets_to_fetch = [
    ("Fsoft-AIC/MainframeBench", "mainframe_bench"),
    ("harshini-kumar/CobolCodeBench", "cobol_code_bench"),
    ("Satya25/cobol-to-java-dataset", "cobol_to_java"),
]

for dataset_name, output_name in datasets_to_fetch:
    try:
        print(f"Fetching {dataset_name}...")
        ds = load_dataset(dataset_name, trust_remote_code=True)

        output_file = DATA_DIR / f"{output_name}.jsonl"
        count = 0

        with open(output_file, 'w') as f:
            for split in ds.keys():
                for item in ds[split]:
                    f.write(json.dumps(dict(item)) + '\n')
                    count += 1

        print(f"  Saved {count} examples to {output_file}")
    except Exception as e:
        print(f"  Error fetching {dataset_name}: {e}")

print("HuggingFace download complete!")
PYTHON

# ============================================
# 2. GitHub Repositories
# ============================================
log "Cloning GitHub repositories..."

GITHUB_REPOS=(
    "https://github.com/openmainframeproject/cobol-code-dataset"
    "https://github.com/openmainframeproject/cobol-programming-course"
    "https://github.com/CBTTape/CBT"
    "https://github.com/IBM/IBM-Z-zOS"
    "https://github.com/cicsdev/cics-banking-sample-application-cbsa"
    "https://github.com/jake-mainframe/COBOL"
    "https://github.com/dscobol/Cobol-Projects"
)

for repo in "${GITHUB_REPOS[@]}"; do
    repo_name=$(basename "$repo")
    target_dir="$DATA_DIR/github/$repo_name"

    if [ -d "$target_dir" ]; then
        log "  Updating $repo_name..."
        git -C "$target_dir" pull --quiet 2>/dev/null || true
    else
        log "  Cloning $repo_name..."
        git clone --depth 1 --quiet "$repo" "$target_dir" 2>/dev/null || log "  Failed to clone $repo"
    fi
done

# ============================================
# 3. Extract Code from Repositories
# ============================================
log "Extracting code files..."

python3 << 'PYTHON'
import os
import json
import hashlib
from pathlib import Path
from collections import defaultdict

DATA_DIR = Path("data/training/collected")
OUTPUT_FILE = DATA_DIR / "extracted_code.jsonl"

EXTENSIONS = {
    '.cbl': 'cobol',
    '.cob': 'cobol',
    '.cpy': 'copybook',
    '.jcl': 'jcl',
    '.proc': 'jcl_proc',
    '.rexx': 'rexx',
    '.rex': 'rexx',
    '.asm': 'assembler',
    '.pli': 'pli',
    '.pl1': 'pli',
}

seen_hashes = set()
extracted = defaultdict(int)

with open(OUTPUT_FILE, 'w') as out:
    for root, dirs, files in os.walk(DATA_DIR / "github"):
        # Skip .git directories
        dirs[:] = [d for d in dirs if d != '.git']

        for file in files:
            ext = Path(file).suffix.lower()
            if ext not in EXTENSIONS:
                continue

            filepath = Path(root) / file
            try:
                content = filepath.read_text(encoding='utf-8', errors='ignore')
            except:
                continue

            # Skip tiny or huge files
            if len(content) < 50 or len(content) > 100000:
                continue

            # Deduplicate by content hash
            content_hash = hashlib.md5(content.encode()).hexdigest()
            if content_hash in seen_hashes:
                continue
            seen_hashes.add(content_hash)

            lang = EXTENSIONS[ext]
            extracted[lang] += 1

            record = {
                "source": str(filepath.relative_to(DATA_DIR)),
                "language": lang,
                "filename": file,
                "content": content,
                "hash": content_hash
            }
            out.write(json.dumps(record) + '\n')

print(f"\nExtracted code files:")
for lang, count in sorted(extracted.items()):
    print(f"  {lang}: {count}")
print(f"Total unique files: {sum(extracted.values())}")
PYTHON

# ============================================
# 4. Convert to Training Format
# ============================================
log "Converting to chat training format..."

python3 << 'PYTHON'
import json
import hashlib
from pathlib import Path

DATA_DIR = Path("data/training/collected")
OUTPUT_FILE = Path("data/training/collected/training_ready.jsonl")

PROMPTS = {
    'cobol': [
        "Explain this COBOL program:",
        "What does this COBOL code do?",
        "Analyze this COBOL program and describe its purpose:",
        "Review this COBOL code:",
    ],
    'jcl': [
        "Explain this JCL job:",
        "What will this JCL execute?",
        "Describe what this JCL does:",
        "Analyze this JCL:",
    ],
    'copybook': [
        "Explain this COBOL copybook:",
        "What data structures are defined in this copybook?",
        "Describe the fields in this copybook:",
    ],
    'rexx': [
        "Explain this REXX script:",
        "What does this REXX program do?",
        "Analyze this REXX code:",
    ],
    'assembler': [
        "Explain this z/OS assembler code:",
        "What does this assembler routine do?",
        "Analyze this mainframe assembler:",
    ],
    'jcl_proc': [
        "Explain this JCL procedure:",
        "What does this PROC do?",
        "Describe this cataloged procedure:",
    ],
    'pli': [
        "Explain this PL/I program:",
        "What does this PL/I code do?",
        "Analyze this PL/I program:",
    ],
}

seen_hashes = set()
count = 0

with open(OUTPUT_FILE, 'w') as out:
    # Process extracted code
    extracted_file = DATA_DIR / "extracted_code.jsonl"
    if extracted_file.exists():
        with open(extracted_file) as f:
            for i, line in enumerate(f):
                record = json.loads(line)
                lang = record.get('language', 'cobol')
                content = record.get('content', '')

                # Skip if too short
                if len(content) < 100:
                    continue

                # Pick a prompt
                prompts = PROMPTS.get(lang, PROMPTS['cobol'])
                prompt = prompts[i % len(prompts)]

                # Create response (code explanation)
                response = f"This {lang.upper()} code:\n\n```{lang}\n{content[:2000]}\n```\n\n"

                if lang == 'cobol':
                    response += "This COBOL program processes data using standard mainframe conventions."
                elif lang == 'jcl':
                    response += "This JCL job defines the execution environment and data sets for batch processing."
                elif lang == 'copybook':
                    response += "This copybook defines shared data structures used across multiple programs."
                else:
                    response += f"This {lang} code performs mainframe operations."

                msg = {
                    "messages": [
                        {"role": "user", "content": f"{prompt}\n\n```{lang}\n{content[:2000]}\n```"},
                        {"role": "assistant", "content": response}
                    ]
                }

                # Dedupe
                msg_hash = hashlib.md5(json.dumps(msg).encode()).hexdigest()
                if msg_hash not in seen_hashes:
                    seen_hashes.add(msg_hash)
                    out.write(json.dumps(msg) + '\n')
                    count += 1

    # Process HuggingFace datasets
    for hf_file in DATA_DIR.glob("*.jsonl"):
        if hf_file.name in ['extracted_code.jsonl', 'training_ready.jsonl']:
            continue

        with open(hf_file) as f:
            for line in f:
                try:
                    record = json.loads(line)

                    # Different formats from different datasets
                    if 'question' in record and 'answer' in record:
                        msg = {
                            "messages": [
                                {"role": "user", "content": record['question']},
                                {"role": "assistant", "content": record['answer']}
                            ]
                        }
                    elif 'input' in record and 'output' in record:
                        msg = {
                            "messages": [
                                {"role": "user", "content": record['input']},
                                {"role": "assistant", "content": record['output']}
                            ]
                        }
                    elif 'code' in record:
                        msg = {
                            "messages": [
                                {"role": "user", "content": f"Explain this code:\n\n{record['code'][:2000]}"},
                                {"role": "assistant", "content": record.get('description', 'This mainframe code performs data processing operations.')}
                            ]
                        }
                    else:
                        continue

                    msg_hash = hashlib.md5(json.dumps(msg).encode()).hexdigest()
                    if msg_hash not in seen_hashes:
                        seen_hashes.add(msg_hash)
                        out.write(json.dumps(msg) + '\n')
                        count += 1

                except:
                    continue

print(f"\nCreated {count} deduplicated training examples")
print(f"Output: {OUTPUT_FILE}")
PYTHON

# ============================================
# 5. Merge with existing training data
# ============================================
log "Merging with existing training data..."

EXISTING="data/training/mlx_data/train.jsonl"
NEW_DATA="data/training/collected/training_ready.jsonl"

if [ -f "$NEW_DATA" ]; then
    NEW_COUNT=$(wc -l < "$NEW_DATA" | tr -d ' ')
    EXISTING_COUNT=$(wc -l < "$EXISTING" | tr -d ' ')

    # Final deduplication during merge
    python3 << PYTHON
import json
import hashlib
from pathlib import Path

existing = Path("$EXISTING")
new_data = Path("$NEW_DATA")
output = Path("data/training/mlx_data/train_merged.jsonl")

seen = set()
count = 0

with open(output, 'w') as out:
    # Read existing (already clean)
    with open(existing) as f:
        for line in f:
            h = hashlib.md5(line.strip().encode()).hexdigest()
            if h not in seen:
                seen.add(h)
                out.write(line)
                count += 1

    existing_count = count

    # Add new
    with open(new_data) as f:
        for line in f:
            h = hashlib.md5(line.strip().encode()).hexdigest()
            if h not in seen:
                seen.add(h)
                out.write(line)
                count += 1

    new_added = count - existing_count

print(f"Existing: {existing_count}")
print(f"New added: {new_added}")
print(f"Total: {count}")
PYTHON

    log "Merge complete!"
else
    log "No new data to merge"
fi

log "========================================"
log "Data Collection Complete!"
log "========================================"
log "Check: data/training/collected/"
log "Merged: data/training/mlx_data/train_merged.jsonl"
