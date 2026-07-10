# External Mainframe Datasets

This document catalogs publicly available datasets for mainframe/COBOL LLM training.

## Available Datasets (Integrated)

### MainframeBench (Fsoft-AIC)
**Source:** https://huggingface.co/datasets/Fsoft-AIC/MainframeBench

| Split | Samples | Description |
|-------|---------|-------------|
| Question Answering | 2,598 | Mainframe/COBOL Q&A pairs |
| Multiple Choice | 1,931 | MCQ about mainframe concepts |
| COBOL Summarization | 2,523 | Code + natural language summary |
| **Total** | **7,052** | |

**Status:** Integrated into `data/training/examples/mainframebench_*.jsonl`

## Available Datasets (Not Yet Integrated)

### Open Mainframe Project COBOL Dataset
**Source:** https://github.com/openmainframeproject/cobol-code-dataset

- Production COBOL code samples
- Designed for LLM training

**Status:** Repository appears empty, may require Git LFS

## Private/Restricted Datasets

### XMainframe Training Data (Fsoft-AIC)
- 236 million tokens from GitHub COBOL + mainframe docs
- 33,561 COBOL files
- 8 million lines of code

**Status:** Not publicly available

### Mainframe-Instruct (Fsoft-AIC)
| Task | Training | Validation | Test |
|------|----------|------------|------|
| Multiple Choice | 13,894 | 1,544 | 1,931 |
| Question Answering | 18,692 | 2,078 | 2,598 |
| COBOL Summarization | 9,081 | 1,010 | 2,523 |
| **Total** | **41,667** | **4,632** | **7,052** |

**Status:** Not publicly available (only test set is public as MainframeBench)

### IBM watsonx Code Assistant Training Data
- Proprietary IBM training data
- Used for COBOL-to-Java translation

**Status:** Not publicly available

## Pre-trained Models

### XMainframe (Fsoft-AIC)
**HuggingFace:** https://huggingface.co/collections/Fsoft-AIC/xmainframe-66aca02d5b552e62033dc2bc

- Based on DeepSeek-Coder 7B
- Available in 7B and 10.5B variants
- Trained on mainframe-specific data

### COBOL-Coder
**Paper:** https://arxiv.org/pdf/2604.03986

- Based on Qwen2.5-Coder
- Specialized for COBOL generation/translation

### Mainframer (BloopAI)
- COBOL code completion model
- Limited to completion task only

## Integration Script

To integrate available external datasets:

```bash
python scripts/training/integrate_external_data.py
```

This will:
1. Download MainframeBench from HuggingFace
2. Convert to BigIron-AI training format
3. Save to `data/training/examples/`

## Data Format

All integrated data uses the chat format:

```json
{
  "messages": [
    {"role": "user", "content": "What is RACF?"},
    {"role": "assistant", "content": "RACF (Resource Access Control Facility)..."}
  ]
}
```

## Adding New Datasets

1. Create a converter function in `integrate_external_data.py`
2. Output to `data/training/examples/<dataset_name>.jsonl`
3. Run `build_bigiron_ai.sh` to include in next training run

## Evaluated Datasets (Not Applicable)

### IBM CodeNet
**Source:** https://github.com/IBM/Project_CodeNet

- 14 million code samples across 55 languages
- **No COBOL samples** - primarily competitive programming (C++, Python, Java, C, Ruby, C#)
- Not useful for mainframe training

## References

- [XMainframe Paper](https://arxiv.org/html/2408.04660v3)
- [COBOL-Coder Paper](https://arxiv.org/pdf/2604.03986)
- [IBM watsonx COBOL Announcement](https://www.ciodive.com/news/IBM-COBOL-AI-watsonx/691395/)
- [IBM CodeNet](https://github.com/IBM/Project_CodeNet)
