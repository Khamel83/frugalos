"""
Prompt optimization and management system for frugalos.

This module provides:
- Schema-aware prompt templates
- Prompt caching and versioning
- Few-shot example generation
- Automatic prompt optimization
- Task-specific template selection
"""

from .template_manager import PromptTemplateManager, create_template_manager_from_config
from .templates import PromptTemplate, get_template, list_templates, get_default_template

__all__ = [
    "PromptTemplateManager",
    "create_template_manager_from_config",
    "PromptTemplate",
    "get_template",
    "list_templates",
    "get_default_template"
]