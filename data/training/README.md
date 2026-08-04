---
language:
- en
license: apache-2.0
tags:
- mainframe
- z/OS
- COBOL
- JCL
- RACF
- CICS
- DB2
- REXX
- VSAM
- IBM
- mlx
- apple-silicon
base_model: mistralai/Mistral-7B-Instruct-v0.3
datasets:
- custom
pipeline_tag: text-generation
---

# BigIron-AI v2

A fine-tuned Mistral-7B model specialized for IBM mainframe expertise: z/OS, COBOL, JCL, CICS, RACF, DB2, VSAM, and REXX.

## Model Description

BigIronV2 is a LoRA fine-tuned version of Mistral-7B-Instruct-v0.3, trained on **86 hand-curated, high-quality examples** covering all major mainframe technologies. Unlike models trained on massive noisy datasets, BigironV2 produces clean, accurate output without artifacts.

**Key Features:**
- Clean output (no bracket tags, no OS/400 confusion)
- Accurate mainframe-specific code generation
- Validated via RLVR on TK5 MVS emulator
- Achieves 10 consecutive perfect JCL scores in 39 iterations

## Training Details

| Parameter | Value |
|-----------|-------|
| Base Model | Mistral-7B-Instruct-v0.3 |
| Fine-tune Type | LoRA |
| Training Examples | 86 curated |
| Val Loss | 2.077 → 1.090 |
| Quantization | Q8_0 |
| Model Size | 7.2 GB |
| Hardware | Apple Silicon (MLX) |

### Training Data Composition

| Category | Examples |
|----------|----------|
| JCL | 20 |
| COBOL | 15 |
| CICS | 10 |
| REXX | 10 |
| RACF | 12 |
| DB2 | 9 |
| z/OS Knowledge | 10 |

## Usage

### With Ollama

```bash
# Download the GGUF
wget https://huggingface.co/w00t3k/bigironv2/resolve/main/bigiron-v2.gguf

# Create Modelfile
cat > Modelfile << 'EOF'
FROM ./bigiron-v2.gguf
TEMPLATE """<s>[INST] {{ .Prompt }} [/INST]"""
PARAMETER temperature 0.3
PARAMETER top_p 0.9
PARAMETER repeat_penalty 1.15
PARAMETER num_predict 512
PARAMETER stop "</s>"
PARAMETER stop "[INST]"
EOF

# Register with Ollama
ollama create bigironv2 -f Modelfile

# Run
ollama run bigironv2 "Write JCL to copy a PDS using IEBCOPY"
```

### With MLX (Apple Silicon)

```python
from mlx_lm import load, generate

model, tokenizer = load("mistralai/Mistral-7B-Instruct-v0.3", 
                        adapter_path="./bigiron_clean_lora")
response = generate(model, tokenizer, 
                   prompt="[INST] What is RACF? [/INST]",
                   max_tokens=256)
print(response)
```

## Example Outputs

**Prompt:** "What is RACF?"

**Response:**
> RACF (Resource Access Control Facility) is IBM's security product for z/OS mainframes. It provides:
> 1. User Authentication - Validates user IDs and passwords
> 2. Access Control - Controls who can access datasets, programs, and resources
> 3. Auditing - Logs security events for compliance
> 4. User/Group Management - Organizes users into groups with shared permissions

**Prompt:** "Write JCL to run IEFBR14"

**Response:**
```jcl
//TESTJOB  JOB (ACCT),'TEST',CLASS=A,MSGCLASS=X
//STEP1    EXEC PGM=IEFBR14
```

## RLVR Validation

The model was validated using Reinforcement Learning with Verifiable Rewards (RLVR) on the TK5 MVS 3.8j emulator. Generated JCL is actually submitted to a running mainframe system to verify correctness.

**Results:** 10 consecutive perfect scores (CC 0000) in only 39 iterations.

## Files

- `bigiron-v2.gguf` - Quantized model (Q8_0, 7.2GB)
- `bigiron_clean_lora/` - LoRA adapters
  - `adapter_config.json` - Adapter configuration
  - `adapters.safetensors` - Trained weights (~40MB)

## Limitations

- Optimized for z/OS mainframes; may confuse IBM i (AS/400) concepts
- Best for common patterns; edge cases may need human review
- Context window limited to 2048 tokens

## Citation

```bibtex
@misc{bigiron-ai-2026,
  title={BigIron-AI: Fine-Tuning LLMs for Mainframe Domain Expertise on Apple Silicon},
  author={BigIron-AI Project Contributors},
  year={2026},
  howpublished={\url{https://github.com/W00t3k/mainframe-ai}}
}
```

## License

Apache 2.0

## Acknowledgments

- [MLX](https://github.com/ml-explore/mlx) - Apple's ML framework
- [TK5](http://wotho.ethz.ch/tk4-/) - MVS 3.8j turnkey system
- [Mistral AI](https://mistral.ai/) - Base model
