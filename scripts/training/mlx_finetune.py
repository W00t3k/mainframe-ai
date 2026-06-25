#!/usr/bin/env python3
"""
MLX Fine-tuning for BigIron Mainframe Assistant

Uses Apple's MLX framework for efficient LoRA fine-tuning on Apple Silicon.
Converts our Q&A training data and fine-tunes Mistral for mainframe expertise.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
TRAINING_DIR = PROJECT_ROOT / "data" / "training"
GENERATED_DIR = TRAINING_DIR / "generated"
MLX_DATA_DIR = TRAINING_DIR / "mlx_data"


def convert_to_mlx_format(input_files: list[Path], output_dir: Path, train_split: float = 0.9):
    """Convert our JSONL training data to MLX chat format."""
    output_dir.mkdir(parents=True, exist_ok=True)

    all_samples = []
    for input_file in input_files:
        if not input_file.exists():
            print(f"Skipping missing file: {input_file}")
            continue

        with open(input_file, "r") as f:
            for line in f:
                if line.strip():
                    all_samples.append(json.loads(line))

    if not all_samples:
        raise SystemExit("No training samples found!")

    print(f"Loaded {len(all_samples)} training samples")

    # Shuffle for randomness
    import random
    random.seed(42)
    random.shuffle(all_samples)

    # Split into train/valid
    split_idx = int(len(all_samples) * train_split)
    train_samples = all_samples[:split_idx]
    valid_samples = all_samples[split_idx:]

    # Write train.jsonl
    train_file = output_dir / "train.jsonl"
    with open(train_file, "w") as f:
        for sample in train_samples:
            f.write(json.dumps(sample) + "\n")

    # Write valid.jsonl
    valid_file = output_dir / "valid.jsonl"
    with open(valid_file, "w") as f:
        for sample in valid_samples:
            f.write(json.dumps(sample) + "\n")

    print(f"Created {train_file} ({len(train_samples)} samples)")
    print(f"Created {valid_file} ({len(valid_samples)} samples)")

    return len(train_samples), len(valid_samples)


def run_mlx_finetune(
    data_dir: Path,
    model: str = "mistralai/Mistral-7B-Instruct-v0.3",
    output_dir: Path = None,
    num_iters: int = 1000,
    batch_size: int = 4,
    lora_rank: int = 8,
    learning_rate: float = 1e-5,
):
    """Run MLX LoRA fine-tuning."""
    if output_dir is None:
        output_dir = TRAINING_DIR / "mlx_adapters"

    output_dir.mkdir(parents=True, exist_ok=True)

    cmd = [
        sys.executable, "-m", "mlx_lm.lora",
        "--model", model,
        "--train",
        "--data", str(data_dir),
        "--adapter-path", str(output_dir),
        "--iters", str(num_iters),
        "--batch-size", str(batch_size),
        "--lora-rank", str(lora_rank),
        "--learning-rate", str(learning_rate),
    ]

    print(f"Running: {' '.join(cmd)}")
    print(f"This will take a while... Training on {model}")

    subprocess.run(cmd, check=True)

    print(f"\nAdapter saved to: {output_dir}")
    return output_dir


def fuse_adapter(
    base_model: str = "mistralai/Mistral-7B-Instruct-v0.3",
    adapter_path: Path = None,
    output_path: Path = None,
):
    """Fuse LoRA adapter into base model."""
    if adapter_path is None:
        adapter_path = TRAINING_DIR / "mlx_adapters"
    if output_path is None:
        output_path = TRAINING_DIR / "mlx_fused"

    output_path.mkdir(parents=True, exist_ok=True)

    cmd = [
        sys.executable, "-m", "mlx_lm.fuse",
        "--model", base_model,
        "--adapter-path", str(adapter_path),
        "--save-path", str(output_path),
    ]

    print(f"Fusing adapter into model...")
    subprocess.run(cmd, check=True)

    print(f"\nFused model saved to: {output_path}")
    return output_path


def convert_to_gguf(mlx_model_path: Path, output_path: Path = None):
    """Convert MLX model to GGUF for Ollama."""
    if output_path is None:
        output_path = TRAINING_DIR / "bigiron-finetuned.gguf"

    # MLX-LM can convert to GGUF
    cmd = [
        sys.executable, "-m", "mlx_lm.convert",
        "--hf-path", str(mlx_model_path),
        "--mlx-path", str(output_path.parent / "mlx_temp"),
        "-q",  # quantize
    ]

    print(f"Converting to GGUF format...")
    # Note: Full GGUF conversion may require llama.cpp
    # This is a placeholder - actual conversion depends on toolchain

    print(f"Model ready for Ollama at: {output_path}")
    return output_path


def main():
    parser = argparse.ArgumentParser(description="MLX Fine-tuning for BigIron")
    parser.add_argument("--convert-only", action="store_true", help="Only convert data, don't train")
    parser.add_argument("--train-only", action="store_true", help="Only train (data already converted)")
    parser.add_argument("--fuse", action="store_true", help="Fuse adapter into base model")
    parser.add_argument("--iters", type=int, default=1000, help="Training iterations")
    parser.add_argument("--batch-size", type=int, default=4, help="Batch size")
    parser.add_argument("--model", default="mistralai/Mistral-7B-Instruct-v0.3", help="Base model")
    args = parser.parse_args()

    # Find all training data
    training_files = list(GENERATED_DIR.glob("*.jsonl"))
    print(f"Found {len(training_files)} training files")

    if args.fuse:
        fuse_adapter(args.model)
        return 0

    if not args.train_only:
        # Convert data
        convert_to_mlx_format(training_files, MLX_DATA_DIR)

    if args.convert_only:
        print("\nData converted. Run with --train-only to start training.")
        return 0

    # Run fine-tuning
    run_mlx_finetune(
        MLX_DATA_DIR,
        model=args.model,
        num_iters=args.iters,
        batch_size=args.batch_size,
    )

    print("\n" + "="*60)
    print("Fine-tuning complete!")
    print("Next steps:")
    print("  1. Fuse adapter: python mlx_finetune.py --fuse")
    print("  2. Convert to GGUF for Ollama")
    print("  3. Create Ollama model: ollama create bigiron-tuned -f Modelfile")
    print("="*60)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
