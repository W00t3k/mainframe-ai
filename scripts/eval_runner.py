#!/usr/bin/env python3
"""
BigIron Model Evaluation Runner

Runs evaluation test cases against different model versions and compares results.
Usage: python scripts/eval_runner.py [--models model1,model2] [--eval-file path]
"""

import json
import subprocess
import argparse
import sys
from pathlib import Path
from typing import List, Dict, Any
from datetime import datetime


def run_ollama_prompt(model: str, prompt: str, timeout: int = 60) -> str:
    """Run a prompt against an Ollama model and return the response."""
    try:
        result = subprocess.run(
            ["ollama", "run", model, prompt],
            capture_output=True,
            text=True,
            timeout=timeout
        )
        return result.stdout.strip()
    except subprocess.TimeoutExpired:
        return "[TIMEOUT]"
    except Exception as e:
        return f"[ERROR: {str(e)}]"


def check_keywords(response: str, expected: List[str]) -> Dict[str, bool]:
    """Check which expected keywords appear in the response."""
    response_lower = response.lower()
    results = {}
    for keyword in expected:
        # Check for keyword (case-insensitive)
        results[keyword] = keyword.lower() in response_lower
    return results


def score_response(keyword_results: Dict[str, bool]) -> float:
    """Calculate score as percentage of keywords found."""
    if not keyword_results:
        return 0.0
    found = sum(1 for v in keyword_results.values() if v)
    return (found / len(keyword_results)) * 100


def load_eval_file(filepath: str) -> List[Dict[str, Any]]:
    """Load evaluation test cases from JSONL file."""
    tests = []
    with open(filepath, 'r') as f:
        for line in f:
            line = line.strip()
            if line:
                tests.append(json.loads(line))
    return tests


def run_evaluation(models: List[str], eval_file: str, verbose: bool = False) -> Dict[str, Any]:
    """Run evaluation against all models and return results."""
    tests = load_eval_file(eval_file)
    print(f"Loaded {len(tests)} test cases from {eval_file}")

    results = {model: {"scores": [], "details": []} for model in models}

    for i, test in enumerate(tests):
        test_id = test.get("id", f"test_{i+1}")
        prompt = test["prompt"]
        expected = test.get("expected_keywords", [])
        category = test.get("category", "general")

        print(f"\n[{i+1}/{len(tests)}] {test_id} ({category})")
        print(f"  Prompt: {prompt[:60]}...")

        for model in models:
            print(f"  Running {model}...", end=" ", flush=True)
            response = run_ollama_prompt(model, prompt)
            keyword_results = check_keywords(response, expected)
            score = score_response(keyword_results)

            results[model]["scores"].append(score)
            results[model]["details"].append({
                "test_id": test_id,
                "category": category,
                "prompt": prompt,
                "response": response[:500] + "..." if len(response) > 500 else response,
                "keywords": keyword_results,
                "score": score
            })

            found = sum(1 for v in keyword_results.values() if v)
            print(f"Score: {score:.0f}% ({found}/{len(expected)} keywords)")

            if verbose:
                print(f"    Response: {response[:200]}...")

    return results


def calculate_summary(results: Dict[str, Any]) -> Dict[str, Dict[str, float]]:
    """Calculate summary statistics for each model."""
    summary = {}

    for model, data in results.items():
        scores = data["scores"]
        if scores:
            summary[model] = {
                "avg_score": sum(scores) / len(scores),
                "min_score": min(scores),
                "max_score": max(scores),
                "total_tests": len(scores),
                "perfect_scores": sum(1 for s in scores if s == 100),
                "zero_scores": sum(1 for s in scores if s == 0)
            }

            # Category breakdown
            categories = {}
            for detail in data["details"]:
                cat = detail["category"]
                if cat not in categories:
                    categories[cat] = []
                categories[cat].append(detail["score"])

            summary[model]["by_category"] = {
                cat: sum(scores)/len(scores)
                for cat, scores in categories.items()
            }

    return summary


def print_results(summary: Dict[str, Dict[str, float]], results: Dict[str, Any]):
    """Print formatted results table."""
    print("\n" + "="*70)
    print("EVALUATION RESULTS")
    print("="*70)

    # Overall scores table
    print("\nOverall Scores:")
    print("-"*50)
    print(f"{'Model':<25} {'Avg Score':>10} {'Perfect':>8} {'Zero':>6}")
    print("-"*50)

    for model, stats in sorted(summary.items(), key=lambda x: x[1]["avg_score"], reverse=True):
        print(f"{model:<25} {stats['avg_score']:>9.1f}% {stats['perfect_scores']:>7} {stats['zero_scores']:>6}")

    # Category breakdown
    print("\nScores by Category:")
    print("-"*70)

    categories = set()
    for stats in summary.values():
        categories.update(stats.get("by_category", {}).keys())

    header = f"{'Model':<20}"
    for cat in sorted(categories):
        header += f" {cat:>10}"
    print(header)
    print("-"*70)

    for model, stats in sorted(summary.items(), key=lambda x: x[1]["avg_score"], reverse=True):
        row = f"{model:<20}"
        for cat in sorted(categories):
            score = stats.get("by_category", {}).get(cat, 0)
            row += f" {score:>9.1f}%"
        print(row)

    # Model comparison
    if len(summary) >= 2:
        models = list(summary.keys())
        print(f"\nComparison: {models[0]} vs {models[1]}")
        print("-"*50)
        diff = summary[models[0]]["avg_score"] - summary[models[1]]["avg_score"]
        if diff > 0:
            print(f"{models[0]} scores {diff:.1f}% higher on average")
        elif diff < 0:
            print(f"{models[1]} scores {-diff:.1f}% higher on average")
        else:
            print("Models have identical average scores")


def save_results(results: Dict[str, Any], summary: Dict[str, Dict[str, float]], output_dir: str):
    """Save detailed results to JSON file."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = Path(output_dir) / f"eval_results_{timestamp}.json"

    output_data = {
        "timestamp": timestamp,
        "summary": summary,
        "detailed_results": results
    }

    with open(output_file, 'w') as f:
        json.dump(output_data, f, indent=2)

    print(f"\nDetailed results saved to: {output_file}")


def main():
    parser = argparse.ArgumentParser(description="BigIron Model Evaluation Runner")
    parser.add_argument(
        "--models",
        default="bigiron-v4:latest,mistral:latest",
        help="Comma-separated list of models to evaluate"
    )
    parser.add_argument(
        "--eval-file",
        default="data/evals/bigiron_v4_tests.jsonl",
        help="Path to evaluation JSONL file"
    )
    parser.add_argument(
        "--output-dir",
        default="data/evals",
        help="Directory to save results"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Show detailed output"
    )
    parser.add_argument(
        "--quick",
        action="store_true",
        help="Run only first 5 tests for quick check"
    )

    args = parser.parse_args()

    models = [m.strip() for m in args.models.split(",")]
    print(f"Evaluating models: {', '.join(models)}")

    # Check Ollama is available
    try:
        subprocess.run(["ollama", "list"], capture_output=True, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("ERROR: Ollama not found or not running")
        sys.exit(1)

    # Check eval file exists
    if not Path(args.eval_file).exists():
        print(f"ERROR: Eval file not found: {args.eval_file}")
        sys.exit(1)

    # Run evaluation
    results = run_evaluation(models, args.eval_file, verbose=args.verbose)

    # Calculate and print summary
    summary = calculate_summary(results)
    print_results(summary, results)

    # Save results
    save_results(results, summary, args.output_dir)

    return 0


if __name__ == "__main__":
    sys.exit(main())
