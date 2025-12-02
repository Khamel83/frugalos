"""
Prompt Optimizer for frugalos.

This module automatically analyzes failure patterns and generates improved prompt templates
using local Ollama models. It learns from validation failures and consensus patterns
to iteratively improve prompt performance over time.
"""

from __future__ import annotations
import json
import time
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
import sqlite3

from .template_manager import PromptTemplateManager, get_template
from .templates import TEMPLATE_REGISTRY
from ..local.ollama_adapter import generate_once
from ..ledger import Receipts

class PromptOptimizer:
    """Automatic prompt optimization using local Ollama models."""

    def __init__(self, project: str, policy_config: Dict[str, Any]):
        """Initialize the prompt optimizer.

        Args:
            project: Project name for optimization scope
            policy_config: Policy configuration dict
        """
        self.project = project
        self.config = policy_config
        self.receipts = Receipts(project)

        # Optimization settings
        prompts_config = self.config.get("prompts", {})
        self.enabled = prompts_config.get("optimization_enabled", True)
        self.lookback_hours = prompts_config.get("optimization_lookback_hours", 24)
        self.optimization_model = prompts_config.get("optimization_model", "qwen2.5-coder:7b")

        # A/B testing settings
        self.ab_enabled = prompts_config.get("ab_test_enabled", True)
        self.ab_traffic_ratio = prompts_config.get("ab_test_new_version_traffic", 0.2)
        self.ab_promotion_threshold = prompts_config.get("ab_test_promotion_threshold", 0.1)

    def analyze_failures(self, hours: int = None) -> Dict[str, Any]:
        """Analyze recent failure patterns.

        Args:
            hours: Hours to look back (default from config)

        Returns:
            Dictionary with failure analysis
        """
        if hours is None:
            hours = self.lookback_hours

        failure_patterns = self.receipts.get_failure_patterns(hours)

        analysis = {
            "total_patterns": 0,
            "common_failures": {},
            "template_performance": {},
            "optimization_opportunities": []
        }

        # Aggregate failure patterns
        for template_version, patterns in failure_patterns.items():
            analysis["template_performance"][template_version] = {
                "total_failures": sum(p["count"] for p in patterns.values()),
                "failure_types": list(patterns.keys()),
                "patterns": patterns
            }
            analysis["total_patterns"] += len(patterns)

            # Identify common failure types
            for failure_type, pattern in patterns.items():
                if failure_type not in analysis["common_failures"]:
                    analysis["common_failures"][failure_type] = 0
                analysis["common_failures"][failure_type] += pattern["count"]

                # Generate optimization suggestions
                if pattern["count"] >= 3:  # Threshold for significant failures
                    analysis["optimization_opportunities"].append({
                        "template_version": template_version,
                        "failure_type": failure_type,
                        "count": pattern["count"],
                        "validation_errors": pattern.get("validation_errors", ""),
                        "suggestion": self._generate_optimization_suggestion(
                            failure_type, pattern.get("validation_errors", "")
                        )
                    })

        return analysis

    def _generate_optimization_suggestion(self, failure_type: str, validation_errors: str) -> str:
        """Generate optimization suggestion based on failure type.

        Args:
            failure_type: Type of failure (schema_invalid, low_consensus, etc.)
            validation_errors: JSON schema validation error details

        Returns:
            Optimization suggestion string
        """
        suggestions = {
            "schema_invalid": "Improve schema instructions and examples",
            "low_consensus": "Clarify task requirements and add examples",
            "local_limit:schema_invalid": "Strengthen schema validation guidance",
            "local_limit:low_consensus": "Reduce ambiguity and add structured output examples",
            "local_limit:schema_invalid,low_consensus": "Comprehensive prompt rewrite with clear examples"
        }

        base_suggestion = suggestions.get(failure_type, "General prompt improvement needed")

        if validation_errors and "schema" in failure_type:
            base_suggestion += f" - Focus on: {validation_errors[:100]}..."

        return base_suggestion

    def generate_improved_template(
        self,
        current_template_key: str,
        failure_analysis: Dict[str, Any]
    ) -> Optional[str]:
        """Generate an improved template using local Ollama model.

        Args:
            current_template_key: Current template version
            failure_analysis: Analysis of failure patterns

        Returns:
            New template dictionary or None if generation fails
        """
        if not self.enabled:
            return None

        current_template = get_template(current_template_key)
        current_dict = current_template.template_dict

        # Prepare optimization prompt for local Ollama
        optimization_prompt = self._build_optimization_prompt(
            current_dict, failure_analysis
        )

        try:
            # Generate improved template using local Ollama model
            improved_template_str = generate_once(
                self.optimization_model,
                optimization_prompt,
                temp=0.1
            )

            # Parse and validate the improved template
            improved_template = self._parse_improved_template(
                improved_template_str, current_template_key
            )

            if improved_template:
                return improved_template

        except Exception as e:
            print(f"Error generating improved template: {e}")

        return None

    def _build_optimization_prompt(
        self,
        current_template: Dict[str, Any],
        failure_analysis: Dict[str, Any]
    ) -> str:
        """Build the optimization prompt for local Ollama.

        Args:
            current_template: Current template dictionary
            failure_analysis: Failure analysis results

        Returns:
            Optimization prompt string
        """
        # Extract key failure patterns
        failure_examples = failure_analysis.get("optimization_opportunities", [])[:3]

        failure_summary = ""
        for failure in failure_examples:
            failure_summary += f"- {failure['failure_type']}: {failure['count']} occurrences\n"
            failure_summary += f"  Validation errors: {failure.get('validation_errors', 'N/A')}\n"
            failure_summary += f"  Suggestion: {failure['suggestion']}\n\n"

        optimization_prompt = f"""You are a prompt engineering expert. Your task is to improve a prompt template based on failure analysis.

CURRENT TEMPLATE:
```json
{json.dumps(current_template, indent=2)}
```

FAILURE ANALYSIS:
{failure_summary}

REQUIREMENTS:
1. Keep the same template structure and keys
2. Focus on addressing the identified failure patterns
3. Improve clarity of instructions
4. Add better examples or guidance if helpful
5. Ensure the template remains task-appropriate
6. Make minimal, targeted improvements

Return ONLY a valid JSON object with the improved template structure. Do not include explanations or markdown.

IMPROVED TEMPLATE:"""

        return optimization_prompt

    def _parse_improved_template(
        self,
        template_str: str,
        current_version: str
    ) -> Optional[Dict[str, Any]]:
        """Parse and validate the improved template.

        Args:
            template_str: Template string from Ollama
            current_version: Current template version

        Returns:
            Parsed template dictionary or None if invalid
        """
        try:
            # Extract JSON from response (handle potential markdown)
            json_start = template_str.find('{')
            json_end = template_str.rfind('}') + 1

            if json_start >= 0 and json_end > json_start:
                json_str = template_str[json_start:json_end]
                improved_template = json.loads(json_str)

                # Validate template structure
                required_keys = ["system", "schema_instruction", "output_format", "final_instruction"]
                for key in required_keys:
                    if key not in improved_template:
                        print(f"Missing required key '{key}' in improved template")
                        return None

                # Generate new version number
                current_num = float(current_version.split('-')[-1]) if '-' in current_version else 1.0
                new_version = f"{current_version.split('-')[0] if '-' in current_version else '1'}-{current_num + 0.1:.1f}"

                # Add metadata
                improved_template["version"] = new_version
                improved_template["parent_version"] = current_version
                improved_template["improvement_reason"] = f"Automatic optimization based on failure analysis"

                # Preserve optional fields with defaults
                improved_template.setdefault("max_examples", 3)
                improved_template.setdefault("context_max_chars", 4000)

                return improved_template

            else:
                print("No valid JSON found in improved template response")
                return None

        except json.JSONDecodeError as e:
            print(f"Error parsing improved template JSON: {e}")
            return None

    def save_improved_template(
        self,
        improved_template: Dict[str, Any]
    ) -> bool:
        """Save improved template to the database.

        Args:
            improved_template: Improved template dictionary

        Returns:
            True if saved successfully
        """
        try:
            conn = sqlite3.connect("out/receipts.sqlite")

            # Save to prompt_templates table
            conn.execute("""
                INSERT INTO prompt_templates (
                    version, template_json, parent_version, improvement_reason,
                    is_active, performance_metrics
                ) VALUES (?, ?, ?, ?, ?, ?)
            """, (
                improved_template["version"],
                json.dumps(improved_template),
                improved_template.get("parent_version"),
                improved_template.get("improvement_reason"),
                0,  # Not active yet (needs A/B testing)
                json.dumps({"ab_test": True, "created_at": int(time.time())})
            ))

            conn.commit()
            conn.close()

            print(f"Saved improved template: {improved_template['version']}")
            return True

        except Exception as e:
            print(f"Error saving improved template: {e}")
            return False

    def run_optimization_cycle(self) -> Dict[str, Any]:
        """Run a complete optimization cycle.

        Returns:
            Results dictionary with optimization outcomes
        """
        if not self.enabled:
            return {"status": "disabled", "message": "Optimization is disabled"}

        print(f"Running optimization cycle for project: {self.project}")

        # Step 1: Analyze failures
        failure_analysis = self.analyze_failures()

        if failure_analysis["total_patterns"] == 0:
            return {"status": "no_failures", "message": "No failure patterns found"}

        print(f"Found {failure_analysis['total_patterns']} failure patterns")

        # Step 2: Generate improvements for most problematic template
        template_performance = failure_analysis["template_performance"]
        worst_template = max(
            template_performance.items(),
            key=lambda x: x[1]["total_failures"]
        )

        template_key, performance = worst_template
        print(f"Targeting template: {template_key} ({performance['total_failures']} failures)")

        # Step 3: Generate improved template
        improved_template = self.generate_improved_template(
            template_key, failure_analysis
        )

        if not improved_template:
            return {
                "status": "generation_failed",
                "template": template_key,
                "message": "Failed to generate improved template"
            }

        # Step 4: Save improved template
        if self.save_improved_template(improved_template):
            return {
                "status": "success",
                "original_template": template_key,
                "new_template": improved_template["version"],
                "failures_analyzed": failure_analysis["total_patterns"],
                "improvement_reason": improved_template.get("improvement_reason", "")
            }
        else:
            return {
                "status": "save_failed",
                "template": template_key,
                "message": "Failed to save improved template"
            }

    def should_ab_test_new_template(self, new_template_version: str) -> bool:
        """Determine if new template should be A/B tested.

        Args:
            new_template_version: New template version

        Returns:
            True if should A/B test
        """
        if not self.ab_enabled:
            return False

        # For now, always A/B test new templates
        # Later versions could be more sophisticated
        return True

    def get_template_performance(self, hours: int = 24) -> Dict[str, Dict[str, Any]]:
        """Get performance metrics for templates.

        Args:
            hours: Hours to look back

        Returns:
            Dictionary with template performance metrics
        """
        cutoff_time = int(time.time()) - (hours * 3600)

        conn = sqlite3.connect("out/receipts.sqlite")
        cursor = conn.cursor()

        # Get success/failure counts by template version
        cursor.execute("""
            SELECT template_version, COUNT(*) as total,
                   SUM(CASE WHEN why LIKE 'ok%' THEN 1 ELSE 0 END) as successes,
                   SUM(CASE WHEN why LIKE 'retry_ok%' THEN 1 ELSE 0 END) as retries,
                   AVG(latency_s) as avg_latency,
                   SUM(cost_cents) as total_cost
            FROM receipts
            WHERE project=? AND ts>?
            GROUP BY template_version
        """, (self.project, cutoff_time))

        performance = {}
        for row in cursor.fetchall():
            template_ver, total, successes, retries, avg_latency, total_cost = row

            success_rate = successes / total if total > 0 else 0
            retry_rate = retries / total if total > 0 else 0

            performance[template_ver] = {
                "total_jobs": total,
                "success_rate": success_rate,
                "retry_rate": retry_rate,
                "avg_latency": avg_latency,
                "total_cost": total_cost,
                "jobs_per_hour": total / hours if hours > 0 else 0
            }

        conn.close()
        return performance

def create_optimizer(project: str, policy_path: str = "frugalos/policy.yaml") -> PromptOptimizer:
    """Create a prompt optimizer instance.

    Args:
        project: Project name
        policy_path: Path to policy configuration

    Returns:
        PromptOptimizer instance
    """
    import yaml

    with open(policy_path, "r") as f:
        config = yaml.safe_load(f)

    return PromptOptimizer(project, config)