"""
Cloud Model Runner - OpenRouter Integration
Handles premium cloud model calls and cost calculation
"""
import time
import requests
from typing import Dict, Optional
from dataclasses import dataclass

from .config import MODEL_COSTS, OPENROUTER_API_KEY, OPENROUTER_BASE_URL


@dataclass
class CloudResult:
    model: str
    response: str
    quality_score: float
    response_time: float
    cost: float
    input_tokens: int
    output_tokens: int
    success: bool
    error: Optional[str] = None


class CloudModelRunner:
    """Runs prompts through OpenRouter cloud models"""

    def __init__(self, api_key: str = OPENROUTER_API_KEY):
        self.api_key = api_key
        self.base_url = OPENROUTER_BASE_URL
        self.premium_models = MODEL_COSTS["premium_models"]

    def run_prompt(self, prompt: str, model: str = "anthropic/claude-3.5-sonnet", max_tokens: int = 4000) -> CloudResult:
        """Run prompt through cloud model"""

        if not self.api_key:
            return CloudResult(
                model=model,
                response="",
                quality_score=0.0,
                response_time=0.0,
                cost=0.0,
                input_tokens=0,
                output_tokens=0,
                success=False,
                error="No API key configured"
            )

        start_time = time.time()

        try:
            response = requests.post(
                f"{self.base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": model,
                    "messages": [
                        {"role": "user", "content": prompt}
                    ],
                    "max_tokens": max_tokens
                },
                timeout=60
            )
            response.raise_for_status()
            response_data = response.json()

            # Extract response
            response_text = response_data["choices"][0]["message"]["content"]

            # Get token usage
            usage = response_data.get("usage", {})
            input_tokens = usage.get("prompt_tokens", 0)
            output_tokens = usage.get("completion_tokens", 0)

            # Calculate cost
            model_config = self.premium_models.get(model, {})
            cost = self._calculate_cost(input_tokens, output_tokens, model_config)

            response_time = time.time() - start_time

            # Quality score (cloud models assumed high quality)
            quality_score = model_config.get("quality", 9.5)

            return CloudResult(
                model=model,
                response=response_text,
                quality_score=quality_score,
                response_time=response_time,
                cost=cost,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                success=True
            )

        except requests.exceptions.Timeout:
            return CloudResult(
                model=model,
                response="",
                quality_score=0.0,
                response_time=time.time() - start_time,
                cost=0.0,
                input_tokens=0,
                output_tokens=0,
                success=False,
                error="Timeout"
            )
        except Exception as e:
            return CloudResult(
                model=model,
                response="",
                quality_score=0.0,
                response_time=time.time() - start_time,
                cost=0.0,
                input_tokens=0,
                output_tokens=0,
                success=False,
                error=str(e)
            )

    def estimate_cost(self, prompt: str, model: str = "anthropic/claude-3.5-sonnet") -> float:
        """Estimate cost for a prompt without running it"""

        # Simple token estimation: words * 1.3
        input_tokens = len(prompt.split()) * 1.3
        output_tokens = input_tokens * 2  # Educated guess

        model_config = self.premium_models.get(model, {})
        return self._calculate_cost(int(input_tokens), int(output_tokens), model_config)

    def _calculate_cost(self, input_tokens: int, output_tokens: int, model_config: Dict) -> float:
        """Calculate cost based on token usage"""

        input_cost_per_million = model_config.get("input_per_million", 3.0)
        output_cost_per_million = model_config.get("output_per_million", 15.0)

        input_cost = (input_tokens / 1_000_000) * input_cost_per_million
        output_cost = (output_tokens / 1_000_000) * output_cost_per_million

        return input_cost + output_cost

    def get_upgrade_options(self, prompt: str, local_quality: float) -> list:
        """Get available upgrade options with costs"""

        upgrade_options = []

        for model_name, model_config in self.premium_models.items():
            estimated_cost = self.estimate_cost(prompt, model_name)
            cloud_quality = model_config.get("quality", 9.5)
            quality_gain = cloud_quality - local_quality

            if quality_gain > 0.5:  # Only show meaningful improvements
                upgrade_options.append({
                    "model": model_name,
                    "quality": cloud_quality,
                    "quality_gain": quality_gain,
                    "estimated_cost": estimated_cost,
                    "cost_per_point": estimated_cost / quality_gain if quality_gain > 0 else 0,
                    "specialties": model_config.get("specialties", [])
                })

        # Sort by cost per quality point (best value first)
        return sorted(upgrade_options, key=lambda x: x["cost_per_point"])
