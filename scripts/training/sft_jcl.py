#!/usr/bin/env python3
"""Quick SFT on JCL examples before RLVR."""
import os
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer, TrainingArguments
from trl import SFTTrainer, SFTConfig
from datasets import load_dataset

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Paths
BASE_MODEL = os.path.join(PROJECT_ROOT, "data/training/bigiron_full/fused")
DATA_PATH = "/tmp/full_training_text.jsonl"  # Preprocessed to text format
OUTPUT_DIR = os.path.join(PROJECT_ROOT, "data/training/bigiron-sft-jcl")

print("=" * 60)
print("JCL SFT Training (pre-RLVR)")
print("=" * 60)

print("\n1. Loading model...")
tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL)
if tokenizer.pad_token is None:
    tokenizer.pad_token = tokenizer.eos_token

model = AutoModelForCausalLM.from_pretrained(
    BASE_MODEL,
    torch_dtype=torch.float32,
)

print("2. Loading dataset...")
dataset = load_dataset("json", data_files=DATA_PATH, split="train")
print(f"   {len(dataset)} examples")

print("3. Configuring trainer...")
training_args = SFTConfig(
    output_dir=OUTPUT_DIR,
    num_train_epochs=2,  # 2 epochs over 34K examples
    per_device_train_batch_size=1,
    gradient_accumulation_steps=4,
    learning_rate=1e-5,
    logging_steps=10,  # Log every 10 steps
    save_steps=500,
    bf16=False,
    fp16=False,
    report_to="none",
    use_mps_device=True,  # Use MPS for Apple Silicon
    dataloader_pin_memory=False,
)

trainer = SFTTrainer(
    model=model,
    args=training_args,
    train_dataset=dataset,
    tokenizer=tokenizer,
    dataset_text_field="text",
    max_seq_length=2048,
)

print("4. Training...")
trainer.train()

print("\n5. Saving model...")
trainer.save_model(OUTPUT_DIR)
tokenizer.save_pretrained(OUTPUT_DIR)

print(f"\nSFT complete! Model saved to: {OUTPUT_DIR}")
print("Now run RLVR on this model for verification-based refinement.")
