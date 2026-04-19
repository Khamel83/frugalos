"""
Advanced multi-model orchestration system for Hermes AI Assistant.

This module provides intelligent model selection, routing, and management across
multiple AI providers and model types with performance tracking, cost optimization,
and automatic fallback capabilities.
"""

import asyncio
import time
import json
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Callable, Tuple
from dataclasses import dataclass, field
from collections import defaultdict, deque
from enum import Enum
import logging

import redis.asyncio as redis
import numpy as np
from openai import AsyncOpenAI
import anthropic
import cohere

logger = logging.getLogger(__name__)


class ModelProvider(Enum):
    """Supported AI model providers."""
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    COHERE = "cohere"
    OLLAMA = "ollama"
    AZURE_OPENAI = "azure_openai"
    GOOGLE_PALM = "google_palm"
    HUGGINGFACE = "huggingface"
    LOCAL = "local"


class ModelCapability(Enum):
    """Model capabilities and use cases."""
    TEXT_GENERATION = "text_generation"
    CHAT_COMPLETION = "chat_completion"
    CODE_GENERATION = "code_generation"
    EMBEDDINGS = "embeddings"
    FUNCTION_CALLING = "function_calling"
    VISION = "vision"
    AUDIO = "audio"
    REASONING = "reasoning"
    LONG_CONTEXT = "long_context"


class TaskComplexity(Enum):
    """Task complexity levels for model selection."""
    SIMPLE = "simple"
    MODERATE = "moderate"
    COMPLEX = "complex"
    EXPERT = "expert"


@dataclass
class ModelConfig:
    """Configuration for an AI model."""
    provider: ModelProvider
    model_id: str
    name: str
    capabilities: List[ModelCapability]
    max_tokens: int
    context_window: int
    cost_per_1k_input_tokens: float
    cost_per_1k_output_tokens: float
    avg_latency_ms: float = 0.0
    priority: int = 1
    enabled: bool = True
    api_key: Optional[str] = None
    api_base: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ModelPerformanceMetrics:
    """Performance metrics for a model."""
    model_id: str
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    total_tokens_input: int = 0
    total_tokens_output: int = 0
    total_cost: float = 0.0
    avg_latency_ms: float = 0.0
    p95_latency_ms: float = 0.0
    p99_latency_ms: float = 0.0
    latency_samples: deque = field(default_factory=lambda: deque(maxlen=1000))
    last_error: Optional[str] = None
    last_used: Optional[datetime] = None
    success_rate: float = 100.0


@dataclass
class ModelRequest:
    """Request to be routed to a model."""
    task_type: ModelCapability
    prompt: str
    max_tokens: int
    temperature: float = 0.7
    complexity: TaskComplexity = TaskComplexity.MODERATE
    budget_cents: Optional[float] = None
    latency_requirement_ms: Optional[float] = None
    preferred_provider: Optional[ModelProvider] = None
    context: Optional[Dict[str, Any]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ModelResponse:
    """Response from a model."""
    model_id: str
    provider: ModelProvider
    content: str
    tokens_input: int
    tokens_output: int
    latency_ms: float
    cost: float
    finish_reason: str
    cached: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)


class ModelRegistry:
    """Registry of available AI models with their configurations."""

    def __init__(self):
        self.models: Dict[str, ModelConfig] = {}
        self.performance_metrics: Dict[str, ModelPerformanceMetrics] = {}
        self._initialize_default_models()

    def _initialize_default_models(self):
        """Initialize registry with default model configurations."""
        default_models = [
            # OpenAI Models
            ModelConfig(
                provider=ModelProvider.OPENAI,
                model_id="gpt-4-turbo-preview",
                name="GPT-4 Turbo",
                capabilities=[
                    ModelCapability.TEXT_GENERATION,
                    ModelCapability.CHAT_COMPLETION,
                    ModelCapability.CODE_GENERATION,
                    ModelCapability.FUNCTION_CALLING,
                    ModelCapability.REASONING
                ],
                max_tokens=4096,
                context_window=128000,
                cost_per_1k_input_tokens=0.01,
                cost_per_1k_output_tokens=0.03,
                avg_latency_ms=2000,
                priority=1
            ),
            ModelConfig(
                provider=ModelProvider.OPENAI,
                model_id="gpt-3.5-turbo",
                name="GPT-3.5 Turbo",
                capabilities=[
                    ModelCapability.TEXT_GENERATION,
                    ModelCapability.CHAT_COMPLETION,
                    ModelCapability.CODE_GENERATION,
                    ModelCapability.FUNCTION_CALLING
                ],
                max_tokens=4096,
                context_window=16384,
                cost_per_1k_input_tokens=0.0005,
                cost_per_1k_output_tokens=0.0015,
                avg_latency_ms=800,
                priority=2
            ),

            # Anthropic Models
            ModelConfig(
                provider=ModelProvider.ANTHROPIC,
                model_id="claude-3-opus-20240229",
                name="Claude 3 Opus",
                capabilities=[
                    ModelCapability.TEXT_GENERATION,
                    ModelCapability.CHAT_COMPLETION,
                    ModelCapability.CODE_GENERATION,
                    ModelCapability.REASONING,
                    ModelCapability.LONG_CONTEXT
                ],
                max_tokens=4096,
                context_window=200000,
                cost_per_1k_input_tokens=0.015,
                cost_per_1k_output_tokens=0.075,
                avg_latency_ms=3000,
                priority=1
            ),
            ModelConfig(
                provider=ModelProvider.ANTHROPIC,
                model_id="claude-3-sonnet-20240229",
                name="Claude 3 Sonnet",
                capabilities=[
                    ModelCapability.TEXT_GENERATION,
                    ModelCapability.CHAT_COMPLETION,
                    ModelCapability.CODE_GENERATION,
                    ModelCapability.REASONING
                ],
                max_tokens=4096,
                context_window=200000,
                cost_per_1k_input_tokens=0.003,
                cost_per_1k_output_tokens=0.015,
                avg_latency_ms=1500,
                priority=2
            ),
            ModelConfig(
                provider=ModelProvider.ANTHROPIC,
                model_id="claude-3-haiku-20240307",
                name="Claude 3 Haiku",
                capabilities=[
                    ModelCapability.TEXT_GENERATION,
                    ModelCapability.CHAT_COMPLETION,
                    ModelCapability.CODE_GENERATION
                ],
                max_tokens=4096,
                context_window=200000,
                cost_per_1k_input_tokens=0.00025,
                cost_per_1k_output_tokens=0.00125,
                avg_latency_ms=600,
                priority=3
            ),

            # Ollama Local Models
            ModelConfig(
                provider=ModelProvider.OLLAMA,
                model_id="llama3.1:8b-instruct",
                name="Llama 3.1 8B",
                capabilities=[
                    ModelCapability.TEXT_GENERATION,
                    ModelCapability.CHAT_COMPLETION,
                    ModelCapability.CODE_GENERATION
                ],
                max_tokens=2048,
                context_window=8192,
                cost_per_1k_input_tokens=0.0,
                cost_per_1k_output_tokens=0.0,
                avg_latency_ms=500,
                priority=4
            ),
            ModelConfig(
                provider=ModelProvider.OLLAMA,
                model_id="qwen2.5-coder:7b",
                name="Qwen 2.5 Coder 7B",
                capabilities=[
                    ModelCapability.CODE_GENERATION,
                    ModelCapability.TEXT_GENERATION
                ],
                max_tokens=2048,
                context_window=8192,
                cost_per_1k_input_tokens=0.0,
                cost_per_1k_output_tokens=0.0,
                avg_latency_ms=400,
                priority=4
            ),
        ]

        for model in default_models:
            self.register_model(model)

    def register_model(self, config: ModelConfig):
        """Register a new model in the registry."""
        self.models[config.model_id] = config
        if config.model_id not in self.performance_metrics:
            self.performance_metrics[config.model_id] = ModelPerformanceMetrics(
                model_id=config.model_id
            )
        logger.info(f"Registered model: {config.name} ({config.model_id})")

    def get_model(self, model_id: str) -> Optional[ModelConfig]:
        """Get model configuration by ID."""
        return self.models.get(model_id)

    def get_models_by_capability(self, capability: ModelCapability,
                                enabled_only: bool = True) -> List[ModelConfig]:
        """Get all models with a specific capability."""
        models = [
            m for m in self.models.values()
            if capability in m.capabilities and (not enabled_only or m.enabled)
        ]
        return sorted(models, key=lambda m: m.priority)

    def get_models_by_provider(self, provider: ModelProvider) -> List[ModelConfig]:
        """Get all models from a specific provider."""
        return [m for m in self.models.values() if m.provider == provider]

    def update_performance_metrics(self, model_id: str, response: ModelResponse,
                                  success: bool = True):
        """Update performance metrics for a model."""
        if model_id not in self.performance_metrics:
            self.performance_metrics[model_id] = ModelPerformanceMetrics(model_id=model_id)

        metrics = self.performance_metrics[model_id]
        metrics.total_requests += 1
        metrics.last_used = datetime.utcnow()

        if success:
            metrics.successful_requests += 1
            metrics.total_tokens_input += response.tokens_input
            metrics.total_tokens_output += response.tokens_output
            metrics.total_cost += response.cost
            metrics.latency_samples.append(response.latency_ms)

            # Update latency statistics
            if metrics.latency_samples:
                metrics.avg_latency_ms = np.mean(list(metrics.latency_samples))
                metrics.p95_latency_ms = np.percentile(list(metrics.latency_samples), 95)
                metrics.p99_latency_ms = np.percentile(list(metrics.latency_samples), 99)
        else:
            metrics.failed_requests += 1

        # Update success rate
        if metrics.total_requests > 0:
            metrics.success_rate = (metrics.successful_requests / metrics.total_requests) * 100

    def get_performance_metrics(self, model_id: str) -> Optional[ModelPerformanceMetrics]:
        """Get performance metrics for a model."""
        return self.performance_metrics.get(model_id)

    def get_all_metrics(self) -> Dict[str, ModelPerformanceMetrics]:
        """Get performance metrics for all models."""
        return self.performance_metrics


class ModelSelector:
    """Intelligent model selection based on requirements and constraints."""

    def __init__(self, registry: ModelRegistry):
        self.registry = registry
        self.selection_history: deque = deque(maxlen=1000)

    def select_model(self, request: ModelRequest) -> Optional[ModelConfig]:
        """Select the best model for the given request."""
        # Get candidate models
        candidates = self._get_candidate_models(request)

        if not candidates:
            logger.warning(f"No suitable models found for task: {request.task_type}")
            return None

        # Score and rank candidates
        scored_models = []
        for model in candidates:
            score = self._score_model(model, request)
            scored_models.append((score, model))

        # Sort by score (highest first)
        scored_models.sort(reverse=True, key=lambda x: x[0])

        # Select best model
        selected_model = scored_models[0][1]

        # Record selection
        self.selection_history.append({
            'timestamp': datetime.utcnow(),
            'model_id': selected_model.model_id,
            'task_type': request.task_type.value,
            'complexity': request.complexity.value,
            'score': scored_models[0][0]
        })

        logger.info(f"Selected model: {selected_model.name} (score: {scored_models[0][0]:.2f})")
        return selected_model

    def _get_candidate_models(self, request: ModelRequest) -> List[ModelConfig]:
        """Get candidate models that meet basic requirements."""
        candidates = []

        # Filter by capability
        capable_models = self.registry.get_models_by_capability(request.task_type)

        for model in capable_models:
            # Check if model meets requirements
            if not model.enabled:
                continue

            # Check preferred provider
            if request.preferred_provider and model.provider != request.preferred_provider:
                continue

            # Check token limit
            if request.max_tokens > model.max_tokens:
                continue

            # Check budget constraint
            if request.budget_cents:
                estimated_cost = self._estimate_cost(model, request)
                if estimated_cost > request.budget_cents:
                    continue

            # Check latency requirement
            if request.latency_requirement_ms:
                metrics = self.registry.get_performance_metrics(model.model_id)
                if metrics and metrics.avg_latency_ms > request.latency_requirement_ms:
                    continue

            candidates.append(model)

        return candidates

    def _score_model(self, model: ModelConfig, request: ModelRequest) -> float:
        """Score a model based on request requirements and performance."""
        score = 0.0

        # Base score from priority (higher priority = higher score)
        score += (5 - model.priority) * 20

        # Performance metrics
        metrics = self.registry.get_performance_metrics(model.model_id)
        if metrics:
            # Success rate (0-30 points)
            score += metrics.success_rate * 0.3

            # Latency score (0-20 points, lower latency = higher score)
            if metrics.avg_latency_ms > 0:
                latency_score = max(0, 20 - (metrics.avg_latency_ms / 100))
                score += latency_score

        # Cost efficiency (0-20 points, lower cost = higher score)
        estimated_cost = self._estimate_cost(model, request)
        if estimated_cost > 0:
            # Normalize cost score (assuming max cost of $0.10 per request)
            cost_score = max(0, 20 - (estimated_cost / 0.10) * 20)
            score += cost_score

        # Complexity matching (0-15 points)
        complexity_scores = {
            TaskComplexity.SIMPLE: {1: 15, 2: 15, 3: 10, 4: 15},  # Favor cheaper models
            TaskComplexity.MODERATE: {1: 12, 2: 15, 3: 12, 4: 10},
            TaskComplexity.COMPLEX: {1: 15, 2: 12, 3: 10, 4: 5},
            TaskComplexity.EXPERT: {1: 15, 2: 10, 3: 5, 4: 0}  # Favor best models
        }
        score += complexity_scores.get(request.complexity, {}).get(model.priority, 0)

        # Context window bonus (0-10 points for large context)
        if model.context_window >= 100000:
            score += 10
        elif model.context_window >= 32000:
            score += 5

        return score

    def _estimate_cost(self, model: ModelConfig, request: ModelRequest) -> float:
        """Estimate cost for the request with this model."""
        # Rough estimation based on prompt length and max_tokens
        estimated_input_tokens = len(request.prompt.split()) * 1.3  # Rough token estimate
        estimated_output_tokens = request.max_tokens * 0.7  # Assume 70% of max

        input_cost = (estimated_input_tokens / 1000) * model.cost_per_1k_input_tokens
        output_cost = (estimated_output_tokens / 1000) * model.cost_per_1k_output_tokens

        return input_cost + output_cost


class ModelExecutor:
    """Executes requests against selected models with retry and fallback."""

    def __init__(self, registry: ModelRegistry, redis_client: Optional[redis.Redis] = None):
        self.registry = registry
        self.redis = redis_client
        self.clients: Dict[ModelProvider, Any] = {}
        self._initialize_clients()

    def _initialize_clients(self):
        """Initialize API clients for different providers."""
        # Initialize clients based on available API keys
        # This would be configured with actual API keys in production
        try:
            self.clients[ModelProvider.OPENAI] = AsyncOpenAI()
        except Exception as e:
            logger.warning(f"Could not initialize OpenAI client: {e}")

        try:
            self.clients[ModelProvider.ANTHROPIC] = anthropic.AsyncAnthropic()
        except Exception as e:
            logger.warning(f"Could not initialize Anthropic client: {e}")

        logger.info(f"Initialized {len(self.clients)} model provider clients")

    async def execute(self, model: ModelConfig, request: ModelRequest,
                     max_retries: int = 3) -> ModelResponse:
        """Execute request against the specified model."""
        start_time = time.time()
        last_error = None

        for attempt in range(max_retries):
            try:
                # Route to appropriate provider
                if model.provider == ModelProvider.OPENAI:
                    response = await self._execute_openai(model, request)
                elif model.provider == ModelProvider.ANTHROPIC:
                    response = await self._execute_anthropic(model, request)
                elif model.provider == ModelProvider.OLLAMA:
                    response = await self._execute_ollama(model, request)
                else:
                    raise ValueError(f"Unsupported provider: {model.provider}")

                # Calculate actual latency
                response.latency_ms = (time.time() - start_time) * 1000

                # Update metrics
                self.registry.update_performance_metrics(model.model_id, response, success=True)

                return response

            except Exception as e:
                last_error = str(e)
                logger.error(f"Error executing model {model.model_id} (attempt {attempt + 1}): {e}")

                if attempt < max_retries - 1:
                    await asyncio.sleep(2 ** attempt)  # Exponential backoff

        # All retries failed
        raise Exception(f"Failed to execute model after {max_retries} attempts: {last_error}")

    async def _execute_openai(self, model: ModelConfig, request: ModelRequest) -> ModelResponse:
        """Execute request using OpenAI API."""
        client = self.clients.get(ModelProvider.OPENAI)
        if not client:
            raise Exception("OpenAI client not initialized")

        messages = [{"role": "user", "content": request.prompt}]

        response = await client.chat.completions.create(
            model=model.model_id,
            messages=messages,
            max_tokens=request.max_tokens,
            temperature=request.temperature
        )

        # Extract response details
        choice = response.choices[0]
        usage = response.usage

        cost = self._calculate_cost(
            model,
            usage.prompt_tokens,
            usage.completion_tokens
        )

        return ModelResponse(
            model_id=model.model_id,
            provider=model.provider,
            content=choice.message.content,
            tokens_input=usage.prompt_tokens,
            tokens_output=usage.completion_tokens,
            latency_ms=0,  # Will be set by executor
            cost=cost,
            finish_reason=choice.finish_reason
        )

    async def _execute_anthropic(self, model: ModelConfig, request: ModelRequest) -> ModelResponse:
        """Execute request using Anthropic API."""
        client = self.clients.get(ModelProvider.ANTHROPIC)
        if not client:
            raise Exception("Anthropic client not initialized")

        response = await client.messages.create(
            model=model.model_id,
            max_tokens=request.max_tokens,
            temperature=request.temperature,
            messages=[{"role": "user", "content": request.prompt}]
        )

        # Extract response details
        content = response.content[0].text
        tokens_input = response.usage.input_tokens
        tokens_output = response.usage.output_tokens

        cost = self._calculate_cost(model, tokens_input, tokens_output)

        return ModelResponse(
            model_id=model.model_id,
            provider=model.provider,
            content=content,
            tokens_input=tokens_input,
            tokens_output=tokens_output,
            latency_ms=0,
            cost=cost,
            finish_reason=response.stop_reason
        )

    async def _execute_ollama(self, model: ModelConfig, request: ModelRequest) -> ModelResponse:
        """Execute request using Ollama local API."""
        import aiohttp

        async with aiohttp.ClientSession() as session:
            url = "http://localhost:11434/api/generate"
            payload = {
                "model": model.model_id,
                "prompt": request.prompt,
                "stream": False,
                "options": {
                    "num_predict": request.max_tokens,
                    "temperature": request.temperature
                }
            }

            async with session.post(url, json=payload) as resp:
                if resp.status != 200:
                    raise Exception(f"Ollama request failed: {resp.status}")

                data = await resp.json()

                # Ollama responses are free (local)
                return ModelResponse(
                    model_id=model.model_id,
                    provider=model.provider,
                    content=data.get('response', ''),
                    tokens_input=0,  # Ollama doesn't return token counts
                    tokens_output=0,
                    latency_ms=0,
                    cost=0.0,
                    finish_reason='stop'
                )

    def _calculate_cost(self, model: ModelConfig, input_tokens: int,
                       output_tokens: int) -> float:
        """Calculate cost for the request."""
        input_cost = (input_tokens / 1000) * model.cost_per_1k_input_tokens
        output_cost = (output_tokens / 1000) * model.cost_per_1k_output_tokens
        return input_cost + output_cost


class MultiModelOrchestrator:
    """Main orchestrator for multi-model AI requests."""

    def __init__(self, redis_client: Optional[redis.Redis] = None):
        self.registry = ModelRegistry()
        self.selector = ModelSelector(self.registry)
        self.executor = ModelExecutor(self.registry, redis_client)
        self.request_history: deque = deque(maxlen=10000)

    async def process_request(self, request: ModelRequest,
                             enable_fallback: bool = True) -> ModelResponse:
        """Process a model request with intelligent routing and fallback."""
        start_time = time.time()

        # Select best model
        selected_model = self.selector.select_model(request)
        if not selected_model:
            raise Exception("No suitable model available for request")

        try:
            # Execute request
            response = await self.executor.execute(selected_model, request)

            # Record success
            self._record_request(request, response, success=True)

            return response

        except Exception as e:
            logger.error(f"Primary model execution failed: {e}")

            if not enable_fallback:
                raise

            # Try fallback models
            response = await self._try_fallback(request, selected_model)

            if response:
                self._record_request(request, response, success=True)
                return response
            else:
                raise Exception(f"All model attempts failed: {e}")

    async def _try_fallback(self, request: ModelRequest,
                           failed_model: ModelConfig) -> Optional[ModelResponse]:
        """Try fallback models if primary fails."""
        # Get alternative models
        candidates = self.registry.get_models_by_capability(request.task_type)

        # Remove failed model and sort by priority
        candidates = [m for m in candidates if m.model_id != failed_model.model_id]
        candidates = sorted(candidates, key=lambda m: m.priority)

        for fallback_model in candidates[:3]:  # Try up to 3 fallbacks
            try:
                logger.info(f"Trying fallback model: {fallback_model.name}")
                response = await self.executor.execute(fallback_model, request, max_retries=1)
                logger.info(f"Fallback successful with {fallback_model.name}")
                return response
            except Exception as e:
                logger.warning(f"Fallback model {fallback_model.name} failed: {e}")
                continue

        return None

    def _record_request(self, request: ModelRequest, response: ModelResponse,
                       success: bool = True):
        """Record request in history."""
        self.request_history.append({
            'timestamp': datetime.utcnow(),
            'task_type': request.task_type.value,
            'model_id': response.model_id,
            'provider': response.provider.value,
            'tokens_input': response.tokens_input,
            'tokens_output': response.tokens_output,
            'cost': response.cost,
            'latency_ms': response.latency_ms,
            'success': success
        })

    def get_statistics(self, hours: int = 24) -> Dict[str, Any]:
        """Get orchestrator statistics."""
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)

        recent_requests = [
            r for r in self.request_history
            if r['timestamp'] >= cutoff_time
        ]

        if not recent_requests:
            return {}

        total_cost = sum(r['cost'] for r in recent_requests)
        total_latency = sum(r['latency_ms'] for r in recent_requests)
        successful = sum(1 for r in recent_requests if r['success'])

        # Group by model
        by_model = defaultdict(lambda: {'count': 0, 'cost': 0, 'tokens': 0})
        for r in recent_requests:
            by_model[r['model_id']]['count'] += 1
            by_model[r['model_id']]['cost'] += r['cost']
            by_model[r['model_id']]['tokens'] += r['tokens_input'] + r['tokens_output']

        return {
            'period_hours': hours,
            'total_requests': len(recent_requests),
            'successful_requests': successful,
            'success_rate': (successful / len(recent_requests)) * 100,
            'total_cost': total_cost,
            'avg_cost_per_request': total_cost / len(recent_requests),
            'avg_latency_ms': total_latency / len(recent_requests),
            'models_used': len(by_model),
            'breakdown_by_model': dict(by_model)
        }


# Global orchestrator instance
orchestrator: Optional[MultiModelOrchestrator] = None