"""
Application Configuration

Centralized configuration management for the Mainframe AI Assistant.
"""

import os
import logging
from dataclasses import dataclass, field
from typing import Optional, Dict

logger = logging.getLogger(__name__)


@dataclass
class Config:
    """Application configuration."""
    
    # Base paths
    BASE_DIR: str = field(default_factory=lambda: os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    
    # Ollama settings
    OLLAMA_URL: str = field(default_factory=lambda: os.getenv("OLLAMA_URL", "http://localhost:11434"))
    OLLAMA_MODEL: str = field(default_factory=lambda: os.getenv("OLLAMA_MODEL", "llama3.1:8b"))
    
    # Server settings
    HOST: str = "127.0.0.1"
    PORT: int = 8080
    
    # GPU settings (populated during __post_init__)
    GPU_ENABLED: bool = False
    GPU_NAME: str = ""
    GPU_VRAM_GB: float = 0.0
    GPU_TIER: str = "cpu"
    GPU_OLLAMA_OPTIONS: Dict = field(default_factory=dict)
    GPU_CODE_MODEL: str = ""  # Dedicated code model for ultra tier dual-model
    
    # Directory paths (computed after BASE_DIR)
    def __post_init__(self):
        self.STATIC_DIR = os.path.join(self.BASE_DIR, "static")
        self.TEMPLATES_DIR = os.path.join(self.BASE_DIR, "templates")
        self.LAB_DATA_DIR = os.path.join(self.BASE_DIR, "lab_data")
        self.DEMO_DATA_DIR = os.path.join(self.BASE_DIR, "docs", "demo")
        self.RAG_DIR = os.path.join(self.BASE_DIR, "rag_data")
        self.SCREENCAPS_DIR = os.path.join(self.BASE_DIR, "screencaps")
        self.GRAPH_DIR = os.path.join(self.BASE_DIR, "trust_graph_data")
        
        # Ensure directories exist
        for dir_path in [self.SCREENCAPS_DIR, self.RAG_DIR, self.GRAPH_DIR]:
            os.makedirs(dir_path, exist_ok=True)
        
        # Detect GPU and auto-configure
        self._detect_and_configure_gpu()
    
    def _detect_and_configure_gpu(self):
        """Detect GPU and set optimal configuration."""
        try:
            from app.gpu import get_gpu_info, get_recommended_model, get_gpu_ollama_options
            
            gpu = get_gpu_info()
            self.GPU_ENABLED = gpu.is_available
            self.GPU_NAME = gpu.name
            self.GPU_VRAM_GB = gpu.vram_total_gb
            self.GPU_TIER = gpu.tier if gpu.is_available else "cpu"
            self.GPU_OLLAMA_OPTIONS = get_gpu_ollama_options(gpu)
            
            # Auto-select model if user hasn't explicitly set one via env var
            if not os.getenv("OLLAMA_MODEL"):
                recommended = get_recommended_model(gpu)
                self.OLLAMA_MODEL = recommended
                logger.info(f"GPU auto-selected model: {recommended} (tier: {self.GPU_TIER})")
            
            if gpu.is_available:
                logger.info(
                    f"GPU enabled: {gpu.name} | {gpu.vram_total_gb}GB VRAM | "
                    f"Tier: {self.GPU_TIER} | Model: {self.OLLAMA_MODEL}"
                )
            else:
                logger.info("No GPU detected — using CPU inference")
                
        except Exception as e:
            logger.warning(f"GPU detection failed, falling back to CPU: {e}")
            self.GPU_ENABLED = False
            self.GPU_TIER = "cpu"
            self.GPU_OLLAMA_OPTIONS = {"num_gpu": 0, "num_thread": 8, "num_ctx": 4096}


# Global configuration instance
config = Config()


def get_config() -> Config:
    """Get the global configuration instance."""
    return config


def update_model(model: str):
    """Update the Ollama model."""
    config.OLLAMA_MODEL = model


def get_gpu_status() -> Dict:
    """Get current GPU status for API/UI consumption."""
    try:
        from app.gpu import get_gpu_info, get_model_recommendations
        gpu = get_gpu_info(force_refresh=True)
        return get_model_recommendations(gpu)
    except Exception as e:
        return {
            "gpu": {"is_available": False, "name": "Detection failed"},
            "tier": "cpu",
            "error": str(e),
        }
