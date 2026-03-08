#!/usr/bin/env python3
"""
Mainframe AI Assistant - Entry Point

Run the web application server.
Auto-detects GPU and selects optimal model.
"""

import argparse
import os
import sys
import uvicorn

# Add tools/ directory to Python path so lazy imports (agent_tools, rag_engine, etc.) still resolve
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "tools"))

from app.config import get_config, update_model


def _load_env():
    """Load .env file into os.environ (no dependency needed)."""
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    if not os.path.exists(env_path):
        return
    with open(env_path, 'r') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue
            key, val = line.split('=', 1)
            key, val = key.strip(), val.strip()
            if val and key not in os.environ:
                os.environ[key] = val


def main():
    """Main entry point for the application."""
    _load_env()
    parser = argparse.ArgumentParser(description="Mainframe AI Assistant Web App")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind to")
    parser.add_argument("--port", type=int, default=8080, help="Port to bind to")
    parser.add_argument("--model", default=None, help="Ollama model to use (auto-detected if not set)")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload")
    parser.add_argument("--gpu-info", action="store_true", help="Show GPU info and recommended models, then exit")
    parser.add_argument("--no-gpu", action="store_true", help="Disable GPU auto-detection, force CPU mode")
    args = parser.parse_args()

    # Update configuration
    config = get_config()
    config.HOST = args.host
    config.PORT = args.port

    # Handle --no-gpu: force CPU mode
    if args.no_gpu:
        config.GPU_ENABLED = False
        config.GPU_TIER = "cpu"
        config.GPU_OLLAMA_OPTIONS = {"num_gpu": 0, "num_thread": 8, "num_ctx": 4096}
        if not args.model:
            update_model("llama3.1:8b")

    # Handle --gpu-info: print GPU details and exit
    if args.gpu_info:
        _print_gpu_info(config)
        return

    # Override model if explicitly provided
    if args.model:
        update_model(args.model)

    # Build GPU status line for banner
    if config.GPU_ENABLED:
        gpu_line = f"GPU: {config.GPU_NAME} ({config.GPU_VRAM_GB}GB VRAM)"
        tier_line = f"Tier: {config.GPU_TIER.upper()} — GPU-accelerated inference"
    else:
        gpu_line = "GPU: Not detected — CPU inference"
        tier_line = "Tier: CPU — install NVIDIA drivers for GPU acceleration"

    print(f"""
╔════════════════════════════════════════════════════════════════╗
║       Mainframe AI Assistant — LOCAL LLM Edition              ║
╠════════════════════════════════════════════════════════════════╣
║  Landing Page:  http://{args.host}:{args.port}/
║  Chat:          http://{args.host}:{args.port}/chat
╠════════════════════════════════════════════════════════════════╣
║  LLM Backend:   Ollama ({config.OLLAMA_MODEL})
║  {gpu_line}
║  {tier_line}
╠════════════════════════════════════════════════════════════════╣
║  No API key required! Runs 100% locally.                      ║
║  Web Terminal: Type in browser, no shell needed!              ║
╚════════════════════════════════════════════════════════════════╝
    """)

    uvicorn.run(
        "app.main:app",
        host=args.host,
        port=args.port,
        reload=args.reload
    )


def _print_gpu_info(config):
    """Print detailed GPU info and model recommendations."""
    try:
        from app.gpu import get_gpu_info, GPU_MODEL_TIERS
        gpu = get_gpu_info(force_refresh=True)
    except Exception as e:
        print(f"GPU detection error: {e}")
        return

    tier = gpu.tier if gpu.is_available else "cpu"
    tier_config = GPU_MODEL_TIERS.get(tier, GPU_MODEL_TIERS["cpu"])

    print(f"""
╔════════════════════════════════════════════════════════════════╗
║                     GPU Information                           ║
╠════════════════════════════════════════════════════════════════╣
║  GPU:       {gpu.name}
║  VRAM:      {gpu.vram_total_gb} GB total / {gpu.vram_free_gb} GB free
║  Driver:    {gpu.driver_version}
║  CUDA:      {gpu.cuda_version}
║  Tier:      {tier.upper()} — {tier_config['description']}
║  GPU Count: {gpu.gpu_count}
╠════════════════════════════════════════════════════════════════╣
║  Default Model: {tier_config['default']}
║
║  Recommended Models:""")

    for m in tier_config["recommended"]:
        marker = " ← DEFAULT" if m["name"] == tier_config["default"] else ""
        print(f"║    • {m['name']} ({m['vram_gb']}GB){marker}")
        print(f"║      {m['description']}")

    print(f"""║
╠════════════════════════════════════════════════════════════════╣
║  Ollama Options (auto-configured):""")
    for k, v in tier_config["ollama_options"].items():
        print(f"║    {k}: {v}")

    print(f"""║
╠════════════════════════════════════════════════════════════════╣
║  Usage:
║    python run.py                          # Auto-detect GPU & model
║    python run.py --model llama3.1:70b      # Override model
║    python run.py --model deepseek-coder-v2:236b  # DeepSeek Coder
║    python run.py --no-gpu                  # Force CPU mode
╚════════════════════════════════════════════════════════════════╝
    """)


if __name__ == "__main__":
    main()
