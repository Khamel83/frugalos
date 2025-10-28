"""
Local Model Runner - Ollama Integration
Runs prompts through local models and scores quality
"""
import time
import requests
from typing import Dict, List, Optional
from dataclasses import dataclass

from .config import MODEL_COSTS, OLLAMA_BASE_URL


@dataclass
class LocalResult:
    model: str
    response: str
    quality_score: float
    response_time: float
    success: bool
    error: Optional[str] = None


class LocalModelRunner:
    """Runs prompts through local Ollama models"""

    def __init__(self, base_url: str = OLLAMA_BASE_URL):
        self.base_url = base_url
        self.local_models = MODEL_COSTS["local_models"]

    def run_prompt(self, prompt: str, model: str, timeout: int = 60) -> LocalResult:
        """Run prompt through a specific local model"""

        start_time = time.time()

        try:
            response = requests.post(
                f"{self.base_url}/api/generate",
                json={
                    "model": model,
                    "prompt": prompt,
                    "stream": False
                },
                timeout=timeout
            )
            response.raise_for_status()
            response_data = response.json()

            response_text = response_data.get("response", "")
            response_time = time.time() - start_time

            # Score quality
            quality_score = self._score_quality(response_text, prompt)

            return LocalResult(
                model=model,
                response=response_text,
                quality_score=quality_score,
                response_time=response_time,
                success=True
            )

        except requests.exceptions.Timeout:
            return LocalResult(
                model=model,
                response="",
                quality_score=0.0,
                response_time=time.time() - start_time,
                success=False,
                error="Timeout"
            )
        except Exception as e:
            return LocalResult(
                model=model,
                response="",
                quality_score=0.0,
                response_time=time.time() - start_time,
                success=False,
                error=str(e)
            )

    def try_all_local_models(self, prompt: str) -> List[LocalResult]:
        """Try prompt on all local models and return results"""

        results = []
        for model_name in self.local_models.keys():
            result = self.run_prompt(prompt, model_name)
            results.append(result)

        return results

    def get_best_local_result(self, prompt: str) -> LocalResult:
        """Get best local result across all models"""

        results = self.try_all_local_models(prompt)

        # Filter successful results
        successful_results = [r for r in results if r.success]

        if not successful_results:
            # All models failed - return first failure
            return results[0]

        # Return highest quality result
        return max(successful_results, key=lambda x: x.quality_score)

    def _score_quality(self, response: str, prompt: str) -> float:
        """
        Simple quality scoring - MVP heuristics
        Returns score from 0-10
        """

        if not response or len(response) < 10:
            return 0.0

        score = 5.0  # Start at 5/10

        # Length check (not too short, not too long)
        if 100 < len(response) < 2000:
            score += 1.0
        elif 50 < len(response) < 3000:
            score += 0.5

        # Contains code if prompt asks for code
        prompt_lower = prompt.lower()
        if any(word in prompt_lower for word in ["code", "function", "implement", "script", "program"]):
            if "```" in response or any(keyword in response for keyword in ["def ", "function ", "class ", "import ", "const ", "let "]):
                score += 1.5

        # Structured response (has paragraphs or bullets)
        if "\n\n" in response or "- " in response or "* " in response:
            score += 1.0

        # Specific keywords from prompt appear in response
        prompt_words = set(word.lower() for word in prompt.split() if len(word) > 3)
        response_words = set(word.lower() for word in response.split())
        if prompt_words:
            overlap = len(prompt_words & response_words) / len(prompt_words)
            score += overlap * 1.5

        # Penalize very short responses
        if len(response) < 50:
            score -= 2.0

        # Penalize extremely long responses (might be rambling)
        if len(response) > 5000:
            score -= 0.5

        return max(0.0, min(10.0, score))
