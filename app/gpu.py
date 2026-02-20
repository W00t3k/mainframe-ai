"""
GPU Detection and Management

Detects NVIDIA GPU capabilities and recommends optimal model configurations.
Designed for H200 (141GB VRAM) but auto-detects any NVIDIA GPU.
"""

import os
import json
import shutil
import logging
import subprocess
from dataclasses import dataclass, field
from typing import Optional, Dict, List, Tuple

logger = logging.getLogger(__name__)


@dataclass
class GPUInfo:
    """Information about a detected GPU."""
    name: str = "Unknown"
    vram_total_mb: int = 0
    vram_free_mb: int = 0
    vram_used_mb: int = 0
    gpu_utilization: int = 0
    temperature: int = 0
    driver_version: str = ""
    cuda_version: str = ""
    compute_capability: str = ""
    gpu_count: int = 0
    power_draw_w: float = 0.0
    power_limit_w: float = 0.0

    @property
    def vram_total_gb(self) -> float:
        return round(self.vram_total_mb / 1024, 1)

    @property
    def vram_free_gb(self) -> float:
        return round(self.vram_free_mb / 1024, 1)

    @property
    def vram_used_gb(self) -> float:
        return round(self.vram_used_mb / 1024, 1)

    @property
    def is_available(self) -> bool:
        return self.vram_total_mb > 0

    @property
    def tier(self) -> str:
        """Classify GPU into performance tiers."""
        vram_gb = self.vram_total_gb
        if vram_gb >= 80:
            return "ultra"      # H100/H200/A100-80GB — run 70B+ models
        elif vram_gb >= 40:
            return "high"       # A100-40GB, A6000 — run 70B quantized
        elif vram_gb >= 20:
            return "medium"     # RTX 4090/3090 — run 13B-34B models
        elif vram_gb >= 8:
            return "low"        # RTX 4070/3060 — run 7B-8B models
        else:
            return "minimal"    # Older GPUs — run 3B or smaller

    def to_dict(self) -> Dict:
        return {
            "name": self.name,
            "vram_total_gb": self.vram_total_gb,
            "vram_free_gb": self.vram_free_gb,
            "vram_used_gb": self.vram_used_gb,
            "gpu_utilization_pct": self.gpu_utilization,
            "temperature_c": self.temperature,
            "driver_version": self.driver_version,
            "cuda_version": self.cuda_version,
            "compute_capability": self.compute_capability,
            "gpu_count": self.gpu_count,
            "power_draw_w": self.power_draw_w,
            "power_limit_w": self.power_limit_w,
            "tier": self.tier,
            "is_available": self.is_available,
        }


# ── Model Recommendations by GPU Tier ──────────────────────────────────────

# Models ranked by quality within each tier.
# With H200 141GB VRAM, "ultra" tier is selected — top-tier models fit entirely in VRAM.
GPU_MODEL_TIERS = {
    "ultra": {
        "description": "H100/H200/A100-80GB — Full 70B+ models in VRAM",
        "recommended": [
            {
                "name": "deepseek-coder-v2:236b",
                "vram_gb": 130,
                "description": "DeepSeek Coder V2 236B — Best coding model available, "
                               "mixture-of-experts, exceptional at code generation and analysis",
                "use_case": "code_expert",
            },
            {
                "name": "llama3.1:70b",
                "vram_gb": 40,
                "description": "Llama 3.1 70B — Meta's flagship, excellent general + code reasoning",
                "use_case": "general",
            },
            {
                "name": "deepseek-v2.5:236b",
                "vram_gb": 130,
                "description": "DeepSeek V2.5 236B — Top-tier general + code, MoE architecture",
                "use_case": "general_expert",
            },
            {
                "name": "qwen2.5:72b",
                "vram_gb": 42,
                "description": "Qwen 2.5 72B — Strong multilingual and code capabilities",
                "use_case": "general",
            },
            {
                "name": "codellama:70b",
                "vram_gb": 40,
                "description": "Code Llama 70B — Dedicated code model, strong at COBOL/JCL",
                "use_case": "code",
            },
            {
                "name": "mixtral:8x22b",
                "vram_gb": 80,
                "description": "Mixtral 8x22B — MoE, fast inference with excellent quality",
                "use_case": "general_fast",
            },
            {
                "name": "llama3.1:8b",
                "vram_gb": 5,
                "description": "Llama 3.1 8B — Lightweight fallback, blazing fast on GPU",
                "use_case": "fast_fallback",
            },
        ],
        "default": "llama3.1:70b",
        "ollama_options": {
            "num_gpu": 99,          # Offload all layers to GPU
            "num_thread": 24,       # Match vCPU count
            "num_ctx": 32768,       # Large context window — H200 has the VRAM
            "num_batch": 2048,      # Large batch for throughput
            "f16_kv": True,         # FP16 KV cache — faster on H200
            "num_keep": 4096,       # Keep more tokens in context
            "use_mmap": True,       # Memory-mapped model loading
            "use_mlock": True,      # Lock model in memory — prevent swapping
        },
    },
    "high": {
        "description": "A100-40GB / A6000 — 70B quantized or 34B full",
        "recommended": [
            {
                "name": "llama3.1:70b-instruct-q4_0",
                "vram_gb": 38,
                "description": "Llama 3.1 70B Q4 — Quantized to fit 40GB, still excellent",
                "use_case": "general",
            },
            {
                "name": "deepseek-coder-v2:16b",
                "vram_gb": 10,
                "description": "DeepSeek Coder V2 16B — Great coding in smaller footprint",
                "use_case": "code",
            },
            {
                "name": "qwen2.5:32b",
                "vram_gb": 20,
                "description": "Qwen 2.5 32B — Strong general purpose",
                "use_case": "general",
            },
            {
                "name": "codellama:34b",
                "vram_gb": 20,
                "description": "Code Llama 34B — Solid code model",
                "use_case": "code",
            },
        ],
        "default": "llama3.1:70b-instruct-q4_0",
        "ollama_options": {
            "num_gpu": 99,
            "num_thread": 16,
            "num_ctx": 16384,
            "num_batch": 1024,
            "f16_kv": True,
            "use_mmap": True,
            "use_mlock": True,
        },
    },
    "medium": {
        "description": "RTX 4090/3090 (20-24GB) — 13B-34B models",
        "recommended": [
            {
                "name": "deepseek-coder-v2:16b",
                "vram_gb": 10,
                "description": "DeepSeek Coder V2 16B — Best code model for this tier",
                "use_case": "code",
            },
            {
                "name": "llama3.1:8b",
                "vram_gb": 5,
                "description": "Llama 3.1 8B — Fast and capable general model",
                "use_case": "general",
            },
            {
                "name": "codellama:13b",
                "vram_gb": 8,
                "description": "Code Llama 13B — Good code generation",
                "use_case": "code",
            },
        ],
        "default": "deepseek-coder-v2:16b",
        "ollama_options": {
            "num_gpu": 99,
            "num_thread": 8,
            "num_ctx": 8192,
            "num_batch": 512,
            "f16_kv": True,
            "use_mmap": True,
        },
    },
    "low": {
        "description": "RTX 4070/3060 (8-12GB) — 7B-8B models",
        "recommended": [
            {
                "name": "llama3.1:8b",
                "vram_gb": 5,
                "description": "Llama 3.1 8B — Best balance of quality and speed",
                "use_case": "general",
            },
            {
                "name": "deepseek-coder:6.7b",
                "vram_gb": 4,
                "description": "DeepSeek Coder 6.7B — Solid code model",
                "use_case": "code",
            },
        ],
        "default": "llama3.1:8b",
        "ollama_options": {
            "num_gpu": 99,
            "num_thread": 8,
            "num_ctx": 4096,
            "num_batch": 256,
            "use_mmap": True,
        },
    },
    "minimal": {
        "description": "Older/small GPUs (<8GB) — 3B or smaller",
        "recommended": [
            {
                "name": "llama3.2:3b",
                "vram_gb": 2,
                "description": "Llama 3.2 3B — Lightweight but capable",
                "use_case": "general",
            },
            {
                "name": "tinyllama",
                "vram_gb": 1,
                "description": "TinyLlama — Minimal resource usage",
                "use_case": "minimal",
            },
        ],
        "default": "llama3.2:3b",
        "ollama_options": {
            "num_gpu": 99,
            "num_thread": 4,
            "num_ctx": 2048,
            "num_batch": 128,
        },
    },
    "cpu": {
        "description": "No GPU detected — CPU-only inference",
        "recommended": [
            {
                "name": "llama3.1:8b",
                "vram_gb": 0,
                "description": "Llama 3.1 8B — Best quality on CPU",
                "use_case": "general",
            },
            {
                "name": "mistral:7b",
                "vram_gb": 0,
                "description": "Mistral 7B — Fast and capable",
                "use_case": "general",
            },
            {
                "name": "deepseek-coder:6.7b",
                "vram_gb": 0,
                "description": "DeepSeek Coder 6.7B — Code-focused",
                "use_case": "code",
            },
            {
                "name": "phi3:mini",
                "vram_gb": 0,
                "description": "Microsoft Phi-3 Mini — Compact and smart",
                "use_case": "general",
            },
            {
                "name": "llama3.2:3b",
                "vram_gb": 0,
                "description": "Llama 3.2 3B — Lightweight, faster on CPU",
                "use_case": "fast",
            },
            {
                "name": "gemma2:2b",
                "vram_gb": 0,
                "description": "Google Gemma 2B — Small and efficient",
                "use_case": "minimal",
            },
            {
                "name": "tinyllama",
                "vram_gb": 0,
                "description": "TinyLlama — Minimal resources",
                "use_case": "minimal",
            },
        ],
        "default": "llama3.1:8b",
        "ollama_options": {
            "num_gpu": 0,
            "num_thread": 8,
            "num_ctx": 4096,
            "num_batch": 256,
        },
    },
}


def detect_gpu() -> GPUInfo:
    """
    Detect NVIDIA GPU using nvidia-smi.
    Returns GPUInfo with all available metrics.
    """
    gpu = GPUInfo()

    if not shutil.which("nvidia-smi"):
        logger.info("nvidia-smi not found — no NVIDIA GPU detected")
        return gpu

    try:
        # Query comprehensive GPU info
        result = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=name,memory.total,memory.free,memory.used,"
                "utilization.gpu,temperature.gpu,driver_version,"
                "compute_cap,count,power.draw,power.limit",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )

        if result.returncode != 0:
            logger.warning(f"nvidia-smi failed: {result.stderr}")
            return gpu

        line = result.stdout.strip().split("\n")[0]
        parts = [p.strip() for p in line.split(",")]

        if len(parts) >= 9:
            gpu.name = parts[0]
            gpu.vram_total_mb = int(float(parts[1]))
            gpu.vram_free_mb = int(float(parts[2]))
            gpu.vram_used_mb = int(float(parts[3]))
            gpu.gpu_utilization = int(float(parts[4])) if parts[4] not in ("[N/A]", "") else 0
            gpu.temperature = int(float(parts[5])) if parts[5] not in ("[N/A]", "") else 0
            gpu.driver_version = parts[6]
            gpu.compute_capability = parts[7]
            gpu.gpu_count = int(parts[8])
            if len(parts) >= 11:
                gpu.power_draw_w = float(parts[9]) if parts[9] not in ("[N/A]", "") else 0.0
                gpu.power_limit_w = float(parts[10]) if parts[10] not in ("[N/A]", "") else 0.0

        # Get CUDA version separately
        cuda_result = subprocess.run(
            ["nvidia-smi", "--query-gpu=driver_version", "--format=csv,noheader"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        # Parse CUDA version from nvidia-smi header
        header_result = subprocess.run(
            ["nvidia-smi"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if header_result.returncode == 0:
            for hline in header_result.stdout.split("\n"):
                if "CUDA Version" in hline:
                    cuda_part = hline.split("CUDA Version:")[1].strip().split()[0]
                    gpu.cuda_version = cuda_part.rstrip("|").strip()
                    break

        logger.info(
            f"GPU detected: {gpu.name} | {gpu.vram_total_gb}GB VRAM | "
            f"Tier: {gpu.tier} | CUDA: {gpu.cuda_version}"
        )

    except subprocess.TimeoutExpired:
        logger.warning("nvidia-smi timed out")
    except Exception as e:
        logger.warning(f"GPU detection error: {e}")

    return gpu


def get_recommended_model(gpu: GPUInfo) -> str:
    """Get the recommended default model for the detected GPU."""
    tier = gpu.tier if gpu.is_available else "cpu"
    tier_config = GPU_MODEL_TIERS.get(tier, GPU_MODEL_TIERS["cpu"])
    return tier_config["default"]


def get_gpu_ollama_options(gpu: GPUInfo) -> Dict:
    """Get optimized Ollama options for the detected GPU."""
    tier = gpu.tier if gpu.is_available else "cpu"
    tier_config = GPU_MODEL_TIERS.get(tier, GPU_MODEL_TIERS["cpu"])
    return dict(tier_config["ollama_options"])


def get_model_recommendations(gpu: GPUInfo) -> Dict:
    """Get full model recommendations for the detected GPU."""
    tier = gpu.tier if gpu.is_available else "cpu"
    tier_config = GPU_MODEL_TIERS.get(tier, GPU_MODEL_TIERS["cpu"])
    return {
        "gpu": gpu.to_dict(),
        "tier": tier,
        "tier_description": tier_config["description"],
        "default_model": tier_config["default"],
        "recommended_models": tier_config["recommended"],
        "ollama_options": tier_config["ollama_options"],
    }


def get_ollama_gpu_env() -> Dict[str, str]:
    """
    Get environment variables to optimize Ollama for GPU usage.
    Set these before starting Ollama for best performance.
    """
    gpu = detect_gpu()
    env = {}

    if gpu.is_available:
        # Tell Ollama to use all available GPUs
        env["CUDA_VISIBLE_DEVICES"] = "0"
        # Keep models loaded longer on GPU (H200 has plenty of VRAM)
        if gpu.tier == "ultra":
            env["OLLAMA_KEEP_ALIVE"] = "60m"
            env["OLLAMA_NUM_PARALLEL"] = "4"    # Handle 4 concurrent requests
            env["OLLAMA_MAX_LOADED_MODELS"] = "3"  # Keep 3 models in VRAM simultaneously
            env["OLLAMA_FLASH_ATTENTION"] = "1"    # Enable flash attention for H200
        elif gpu.tier == "high":
            env["OLLAMA_KEEP_ALIVE"] = "30m"
            env["OLLAMA_NUM_PARALLEL"] = "2"
            env["OLLAMA_MAX_LOADED_MODELS"] = "2"
            env["OLLAMA_FLASH_ATTENTION"] = "1"
        else:
            env["OLLAMA_KEEP_ALIVE"] = "10m"
            env["OLLAMA_NUM_PARALLEL"] = "1"
            env["OLLAMA_MAX_LOADED_MODELS"] = "1"
    else:
        env["OLLAMA_KEEP_ALIVE"] = "5m"

    return env


# ── Singleton GPU info ──────────────────────────────────────────────────────

_gpu_info: Optional[GPUInfo] = None


def get_gpu_info(force_refresh: bool = False) -> GPUInfo:
    """Get cached GPU info (detect once, reuse)."""
    global _gpu_info
    if _gpu_info is None or force_refresh:
        _gpu_info = detect_gpu()
    return _gpu_info
