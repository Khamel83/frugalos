"""
Prompt Template Manager for frugalos.

This module manages the creation, caching, and versioning of prompts
using the template system. It integrates with the existing cache infrastructure
for performance optimization.
"""

from __future__ import annotations
import json
import hashlib
import time
from pathlib import Path
from typing import Dict, List, Optional, Any
import yaml

from .templates import PromptTemplate, get_template, DEFAULT_TEMPLATES

class SimpleCache:
    """Simple in-memory cache with TTL for prompt caching."""

    def __init__(self, default_ttl_seconds: int = 3600):
        self.cache = {}
        self.default_ttl = default_ttl_seconds

    def _is_expired(self, entry: Dict[str, Any]) -> bool:
        """Check if cache entry is expired."""
        return time.time() > entry["expires_at"]

    def get(self, key: str) -> Optional[Any]:
        """Get value from cache."""
        if key in self.cache:
            entry = self.cache[key]
            if not self._is_expired(entry):
                return entry["value"]
            else:
                del self.cache[key]  # Remove expired entry
        return None

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """Set value in cache with TTL."""
        if ttl is None:
            ttl = self.default_ttl
        self.cache[key] = {
            "value": value,
            "expires_at": time.time() + ttl
        }

    def clear(self) -> None:
        """Clear all cache entries."""
        self.cache.clear()

class PromptTemplateManager:
    """Manages prompt templates with caching and versioning."""

    def __init__(self, cache_ttl_seconds: int = 3600):
        """Initialize the template manager.

        Args:
            cache_ttl_seconds: Time-to-live for cached prompts (default: 1 hour)
        """
        self.cache_ttl_seconds = cache_ttl_seconds
        self.cache = SimpleCache(cache_ttl_seconds)
        self.default_template = get_template("1.0")

    def _get_cache_key(
        self,
        goal: str,
        context_hash: str,
        schema_hash: str,
        template_key: str,
        examples_hash: str
    ) -> str:
        """Generate cache key for a prompt.

        Args:
            goal: The task goal
            context_hash: Hash of the context
            schema_hash: Hash of the schema
            template_key: Template version key
            examples_hash: Hash of examples

        Returns:
            Cache key string
        """
        components = [
            goal,
            context_hash,
            schema_hash,
            template_key,
            examples_hash
        ]
        combined = "|".join(str(comp) for comp in components)
        return hashlib.sha256(combined.encode()).hexdigest()[:16]

    def _hash_content(self, content: Any) -> str:
        """Hash content for cache keys.

        Args:
            content: Content to hash (string, dict, etc.)

        Returns:
            Short hash string
        """
        if isinstance(content, (dict, list)):
            content = json.dumps(content, sort_keys=True)
        elif content is None:
            return "empty"
        return hashlib.sha256(str(content).encode()).hexdigest()[:8]

    def select_template(
        self,
        goal: str,
        schema: Optional[Dict] = None,
        template_key: Optional[str] = None
    ) -> str:
        """Select the appropriate template based on task characteristics.

        Args:
            goal: The task goal description
            schema: JSON schema if provided
            template_key: Explicit template key if provided

        Returns:
            Template key to use
        """
        if template_key:
            return template_key

        # Simple heuristic for template selection based on goal content
        goal_lower = goal.lower()

        # Code-related tasks
        if any(keyword in goal_lower for keyword in [
            "code", "function", "class", "debug", "refactor", "implement"
        ]):
            return "code-1.0"

        # Data extraction tasks
        elif any(keyword in goal_lower for keyword in [
            "extract", "find", "identify", "locate", "parse", "detect"
        ]):
            return "extraction-1.0"

        # Data transformation tasks
        elif any(keyword in goal_lower for keyword in [
            "transform", "convert", "format", "restructure", "reshape"
        ]):
            return "transformation-1.0"

        # Analysis tasks
        elif any(keyword in goal_lower for keyword in [
            "analyze", "summarize", "insight", "compare", "evaluate"
        ]):
            return "analysis-1.0"

        # Default template
        return "1.0"

    def build_prompt(
        self,
        goal: str,
        context: str,
        schema: Optional[Dict] = None,
        template_key: Optional[str] = None,
        examples: Optional[List[Dict]] = None,
        use_cache: bool = True
    ) -> tuple[str, str]:
        """Build a complete prompt using templates and caching.

        Args:
            goal: The task goal
            context: Context information
            schema: JSON schema for output validation
            template_key: Template version to use (auto-selected if None)
            examples: Few-shot examples
            use_cache: Whether to use cache (default: True)

        Returns:
            Tuple of (prompt, template_key_used)
        """
        # Select template
        template_key = self.select_template(goal, schema, template_key)
        template = get_template(template_key)

        # Generate hashes for caching
        context_hash = self._hash_content(context)
        schema_hash = self._hash_content(schema)
        examples_hash = self._hash_content(examples)

        # Check cache
        cache_key = self._get_cache_key(
            goal, context_hash, schema_hash, template_key, examples_hash
        )

        if use_cache:
            cached_prompt = self.cache.get(cache_key)
            if cached_prompt:
                return cached_prompt, template_key

        # Build prompt from template
        prompt = template.build_prompt(
            goal=goal,
            context=context,
            schema=schema,
            examples=examples
        )

        # Cache the prompt
        if use_cache:
            self.cache.set(cache_key, prompt, ttl=self.cache_ttl_seconds)

        return prompt, template_key

    def load_context_from_path(self, context_path: Optional[str]) -> str:
        """Load context from file or directory path.

        Args:
            context_path: Path to file or directory

        Returns:
            Combined context string
        """
        if not context_path or not Path(context_path).exists():
            return ""

        p = Path(context_path)
        if p.is_file():
            return p.read_text(encoding="utf-8", errors="ignore")
        else:
            # Concatenate small files
            parts = []
            for sub in p.glob("**/*"):
                if sub.is_file() and sub.stat().st_size < 200_000:
                    parts.append(sub.read_text(encoding="utf-8", errors="ignore"))
            return "\n\n".join(parts[:5])

    def get_template_info(self, template_key: str) -> Dict[str, Any]:
        """Get information about a template.

        Args:
            template_key: Template version key

        Returns:
            Template information dictionary
        """
        template = get_template(template_key)
        return {
            "version": template.version,
            "system": template.template_dict["system"],
            "max_examples": template.template_dict.get("max_examples", 3),
            "context_max_chars": template.template_dict.get("context_max_chars", 4000)
        }

    def list_available_templates(self) -> List[str]:
        """List all available template keys.

        Returns:
            List of template keys
        """
        from .templates import list_templates
        return list_templates()

    def clear_cache(self):
        """Clear the prompt cache."""
        self.cache.clear()

def create_template_manager_from_config(config_path: str) -> PromptTemplateManager:
    """Create template manager from configuration file.

    Args:
        config_path: Path to policy.yaml configuration

    Returns:
        Configured PromptTemplateManager instance
    """
    with open(config_path, "r") as f:
        config = yaml.safe_load(f)

    prompts_config = config.get("prompts", {})
    cache_ttl = prompts_config.get("template_cache_ttl_seconds", 3600)

    return PromptTemplateManager(cache_ttl_seconds=cache_ttl)