"""
Application Configuration

Centralized configuration management for the Mainframe AI Assistant.
"""

import os
from dataclasses import dataclass, field
from typing import Optional


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


# Global configuration instance
config = Config()


def get_config() -> Config:
    """Get the global configuration instance."""
    return config


def update_model(model: str):
    """Update the Ollama model."""
    config.OLLAMA_MODEL = model
