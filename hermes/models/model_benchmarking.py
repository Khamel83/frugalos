"""
Advanced model performance benchmarking and evaluation system.

This module provides comprehensive benchmarking capabilities for AI models including:
- Performance testing across different task types
- Quality evaluation metrics
- Cost-performance analysis
- Comparative benchmarking
- Automated model selection recommendations
"""

import asyncio
import time
import json
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
from collections import defaultdict
import logging
from pathlib import Path

import numpy as np
from sklearn.metrics import accuracy_score, f1_score
import matplotlib.pyplot as plt
import seaborn as sns

from .model_orchestrator import (
    ModelConfig, ModelRequest, ModelResponse, ModelCapability,
    TaskComplexity, ModelProvider, MultiModelOrchestrator
)

logger = logging.getLogger(__name__)


@dataclass
class BenchmarkTask:
    """A single benchmark task."""
    task_id: str
    task_type: ModelCapability
    complexity: TaskComplexity
    prompt: str
    expected_output: Optional[str] = None
    ground_truth: Optional[Any] = None
    max_tokens: int = 500
    temperature: float = 0.7
    evaluation_criteria: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class BenchmarkResult:
    """Results from benchmarking a model on a task."""
    task_id: str
    model_id: str
    provider: str
    response_content: str
    tokens_input: int
    tokens_output: int
    latency_ms: float
    cost: float
    quality_score: float
    accuracy: Optional[float] = None
    passed: bool = False
    error: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ModelBenchmarkReport:
    """Comprehensive benchmark report for a model."""
    model_id: str
    model_name: str
    provider: str
    total_tasks: int
    successful_tasks: int
    failed_tasks: int
    avg_latency_ms: float
    p95_latency_ms: float
    p99_latency_ms: float
    total_cost: float
    avg_cost_per_task: float
    avg_quality_score: float
    pass_rate: float
    results_by_complexity: Dict[str, Dict[str, Any]]
    results_by_task_type: Dict[str, Dict[str, Any]]
    recommendations: List[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.utcnow)


class BenchmarkTaskGenerator:
    """Generates benchmark tasks for different capabilities."""

    def __init__(self):
        self.task_templates = self._load_task_templates()

    def _load_task_templates(self) -> Dict[ModelCapability, List[Dict[str, Any]]]:
        """Load predefined benchmark task templates."""
        return {
            ModelCapability.TEXT_GENERATION: [
                {
                    'complexity': TaskComplexity.SIMPLE,
                    'prompt': 'Write a brief introduction about artificial intelligence in 2-3 sentences.',
                    'max_tokens': 150,
                    'evaluation_criteria': ['coherence', 'conciseness', 'factual_accuracy']
                },
                {
                    'complexity': TaskComplexity.MODERATE,
                    'prompt': 'Explain the difference between supervised and unsupervised machine learning with examples.',
                    'max_tokens': 300,
                    'evaluation_criteria': ['clarity', 'depth', 'examples_quality']
                },
                {
                    'complexity': TaskComplexity.COMPLEX,
                    'prompt': 'Write a detailed analysis of the ethical implications of AI in healthcare, covering privacy, bias, and accessibility concerns.',
                    'max_tokens': 500,
                    'evaluation_criteria': ['depth', 'balance', 'critical_thinking', 'structure']
                }
            ],
            ModelCapability.CODE_GENERATION: [
                {
                    'complexity': TaskComplexity.SIMPLE,
                    'prompt': 'Write a Python function to check if a number is prime.',
                    'max_tokens': 200,
                    'evaluation_criteria': ['correctness', 'efficiency', 'code_quality'],
                    'ground_truth': {'function_name': 'is_prime', 'handles_edge_cases': True}
                },
                {
                    'complexity': TaskComplexity.MODERATE,
                    'prompt': 'Create a Python class for a binary search tree with insert, search, and delete methods.',
                    'max_tokens': 400,
                    'evaluation_criteria': ['correctness', 'completeness', 'code_quality'],
                    'ground_truth': {'methods': ['insert', 'search', 'delete']}
                },
                {
                    'complexity': TaskComplexity.COMPLEX,
                    'prompt': 'Implement a concurrent web scraper in Python that handles rate limiting, retries, and saves results to a database.',
                    'max_tokens': 600,
                    'evaluation_criteria': ['correctness', 'concurrency', 'error_handling', 'architecture'],
                    'ground_truth': {'features': ['threading', 'rate_limiting', 'retry_logic', 'database']}
                }
            ],
            ModelCapability.REASONING: [
                {
                    'complexity': TaskComplexity.SIMPLE,
                    'prompt': 'If all roses are flowers and some flowers fade quickly, can we conclude that some roses fade quickly? Explain your reasoning.',
                    'max_tokens': 200,
                    'evaluation_criteria': ['logical_validity', 'clarity', 'correct_conclusion']
                },
                {
                    'complexity': TaskComplexity.MODERATE,
                    'prompt': 'You have 8 balls, all of equal size. 7 of them weigh the same, and one is heavier. Using a balance scale only twice, how can you find the heavier ball?',
                    'max_tokens': 300,
                    'evaluation_criteria': ['correctness', 'explanation_quality', 'step_by_step']
                },
                {
                    'complexity': TaskComplexity.EXPERT,
                    'prompt': 'Three logicians walk into a bar. The bartender asks "Do all of you want a drink?" The first logician says "I don\'t know." The second logician says "I don\'t know." The third logician says "Yes." Explain the logic behind their answers.',
                    'max_tokens': 400,
                    'evaluation_criteria': ['logical_reasoning', 'completeness', 'clarity']
                }
            ],
            ModelCapability.CHAT_COMPLETION: [
                {
                    'complexity': TaskComplexity.SIMPLE,
                    'prompt': 'Hello! Can you help me understand what a neural network is?',
                    'max_tokens': 200,
                    'evaluation_criteria': ['helpfulness', 'clarity', 'conversational_tone']
                },
                {
                    'complexity': TaskComplexity.MODERATE,
                    'prompt': 'I\'m working on a machine learning project and getting overfitting. What strategies would you recommend?',
                    'max_tokens': 350,
                    'evaluation_criteria': ['practical_advice', 'completeness', 'actionable_steps']
                }
            ]
        }

    def generate_benchmark_suite(self, capabilities: List[ModelCapability],
                                 tasks_per_capability: int = 3) -> List[BenchmarkTask]:
        """Generate a comprehensive benchmark suite."""
        tasks = []
        task_counter = 0

        for capability in capabilities:
            templates = self.task_templates.get(capability, [])[:tasks_per_capability]

            for template in templates:
                task_id = f"bench_{capability.value}_{task_counter:03d}"
                task = BenchmarkTask(
                    task_id=task_id,
                    task_type=capability,
                    complexity=template['complexity'],
                    prompt=template['prompt'],
                    max_tokens=template.get('max_tokens', 500),
                    temperature=template.get('temperature', 0.7),
                    evaluation_criteria=template.get('evaluation_criteria', []),
                    ground_truth=template.get('ground_truth'),
                    expected_output=template.get('expected_output')
                )
                tasks.append(task)
                task_counter += 1

        logger.info(f"Generated {len(tasks)} benchmark tasks across {len(capabilities)} capabilities")
        return tasks


class ModelBenchmark:
    """Benchmarks models against a suite of tasks."""

    def __init__(self, orchestrator: MultiModelOrchestrator):
        self.orchestrator = orchestrator
        self.task_generator = BenchmarkTaskGenerator()
        self.results: Dict[str, List[BenchmarkResult]] = defaultdict(list)

    async def benchmark_model(self, model_id: str,
                             tasks: Optional[List[BenchmarkTask]] = None) -> List[BenchmarkResult]:
        """Benchmark a specific model against tasks."""
        if tasks is None:
            # Generate default benchmark suite
            tasks = self.task_generator.generate_benchmark_suite(
                [ModelCapability.TEXT_GENERATION, ModelCapability.CODE_GENERATION,
                 ModelCapability.REASONING, ModelCapability.CHAT_COMPLETION]
            )

        logger.info(f"Benchmarking model {model_id} with {len(tasks)} tasks")

        results = []
        for i, task in enumerate(tasks):
            logger.info(f"Running task {i+1}/{len(tasks)}: {task.task_id}")

            try:
                result = await self._run_benchmark_task(model_id, task)
                results.append(result)
                self.results[model_id].append(result)
            except Exception as e:
                logger.error(f"Error running task {task.task_id}: {e}")
                # Record failure
                results.append(BenchmarkResult(
                    task_id=task.task_id,
                    model_id=model_id,
                    provider="unknown",
                    response_content="",
                    tokens_input=0,
                    tokens_output=0,
                    latency_ms=0,
                    cost=0,
                    quality_score=0,
                    passed=False,
                    error=str(e)
                ))

            # Small delay between requests
            await asyncio.sleep(1)

        logger.info(f"Completed benchmarking {model_id}: {len(results)} results")
        return results

    async def _run_benchmark_task(self, model_id: str, task: BenchmarkTask) -> BenchmarkResult:
        """Run a single benchmark task."""
        # Get model config
        model = self.orchestrator.registry.get_model(model_id)
        if not model:
            raise ValueError(f"Model {model_id} not found in registry")

        # Create request
        request = ModelRequest(
            task_type=task.task_type,
            prompt=task.prompt,
            max_tokens=task.max_tokens,
            temperature=task.temperature,
            complexity=task.complexity,
            preferred_provider=model.provider
        )

        # Execute request
        start_time = time.time()
        response = await self.orchestrator.executor.execute(model, request)
        latency_ms = (time.time() - start_time) * 1000

        # Evaluate response quality
        quality_score = self._evaluate_response_quality(
            response.content,
            task.evaluation_criteria,
            task.ground_truth
        )

        # Determine if task passed
        passed = quality_score >= 0.7  # 70% threshold

        return BenchmarkResult(
            task_id=task.task_id,
            model_id=model_id,
            provider=model.provider.value,
            response_content=response.content,
            tokens_input=response.tokens_input,
            tokens_output=response.tokens_output,
            latency_ms=latency_ms,
            cost=response.cost,
            quality_score=quality_score,
            passed=passed
        )

    def _evaluate_response_quality(self, response: str, criteria: List[str],
                                  ground_truth: Optional[Any] = None) -> float:
        """Evaluate response quality based on criteria."""
        if not criteria:
            return 0.8  # Default score if no criteria

        scores = []

        # Simple heuristic-based evaluation
        # In production, this would use more sophisticated evaluation methods

        for criterion in criteria:
            if criterion == 'coherence':
                # Check for coherent sentences
                score = min(1.0, len(response.split('.')) / 3)
                scores.append(score)

            elif criterion == 'conciseness':
                # Penalize overly long responses
                word_count = len(response.split())
                score = 1.0 if word_count < 200 else max(0.5, 1.0 - (word_count - 200) / 200)
                scores.append(score)

            elif criterion == 'factual_accuracy':
                # Simple keyword check (would use fact-checking in production)
                score = 0.8  # Placeholder
                scores.append(score)

            elif criterion == 'correctness':
                # Check against ground truth if available
                if ground_truth:
                    score = self._check_ground_truth(response, ground_truth)
                else:
                    score = 0.8  # Placeholder
                scores.append(score)

            elif criterion == 'code_quality':
                # Check for common code quality indicators
                has_functions = 'def ' in response
                has_docstrings = '"""' in response or "'''" in response
                has_comments = '#' in response
                score = (has_functions * 0.5 + has_docstrings * 0.3 + has_comments * 0.2)
                scores.append(score)

            elif criterion in ['clarity', 'depth', 'helpfulness']:
                # Length-based heuristic (would use NLP models in production)
                word_count = len(response.split())
                score = min(1.0, word_count / 100)
                scores.append(score)

            else:
                # Default score for unknown criteria
                scores.append(0.75)

        return np.mean(scores) if scores else 0.7

    def _check_ground_truth(self, response: str, ground_truth: Dict[str, Any]) -> float:
        """Check response against ground truth."""
        score = 0.0
        checks = 0

        for key, value in ground_truth.items():
            checks += 1
            if isinstance(value, str):
                if value.lower() in response.lower():
                    score += 1.0
            elif isinstance(value, list):
                # Check if all items present
                present = sum(1 for item in value if str(item).lower() in response.lower())
                score += present / len(value)
            elif isinstance(value, bool):
                # Boolean checks are binary
                if value:
                    score += 1.0

        return score / checks if checks > 0 else 0.5

    def generate_report(self, model_id: str) -> ModelBenchmarkReport:
        """Generate comprehensive benchmark report for a model."""
        results = self.results.get(model_id, [])

        if not results:
            raise ValueError(f"No benchmark results for model {model_id}")

        # Get model info
        model = self.orchestrator.registry.get_model(model_id)
        if not model:
            raise ValueError(f"Model {model_id} not found")

        # Calculate aggregate metrics
        successful = [r for r in results if not r.error]
        failed = [r for r in results if r.error]

        latencies = [r.latency_ms for r in successful]
        costs = [r.cost for r in successful]
        quality_scores = [r.quality_score for r in successful]

        # Group by complexity
        by_complexity = defaultdict(list)
        for r in results:
            # Get task to find complexity
            by_complexity['unknown'].append(r)  # Simplified

        # Group by task type
        by_task_type = defaultdict(list)
        for r in results:
            by_task_type['unknown'].append(r)  # Simplified

        # Generate recommendations
        recommendations = self._generate_recommendations(model_id, results)

        return ModelBenchmarkReport(
            model_id=model_id,
            model_name=model.name,
            provider=model.provider.value,
            total_tasks=len(results),
            successful_tasks=len(successful),
            failed_tasks=len(failed),
            avg_latency_ms=np.mean(latencies) if latencies else 0,
            p95_latency_ms=np.percentile(latencies, 95) if latencies else 0,
            p99_latency_ms=np.percentile(latencies, 99) if latencies else 0,
            total_cost=sum(costs),
            avg_cost_per_task=np.mean(costs) if costs else 0,
            avg_quality_score=np.mean(quality_scores) if quality_scores else 0,
            pass_rate=sum(1 for r in results if r.passed) / len(results) * 100,
            results_by_complexity={},
            results_by_task_type={},
            recommendations=recommendations
        )

    def _generate_recommendations(self, model_id: str, results: List[BenchmarkResult]) -> List[str]:
        """Generate recommendations based on benchmark results."""
        recommendations = []

        # Quality recommendations
        avg_quality = np.mean([r.quality_score for r in results if not r.error])
        if avg_quality < 0.6:
            recommendations.append(
                "Consider using a more capable model for better quality results"
            )

        # Cost recommendations
        total_cost = sum(r.cost for r in results)
        if total_cost > 1.0:
            recommendations.append(
                "High cost detected - consider using cheaper models for simple tasks"
            )

        # Latency recommendations
        avg_latency = np.mean([r.latency_ms for r in results if not r.error])
        if avg_latency > 3000:
            recommendations.append(
                "High latency detected - consider using faster models or local alternatives"
            )

        # Success rate recommendations
        success_rate = sum(1 for r in results if r.passed) / len(results)
        if success_rate < 0.8:
            recommendations.append(
                f"Low pass rate ({success_rate:.1%}) - review failed tasks and adjust parameters"
            )

        return recommendations


class ComparativeBenchmark:
    """Compare multiple models across the same benchmark suite."""

    def __init__(self, orchestrator: MultiModelOrchestrator):
        self.orchestrator = orchestrator
        self.benchmarker = ModelBenchmark(orchestrator)

    async def compare_models(self, model_ids: List[str],
                            tasks: Optional[List[BenchmarkTask]] = None) -> Dict[str, Any]:
        """Run comparative benchmark across multiple models."""
        if tasks is None:
            tasks = self.benchmarker.task_generator.generate_benchmark_suite(
                [ModelCapability.TEXT_GENERATION, ModelCapability.CODE_GENERATION,
                 ModelCapability.REASONING, ModelCapability.CHAT_COMPLETION]
            )

        logger.info(f"Running comparative benchmark for {len(model_ids)} models")

        # Benchmark each model
        reports = {}
        for model_id in model_ids:
            logger.info(f"Benchmarking {model_id}...")
            await self.benchmarker.benchmark_model(model_id, tasks)
            reports[model_id] = self.benchmarker.generate_report(model_id)

        # Generate comparison
        comparison = self._generate_comparison(reports)

        return comparison

    def _generate_comparison(self, reports: Dict[str, ModelBenchmarkReport]) -> Dict[str, Any]:
        """Generate comparative analysis."""
        comparison = {
            'models_compared': len(reports),
            'timestamp': datetime.utcnow().isoformat(),
            'summary': {},
            'rankings': {},
            'recommendations': []
        }

        # Quality ranking
        quality_scores = [(model_id, report.avg_quality_score)
                         for model_id, report in reports.items()]
        quality_scores.sort(key=lambda x: x[1], reverse=True)
        comparison['rankings']['quality'] = [
            {'model_id': m, 'score': s} for m, s in quality_scores
        ]

        # Cost ranking (lower is better)
        cost_scores = [(model_id, report.avg_cost_per_task)
                      for model_id, report in reports.items()]
        cost_scores.sort(key=lambda x: x[1])
        comparison['rankings']['cost_efficiency'] = [
            {'model_id': m, 'avg_cost': c} for m, c in cost_scores
        ]

        # Speed ranking (lower latency is better)
        speed_scores = [(model_id, report.avg_latency_ms)
                       for model_id, report in reports.items()]
        speed_scores.sort(key=lambda x: x[1])
        comparison['rankings']['speed'] = [
            {'model_id': m, 'avg_latency_ms': l} for m, l in speed_scores
        ]

        # Value ranking (quality per dollar)
        value_scores = [(model_id, report.avg_quality_score / max(report.avg_cost_per_task, 0.0001))
                       for model_id, report in reports.items()]
        value_scores.sort(key=lambda x: x[1], reverse=True)
        comparison['rankings']['value'] = [
            {'model_id': m, 'value_score': v} for m, v in value_scores
        ]

        # Generate recommendations
        best_quality = quality_scores[0][0]
        best_cost = cost_scores[0][0]
        best_speed = speed_scores[0][0]
        best_value = value_scores[0][0]

        comparison['recommendations'] = [
            f"For best quality: Use {best_quality}",
            f"For lowest cost: Use {best_cost}",
            f"For fastest response: Use {best_speed}",
            f"For best value: Use {best_value}"
        ]

        # Detailed comparison per model
        comparison['detailed_comparison'] = {
            model_id: {
                'quality_score': report.avg_quality_score,
                'avg_cost': report.avg_cost_per_task,
                'avg_latency_ms': report.avg_latency_ms,
                'pass_rate': report.pass_rate,
                'total_tasks': report.total_tasks,
                'successful_tasks': report.successful_tasks
            }
            for model_id, report in reports.items()
        }

        return comparison

    def visualize_comparison(self, comparison: Dict[str, Any], output_path: Path):
        """Generate visualization of model comparison."""
        models = list(comparison['detailed_comparison'].keys())
        data = comparison['detailed_comparison']

        # Create subplots
        fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(15, 12))

        # Quality scores
        quality_scores = [data[m]['quality_score'] for m in models]
        ax1.bar(models, quality_scores, color='skyblue')
        ax1.set_ylabel('Quality Score')
        ax1.set_title('Average Quality Score by Model')
        ax1.set_ylim(0, 1)
        plt.setp(ax1.xaxis.get_majorticklabels(), rotation=45, ha='right')

        # Cost comparison
        costs = [data[m]['avg_cost'] * 1000 for m in models]  # Convert to per 1000 tasks
        ax2.bar(models, costs, color='coral')
        ax2.set_ylabel('Cost per 1000 Tasks ($)')
        ax2.set_title('Cost Efficiency by Model')
        plt.setp(ax2.xaxis.get_majorticklabels(), rotation=45, ha='right')

        # Latency comparison
        latencies = [data[m]['avg_latency_ms'] for m in models]
        ax3.bar(models, latencies, color='lightgreen')
        ax3.set_ylabel('Latency (ms)')
        ax3.set_title('Average Latency by Model')
        plt.setp(ax3.xaxis.get_majorticklabels(), rotation=45, ha='right')

        # Pass rate
        pass_rates = [data[m]['pass_rate'] for m in models]
        ax4.bar(models, pass_rates, color='gold')
        ax4.set_ylabel('Pass Rate (%)')
        ax4.set_title('Task Pass Rate by Model')
        ax4.set_ylim(0, 100)
        plt.setp(ax4.xaxis.get_majorticklabels(), rotation=45, ha='right')

        plt.tight_layout()
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        plt.close()

        logger.info(f"Saved comparison visualization to {output_path}")


# Global benchmark instance
benchmark_system: Optional[ModelBenchmark] = None
comparative_benchmark: Optional[ComparativeBenchmark] = None