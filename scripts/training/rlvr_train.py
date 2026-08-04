#!/usr/bin/env python3
"""
RLVR Training Script for BigIron-AI using TRL GRPO

This script:
1. Loads the fine-tuned BigIron model
2. Generates prompts using the RLVR agent
3. Gets completions and verifies on TK5
4. Trains with GRPO based on rewards

Requirements:
    pip install torch transformers trl accelerate

Usage:
    # First, ensure TK5 is running
    ./start.sh  # In another terminal

    # Run training
    python rlvr_train.py --steps 500 --batch-size 4

    # Dry run (no actual training)
    python rlvr_train.py --dry-run
"""

import os
import sys
import json
import argparse
from dataclasses import dataclass, field
from typing import List, Dict, Optional
import time

# Add local imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Check dependencies
def check_deps():
    missing = []
    try:
        import torch
    except ImportError:
        missing.append("torch")
    try:
        from transformers import AutoModelForCausalLM, AutoTokenizer
    except ImportError:
        missing.append("transformers")
    try:
        from trl import GRPOConfig, GRPOTrainer
    except ImportError:
        missing.append("trl")
    try:
        from datasets import Dataset
    except ImportError:
        missing.append("datasets")

    if missing:
        print(f"Missing dependencies: {', '.join(missing)}")
        print(f"Install with: pip install {' '.join(missing)}")
        sys.exit(1)

    return True


@dataclass
class RLVRConfig:
    """Training configuration."""
    # Model - Use SFT JCL model (knows correct JCL structure)
    model_name_or_path: str = os.path.join(PROJECT_ROOT, "data/training/bigiron-sft-jcl")
    adapter_path: str = os.path.join(PROJECT_ROOT, "data/training/bigiron-ai-lora")
    output_dir: str = os.path.join(PROJECT_ROOT, "data/training/bigiron-rlvr")

    # Training
    max_steps: int = 500
    batch_size: int = 4
    generations_per_prompt: int = 4
    learning_rate: float = 1e-6
    max_new_tokens: int = 2048

    # GRPO specific
    kl_coef: float = 0.1
    gamma: float = 1.0
    temperature: float = 0.8

    # Hardware
    device: str = "mps"  # Apple Silicon

    # Verification
    verify_on_tk5: bool = True
    tk5_timeout: int = 60


def create_reward_function(verifier, config: RLVRConfig):
    """Create reward function for GRPO."""
    from tk5_verifier import compute_reward

    def reward_fn(completions: List[str], **kwargs) -> List[float]:
        """
        Compute rewards for completions.

        Args:
            completions: LLM outputs
            **kwargs: Additional arguments from trainer

        Returns:
            List of rewards (floats)
        """
        rewards = []

        for completion in completions:
            if config.verify_on_tk5 and verifier:
                # Actually verify on TK5
                result = verifier.verify(
                    llm_output=completion,
                    task_type="jcl"  # Default to JCL
                )
                reward = compute_reward(result)
            else:
                # Heuristic-based reward (for testing without TK5)
                reward = heuristic_reward(completion, {"task_type": "jcl"})

            rewards.append(reward)

        return rewards

    return reward_fn


def heuristic_reward(completion: str, prompt: Dict) -> float:
    """
    Heuristic reward when TK5 isn't available.
    Checks for basic code quality signals.
    """
    reward = -0.5  # Start negative

    task_type = prompt.get("task_type", "jcl")

    if task_type == "jcl":
        # Check for JCL structure
        if "//" in completion and "JOB" in completion.upper():
            reward += 0.3
        if "EXEC" in completion.upper():
            reward += 0.2
        if "DD" in completion.upper():
            reward += 0.2
        if completion.count("//") >= 3:
            reward += 0.2
        # Penalty for common errors
        if "TODO" in completion or "..." in completion:
            reward -= 0.3

    elif task_type == "cobol":
        # Check for COBOL structure
        if "IDENTIFICATION DIVISION" in completion.upper():
            reward += 0.2
        if "PROCEDURE DIVISION" in completion.upper():
            reward += 0.3
        if "DATA DIVISION" in completion.upper():
            reward += 0.2
        if "STOP RUN" in completion.upper():
            reward += 0.2
        # Check for working-storage
        if "WORKING-STORAGE" in completion.upper():
            reward += 0.1

    # Cap to [-1, 1]
    return max(-1.0, min(1.0, reward))


def find_latest_checkpoint(output_dir: str) -> str:
    """Find the latest checkpoint in output directory."""
    import os
    import re
    if not os.path.exists(output_dir):
        return None
    checkpoints = [d for d in os.listdir(output_dir) if d.startswith("checkpoint-")]
    if not checkpoints:
        return None
    # Sort by step number
    checkpoints.sort(key=lambda x: int(re.search(r'\d+', x).group()), reverse=True)
    return os.path.join(output_dir, checkpoints[0])


def train(config: RLVRConfig, dry_run: bool = False, resume: bool = False):
    """Main training loop."""
    check_deps()

    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer
    from trl import GRPOConfig, GRPOTrainer
    from datasets import Dataset

    from rlvr_agent import PromptGenerator
    from tk5_verifier import TK5Verifier

    print("=" * 60)
    print("BigIron-AI RLVR Training")
    print("=" * 60)

    # Initialize components
    print("\n1. Initializing prompt generator...")
    prompt_gen = PromptGenerator()

    print("2. Initializing TK5 verifier...")
    verifier = TK5Verifier() if config.verify_on_tk5 else None

    if dry_run:
        print("\n[DRY RUN MODE - No model loading or training]")

        # Generate sample prompts
        prompts = prompt_gen.generate(n=10, difficulty_range=(0, 2))  # Start with easy tasks
        print("\nSample prompts that would be used:")
        for i, p in enumerate(prompts):
            print(f"  [{i+1}] {p['prompt'][:70]}...")

        print("\nReward function test (heuristic mode):")
        test_completions = [
            "//TESTJOB JOB (ACCT),'TEST'\n//STEP1 EXEC PGM=IEFBR14\n//SYSOUT DD SYSOUT=*",
            "This is not valid JCL",
            "IDENTIFICATION DIVISION.\nPROGRAM-ID. TEST.\nPROCEDURE DIVISION.\nSTOP RUN.",
        ]
        for comp in test_completions:
            r = heuristic_reward(comp, {"task_type": "jcl"})
            print(f"  Reward: {r:.2f} | {comp[:50]}...")

        return

    print("3. Loading model...")
    tokenizer = AutoTokenizer.from_pretrained(config.model_name_or_path)
    tokenizer.pad_token = tokenizer.eos_token

    # Load with memory optimizations for Apple Silicon
    model = AutoModelForCausalLM.from_pretrained(
        config.model_name_or_path,
        torch_dtype=torch.float16,
        device_map="auto",
        low_cpu_mem_usage=True,
    )

    # Load adapter if exists
    if os.path.exists(config.adapter_path):
        print(f"   Loading adapter from {config.adapter_path}")
        from peft import PeftModel
        model = PeftModel.from_pretrained(model, config.adapter_path)

    print("4. Creating training dataset...")
    # Generate initial prompts
    initial_prompts = prompt_gen.generate(n=config.max_steps * config.batch_size)
    # GRPO expects "prompt" column
    dataset = Dataset.from_list([{"prompt": p["prompt"]} for p in initial_prompts])

    print("5. Configuring GRPO trainer...")
    # Ensure batch size is divisible by num_generations
    num_gen = min(config.generations_per_prompt, config.batch_size)
    if config.batch_size % num_gen != 0:
        num_gen = 1

    grpo_config = GRPOConfig(
        output_dir=config.output_dir,
        per_device_train_batch_size=2,  # Must be divisible by num_generations
        num_generations=2,  # 2 generations per prompt
        max_completion_length=192,  # Enough for complete JCL (was 64, too short)
        learning_rate=config.learning_rate,
        beta=config.kl_coef,  # KL coefficient
        temperature=config.temperature,
        max_steps=config.max_steps,
        logging_steps=1,
        save_steps=50,  # Save less often to reduce disk usage
        save_total_limit=2,  # Only keep last 2 checkpoints (auto-cleanup)
        gradient_checkpointing=True,
        gradient_accumulation_steps=2,  # Accumulate to reduce memory peaks
        bf16=False,
        fp16=False,  # Disable mixed precision for MPS compatibility
        remove_unused_columns=False,
        report_to="none",  # Disable wandb etc
        sync_ref_model=False,  # Don't sync ref model to save memory
    )

    # Create reward function
    reward_fn = create_reward_function(verifier, config)

    print("6. Starting training...")

    # GRPO needs a reward model or function
    # For now, we'll use a simple training approach
    from trl import GRPOTrainer

    trainer = GRPOTrainer(
        model=model,
        args=grpo_config,
        processing_class=tokenizer,
        train_dataset=dataset,
        reward_funcs=reward_fn,
    )

    # Find checkpoint if resuming
    checkpoint = None
    if resume:
        checkpoint = find_latest_checkpoint(config.output_dir)
        if checkpoint:
            print(f"   Resuming from: {checkpoint}")
        else:
            print("   No checkpoint found, starting fresh")

    trainer.train(resume_from_checkpoint=checkpoint)

    print("\n7. Saving final model...")
    trainer.save_model(config.output_dir)
    tokenizer.save_pretrained(config.output_dir)

    print(f"\nTraining complete! Model saved to: {config.output_dir}")

    # Cleanup
    if verifier:
        verifier.cleanup()


def main():
    parser = argparse.ArgumentParser(description="RLVR Training for BigIron-AI")

    parser.add_argument("--steps", type=int, default=500, help="Training steps")
    parser.add_argument("--batch-size", type=int, default=4, help="Batch size")
    parser.add_argument("--lr", type=float, default=1e-6, help="Learning rate")
    parser.add_argument("--dry-run", action="store_true", help="Test without training")
    parser.add_argument("--no-tk5", action="store_true", help="Use heuristic rewards (no TK5)")
    parser.add_argument("--output", type=str, default=None, help="Output directory")
    parser.add_argument("--resume", action="store_true", help="Resume from latest checkpoint")

    args = parser.parse_args()

    config = RLVRConfig(
        max_steps=args.steps,
        batch_size=args.batch_size,
        learning_rate=args.lr,
        verify_on_tk5=not args.no_tk5,
    )

    if args.output:
        config.output_dir = args.output

    train(config, dry_run=args.dry_run, resume=args.resume)


if __name__ == "__main__":
    main()
