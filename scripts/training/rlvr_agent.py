#!/usr/bin/env python3
"""
RLVR Training Agent for BigIron-AI

Agent-based reinforcement learning with verifiable rewards.
Generates non-deterministic prompts, verifies on TK5, and trains.

Architecture:
    PromptGenerator → LLM → TK5Verifier → RewardCalculator → GRPO Training

Usage:
    python rlvr_agent.py --dry-run     # Generate prompts without training
    python rlvr_agent.py --train       # Full RLVR training loop
    python rlvr_agent.py --eval        # Evaluate current model
"""

import os
import sys
import json
import random
import argparse
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Callable
from enum import Enum
import time

# Local imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from tk5_verifier import TK5Verifier, VerifyResult, compute_reward

# Try imports for training
try:
    import torch
    HAS_TORCH = True
except ImportError:
    HAS_TORCH = False

try:
    from transformers import AutoModelForCausalLM, AutoTokenizer
    from trl import GRPOConfig, GRPOTrainer
    HAS_TRL = True
except ImportError:
    HAS_TRL = False


# =============================================================================
# TASK DEFINITIONS - Building blocks for non-deterministic prompts
# =============================================================================

class TaskCategory(Enum):
    JCL_UTILITY = "jcl_utility"      # IEBGENER, IEBCOPY, IDCAMS, etc.
    JCL_CONTROL = "jcl_control"      # COND, IF/THEN, procedures
    VSAM = "vsam"                     # VSAM cluster operations
    SORT = "sort"                     # DFSORT/SYNCSORT
    COBOL_BASIC = "cobol_basic"      # Simple COBOL programs
    COBOL_FILE = "cobol_file"        # COBOL file I/O
    COBOL_TABLE = "cobol_table"      # COBOL tables/arrays


@dataclass
class TaskTemplate:
    """Template for generating varied prompts."""
    category: TaskCategory
    base_prompt: str
    variations: List[str] = field(default_factory=list)  # Swap-in phrases
    parameters: Dict[str, List[str]] = field(default_factory=dict)  # {name: [options]}
    difficulty: int = 1  # 1-5 scale


# Task templates with variations
TASK_TEMPLATES = [
    # TRIVIAL - Few-shot examples to teach structure
    TaskTemplate(
        category=TaskCategory.JCL_UTILITY,
        base_prompt="""Write JCL to run IEFBR14. Example format:
//MYJOB   JOB (ACCT),'DESC',CLASS=A,MSGCLASS=X
//STEP1   EXEC PGM=IEFBR14
Now write similar JCL:""",
        variations=[
            """Here is an example JCL job:
//SAMPLE  JOB (ACCT),'TEST',CLASS=A
//RUN     EXEC PGM=IEFBR14
Write a similar IEFBR14 job:""",
        ],
        parameters={},
        difficulty=0  # Trivial with example
    ),
    TaskTemplate(
        category=TaskCategory.JCL_UTILITY,
        base_prompt="""Write JCL to list a dataset. Example:
//LISTJOB JOB (ACCT),'LIST',CLASS=A,MSGCLASS=X
//STEP1   EXEC PGM=IEBGENER
//SYSUT1  DD DSN=SYS1.PARMLIB(IEASYS00),DISP=SHR
//SYSUT2  DD SYSOUT=*
//SYSPRINT DD SYSOUT=*
//SYSIN   DD DUMMY
Now write similar JCL to list a dataset:""",
        variations=[],
        parameters={},
        difficulty=0  # With example
    ),
    # JCL Utilities
    TaskTemplate(
        category=TaskCategory.JCL_UTILITY,
        base_prompt="Write JCL to {action} using {utility}",
        variations=["create a job that will", "generate JCL code to", "show me JCL for"],
        parameters={
            "action": [
                "copy a sequential dataset",
                "copy a PDS member",
                "delete a dataset",
                "allocate a new dataset",
                "print a dataset to SYSOUT",
                "list catalog entries",
            ],
            "utility": ["IEBGENER", "IEBCOPY", "IEFBR14", "IDCAMS"],
        },
        difficulty=1
    ),
    TaskTemplate(
        category=TaskCategory.VSAM,
        base_prompt="Write JCL to {action} a VSAM {cluster_type}",
        variations=["create JCL for", "show how to", "generate code to"],
        parameters={
            "action": ["define", "delete", "repro", "verify", "alter", "listcat"],
            "cluster_type": ["KSDS", "ESDS", "RRDS", "LINEAR"],
        },
        difficulty=2
    ),
    TaskTemplate(
        category=TaskCategory.SORT,
        base_prompt="Write JCL to sort a file {sort_spec} using DFSORT",
        variations=["create a sort job that", "generate sort JCL to", "show DFSORT JCL to"],
        parameters={
            "sort_spec": [
                "by columns 1-10 ascending",
                "by columns 1-5 descending, then 10-15 ascending",
                "and remove duplicates",
                "and include only records where column 5 equals 'A'",
                "and reformat the output to columns 1-20 only",
                "and sum numeric fields in columns 30-40",
            ],
        },
        difficulty=2
    ),
    TaskTemplate(
        category=TaskCategory.JCL_CONTROL,
        base_prompt="Write JCL with {control_feature}",
        variations=["create a job using", "generate JCL demonstrating", "show how to use"],
        parameters={
            "control_feature": [
                "COND parameter to skip a step if prior step fails",
                "IF/THEN/ELSE/ENDIF conditional execution",
                "INCLUDE a procedure and override a DD",
                "symbolic parameters passed to a procedure",
                "restart from a specific step",
                "passing temporary datasets between steps",
            ],
        },
        difficulty=3
    ),
    TaskTemplate(
        category=TaskCategory.COBOL_BASIC,
        base_prompt="Write a COBOL program that {cobol_task}",
        variations=["create COBOL code to", "generate a COBOL program that", "show COBOL for"],
        parameters={
            "cobol_task": [
                "displays 'HELLO WORLD' to SYSOUT",
                "accepts the current date and displays it",
                "reads a number from input and displays it doubled",
                "validates if an input field is numeric",
                "converts a string to uppercase",
                "calculates the factorial of a number",
            ],
        },
        difficulty=2
    ),
    TaskTemplate(
        category=TaskCategory.COBOL_FILE,
        base_prompt="Write a COBOL program that {file_task}",
        variations=["create COBOL for", "generate code that", "show a program to"],
        parameters={
            "file_task": [
                "reads a sequential file and counts records",
                "copies input to output, converting to uppercase",
                "reads a file and calculates sum of a numeric field",
                "produces a report with headers and page breaks",
                "reads multiple input files and merges them",
                "writes to multiple output files based on a key",
            ],
        },
        difficulty=3
    ),
    TaskTemplate(
        category=TaskCategory.COBOL_TABLE,
        base_prompt="Write a COBOL program using {table_feature}",
        variations=["create COBOL with", "generate code using", "show how to use"],
        parameters={
            "table_feature": [
                "SEARCH to find a value in a table",
                "SEARCH ALL for binary search",
                "OCCURS DEPENDING ON for variable-length tables",
                "a two-dimensional table",
                "PERFORM VARYING to iterate through a table",
                "INDEXED BY for efficient table access",
            ],
        },
        difficulty=4
    ),
]

# Additional context injections for variety
CONTEXT_INJECTIONS = [
    "",  # No extra context
    "The output should be production-quality.",
    "Include error handling.",
    "Make it as simple as possible.",
    "Optimize for performance.",
    "Add appropriate comments.",
    "Follow enterprise coding standards.",
]

DATASET_NAMES = [
    "HERC01.TEST.DATA",
    "HERC01.PROD.FILE",
    "SYS1.SAMPLE.DATA",
    "MYAPP.INPUT.FILE",
    "BATCH.OUTPUT.DATA",
]


# =============================================================================
# PROMPT GENERATOR - Creates non-deterministic prompts
# =============================================================================

class PromptGenerator:
    """Generates varied prompts from templates."""

    def __init__(self, templates: List[TaskTemplate] = None, seed: int = None):
        self.templates = templates or TASK_TEMPLATES
        if seed:
            random.seed(seed)

    def generate(self, n: int = 1, difficulty_range: tuple = (0, 5)) -> List[Dict]:
        """
        Generate n non-deterministic prompts.

        Returns list of:
            {
                "prompt": str,
                "category": str,
                "difficulty": int,
                "task_type": str,  # jcl, cobol, etc.
            }
        """
        prompts = []

        for _ in range(n):
            # Filter by difficulty
            eligible = [t for t in self.templates
                       if difficulty_range[0] <= t.difficulty <= difficulty_range[1]]

            if not eligible:
                eligible = self.templates

            template = random.choice(eligible)
            prompt = self._instantiate(template)
            prompts.append(prompt)

        return prompts

    def _instantiate(self, template: TaskTemplate) -> Dict:
        """Create a concrete prompt from a template."""
        # Start with base prompt, maybe use variation prefix
        base = template.base_prompt

        if template.variations and random.random() > 0.5:
            # Replace "Write JCL to" with variation
            prefix = base.split("{")[0].strip()
            variation = random.choice(template.variations)
            base = variation + " " + base[len(prefix):].strip()

        # Fill in parameters
        prompt = base
        for param, options in template.parameters.items():
            value = random.choice(options)
            prompt = prompt.replace("{" + param + "}", value)

        # Maybe add context
        if random.random() > 0.7:
            context = random.choice(CONTEXT_INJECTIONS)
            if context:
                prompt += " " + context

        # Maybe add specific dataset name
        if random.random() > 0.8 and "dataset" in prompt.lower():
            ds = random.choice(DATASET_NAMES)
            prompt += f" Use dataset name {ds}."

        # Determine task type
        if template.category in [TaskCategory.COBOL_BASIC, TaskCategory.COBOL_FILE, TaskCategory.COBOL_TABLE]:
            task_type = "cobol"
        else:
            task_type = "jcl"

        return {
            "prompt": prompt.strip(),
            "category": template.category.value,
            "difficulty": template.difficulty,
            "task_type": task_type,
        }


# =============================================================================
# TRAINING AGENT - Orchestrates RLVR training
# =============================================================================

@dataclass
class TrainingConfig:
    """RLVR training configuration."""
    model_path: str = "data/training/bigiron-ai"  # Base model
    output_dir: str = "data/training/bigiron-rlvr"
    prompts_per_batch: int = 8
    generations_per_prompt: int = 4  # Like Outflank's 7
    max_steps: int = 1000
    learning_rate: float = 1e-6
    difficulty_start: int = 1
    difficulty_max: int = 5
    difficulty_ramp_steps: int = 200  # Steps before increasing difficulty


class RLVRAgent:
    """
    Agent that manages RLVR training loop.

    Flow:
    1. Generate prompts (non-deterministic)
    2. Get LLM completions
    3. Verify each completion on TK5
    4. Compute rewards
    5. Update model with GRPO
    6. Repeat
    """

    def __init__(self, config: TrainingConfig):
        self.config = config
        self.prompt_gen = PromptGenerator()
        self.verifier = TK5Verifier()
        self.step = 0
        self.rewards_history = []

        # Training state
        self.model = None
        self.tokenizer = None
        self.trainer = None

    def current_difficulty(self) -> tuple:
        """Get difficulty range based on training progress."""
        ramp = self.config.difficulty_ramp_steps
        max_d = self.config.difficulty_max
        start_d = self.config.difficulty_start

        if self.step < ramp:
            # Start easy
            d = start_d
        else:
            # Gradually increase
            progress = (self.step - ramp) / ramp
            d = min(start_d + int(progress * (max_d - start_d)), max_d)

        return (start_d, d)

    def generate_prompts(self, n: int) -> List[Dict]:
        """Generate n prompts at current difficulty."""
        difficulty = self.current_difficulty()
        return self.prompt_gen.generate(n=n, difficulty_range=difficulty)

    def get_completions(self, prompts: List[str], n: int = 1) -> List[List[str]]:
        """
        Get LLM completions for prompts.

        Returns: List of lists (multiple completions per prompt)
        """
        if self.model is None:
            # Dry run - return placeholder
            return [["[PLACEHOLDER COMPLETION]" for _ in range(n)] for _ in prompts]

        completions = []
        for prompt in prompts:
            prompt_completions = []
            for _ in range(n):
                # Generate with temperature > 0 for variety
                inputs = self.tokenizer(prompt, return_tensors="pt")
                outputs = self.model.generate(
                    **inputs,
                    max_new_tokens=2048,
                    temperature=0.8,
                    do_sample=True,
                    top_p=0.9,
                )
                text = self.tokenizer.decode(outputs[0], skip_special_tokens=True)
                prompt_completions.append(text[len(prompt):])
            completions.append(prompt_completions)

        return completions

    def verify_completions(self, prompts: List[Dict], completions: List[List[str]]) -> List[List[VerifyResult]]:
        """Verify all completions on TK5."""
        results = []
        for prompt, prompt_completions in zip(prompts, completions):
            prompt_results = []
            for completion in prompt_completions:
                result = self.verifier.verify(
                    llm_output=completion,
                    task_type=prompt["task_type"]
                )
                prompt_results.append(result)
            results.append(prompt_results)
        return results

    def compute_batch_rewards(self, results: List[List[VerifyResult]]) -> List[List[float]]:
        """Convert verification results to GRPO rewards."""
        rewards = []
        for prompt_results in results:
            prompt_rewards = [compute_reward(r) for r in prompt_results]
            rewards.append(prompt_rewards)
            self.rewards_history.extend(prompt_rewards)
        return rewards

    def training_step(self) -> Dict:
        """Execute one training step."""
        self.step += 1

        # 1. Generate prompts
        prompts = self.generate_prompts(self.config.prompts_per_batch)

        # 2. Get completions
        prompt_texts = [p["prompt"] for p in prompts]
        completions = self.get_completions(
            prompt_texts,
            n=self.config.generations_per_prompt
        )

        # 3. Verify
        results = self.verify_completions(prompts, completions)

        # 4. Compute rewards
        rewards = self.compute_batch_rewards(results)

        # 5. GRPO update (if training)
        loss = 0.0
        if self.trainer is not None:
            # TRL GRPO training step
            # This is simplified - real impl needs proper batch formatting
            pass

        # Stats
        flat_rewards = [r for pr in rewards for r in pr]
        return {
            "step": self.step,
            "difficulty": self.current_difficulty(),
            "prompts": len(prompts),
            "completions": len(flat_rewards),
            "mean_reward": sum(flat_rewards) / len(flat_rewards) if flat_rewards else 0,
            "max_reward": max(flat_rewards) if flat_rewards else 0,
            "success_rate": sum(1 for r in flat_rewards if r > 0.5) / len(flat_rewards) if flat_rewards else 0,
            "loss": loss,
        }

    def train(self, steps: int = None):
        """Main training loop."""
        steps = steps or self.config.max_steps

        print(f"Starting RLVR training for {steps} steps...")
        print(f"Model: {self.config.model_path}")
        print(f"Prompts/batch: {self.config.prompts_per_batch}")
        print(f"Generations/prompt: {self.config.generations_per_prompt}")
        print()

        for _ in range(steps):
            stats = self.training_step()

            if self.step % 10 == 0:
                print(f"Step {stats['step']:4d} | "
                      f"Diff: {stats['difficulty']} | "
                      f"Reward: {stats['mean_reward']:.3f} | "
                      f"Success: {stats['success_rate']*100:.1f}% | "
                      f"Loss: {stats['loss']:.4f}")

            if self.step % 100 == 0:
                self._save_checkpoint()

        self._save_checkpoint()
        print("\nTraining complete!")

    def _save_checkpoint(self):
        """Save model checkpoint."""
        if self.model is not None:
            path = f"{self.config.output_dir}/checkpoint-{self.step}"
            self.model.save_pretrained(path)
            self.tokenizer.save_pretrained(path)
            print(f"Saved checkpoint: {path}")

    def dry_run(self, n: int = 5):
        """Generate and show prompts without training."""
        print(f"Generating {n} sample prompts...\n")

        prompts = self.generate_prompts(n)
        for i, p in enumerate(prompts):
            print(f"[{i+1}] Category: {p['category']}, Difficulty: {p['difficulty']}, Type: {p['task_type']}")
            print(f"    Prompt: {p['prompt']}")
            print()


# =============================================================================
# CLI
# =============================================================================

def main():
    parser = argparse.ArgumentParser(description="RLVR Training Agent for BigIron-AI")
    parser.add_argument("--dry-run", action="store_true", help="Generate prompts without training")
    parser.add_argument("--train", action="store_true", help="Run RLVR training")
    parser.add_argument("--eval", action="store_true", help="Evaluate model")
    parser.add_argument("--steps", type=int, default=100, help="Training steps")
    parser.add_argument("--prompts", type=int, default=10, help="Prompts for dry-run")

    args = parser.parse_args()

    config = TrainingConfig()
    agent = RLVRAgent(config)

    if args.dry_run:
        agent.dry_run(n=args.prompts)

    elif args.train:
        if not HAS_TRL:
            print("Error: TRL not installed. Run: pip install trl transformers torch")
            sys.exit(1)
        agent.train(steps=args.steps)

    elif args.eval:
        print("Evaluation mode - generating and verifying...")
        prompts = agent.generate_prompts(args.prompts)
        for p in prompts:
            print(f"\nPrompt: {p['prompt']}")
            # Would need model loaded to actually evaluate

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
