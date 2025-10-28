"""
Configuration for Local-First Routing
"""
import os
from typing import Dict
from dotenv import load_dotenv

# Load environment variables from hermes/.env
env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env')
load_dotenv(env_path)

# Model costs from real testing data
MODEL_COSTS = {
    "local_models": {
        "llama3.2:3b": {
            "cost": 0.0,
            "quality_base": 8.7,
            "time": 1.27,
            "specialties": ["quick_qa", "conversation", "simple_tasks"]
        },
        "qwen2.5-coder:7b": {
            "cost": 0.0,
            "quality_base": 7.9,
            "time": 4.47,
            "specialties": ["code_generation", "debugging", "technical_tasks"]
        },
        "gemma2:latest": {
            "cost": 0.0,
            "quality_base": 7.9,
            "time": 6.14,
            "specialties": ["analysis", "reasoning", "data_processing"]
        },
        "llama3.1:8b-instruct-q8_0": {
            "cost": 0.0,
            "quality_base": 6.6,
            "time": 14.51,
            "specialties": ["backup", "complex_tasks", "analysis"]
        }
    },
    "premium_models": {
        "anthropic/claude-3.5-sonnet": {
            "input_per_million": 3.0,
            "output_per_million": 15.0,
            "quality": 9.5,
            "specialties": ["code_review", "analysis", "writing"]
        },
        "openai/gpt-4": {
            "input_per_million": 30.0,
            "output_per_million": 60.0,
            "quality": 9.9,
            "specialties": ["complex_reasoning", "architecture", "debugging"]
        },
        "anthropic/claude-3-opus": {
            "input_per_million": 15.0,
            "output_per_million": 75.0,
            "quality": 9.8,
            "specialties": ["creative", "analysis", "research"]
        }
    }
}

# Session configuration
SESSION_CONFIG = {
    "context_transfer_cost": 0.006,  # Cost to move context to cloud
    "average_session_tasks": 25,
    "session_continuation_cost": 0.15,  # Total additional cost for staying in cloud
    "context_loss_risk": 0.1
}

# Quality thresholds
QUALITY_THRESHOLDS = {
    "target": 9.0,  # Target quality score
    "acceptable": 7.0,  # Acceptable quality for less critical tasks
    "minimum": 5.0  # Minimum viable quality
}

# API configuration
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

# Database
DATABASE_PATH = os.getenv("ROUTING_DB_PATH", "./hermes/data/routing.db")
