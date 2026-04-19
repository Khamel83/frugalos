"""
API routes for AI model orchestration and management.

This module provides REST endpoints for:
- Model selection and execution
- Model performance monitoring
- Benchmarking and comparison
- Model registry management
"""

import asyncio
from datetime import datetime
from typing import Dict, Any, Optional, List
from flask import Blueprint, jsonify, request
import logging

from ..models.model_orchestrator import (
    MultiModelOrchestrator, ModelRequest, ModelCapability,
    TaskComplexity, ModelProvider, orchestrator
)
from ..models.model_benchmarking import (
    ModelBenchmark, ComparativeBenchmark, BenchmarkTask,
    benchmark_system, comparative_benchmark
)

logger = logging.getLogger(__name__)

# Create blueprint for model routes
models_bp = Blueprint('models', __name__, url_prefix='/api/models')


@models_bp.route('/completions', methods=['POST'])
def create_completion():
    """
    Execute an AI completion request with intelligent model routing.

    Request body:
    {
        "prompt": "Your prompt here",
        "task_type": "text_generation|code_generation|chat_completion|reasoning",
        "max_tokens": 500,
        "temperature": 0.7,
        "complexity": "simple|moderate|complex|expert",
        "budget_cents": 0.10,  // optional
        "latency_requirement_ms": 2000,  // optional
        "preferred_provider": "openai|anthropic|ollama"  // optional
    }
    """
    try:
        data = request.get_json()

        if not data or 'prompt' not in data:
            return jsonify({'error': 'Missing prompt field'}), 400

        # Parse task type
        task_type_str = data.get('task_type', 'text_generation')
        try:
            task_type = ModelCapability[task_type_str.upper()]
        except KeyError:
            return jsonify({'error': f'Invalid task_type: {task_type_str}'}), 400

        # Parse complexity
        complexity_str = data.get('complexity', 'moderate')
        try:
            complexity = TaskComplexity[complexity_str.upper()]
        except KeyError:
            return jsonify({'error': f'Invalid complexity: {complexity_str}'}), 400

        # Parse preferred provider if specified
        preferred_provider = None
        if 'preferred_provider' in data:
            try:
                preferred_provider = ModelProvider[data['preferred_provider'].upper()]
            except KeyError:
                return jsonify({'error': f'Invalid provider: {data["preferred_provider"]}'}), 400

        # Create model request
        model_request = ModelRequest(
            task_type=task_type,
            prompt=data['prompt'],
            max_tokens=data.get('max_tokens', 500),
            temperature=data.get('temperature', 0.7),
            complexity=complexity,
            budget_cents=data.get('budget_cents'),
            latency_requirement_ms=data.get('latency_requirement_ms'),
            preferred_provider=preferred_provider,
            metadata=data.get('metadata', {})
        )

        # Process request
        if not orchestrator:
            return jsonify({'error': 'Model orchestrator not initialized'}), 503

        response = asyncio.run(orchestrator.process_request(
            model_request,
            enable_fallback=data.get('enable_fallback', True)
        ))

        # Return response
        return jsonify({
            'success': True,
            'model_id': response.model_id,
            'provider': response.provider.value,
            'content': response.content,
            'tokens': {
                'input': response.tokens_input,
                'output': response.tokens_output,
                'total': response.tokens_input + response.tokens_output
            },
            'latency_ms': response.latency_ms,
            'cost': response.cost,
            'finish_reason': response.finish_reason,
            'cached': response.cached,
            'metadata': response.metadata
        }), 200

    except Exception as e:
        logger.error(f"Error processing completion request: {e}")
        return jsonify({'error': str(e)}), 500


@models_bp.route('/registry', methods=['GET'])
def list_models():
    """List all registered models with their configurations."""
    try:
        if not orchestrator:
            return jsonify({'error': 'Model orchestrator not initialized'}), 503

        models = []
        for model_id, config in orchestrator.registry.models.items():
            metrics = orchestrator.registry.get_performance_metrics(model_id)

            models.append({
                'model_id': model_id,
                'name': config.name,
                'provider': config.provider.value,
                'capabilities': [c.value for c in config.capabilities],
                'max_tokens': config.max_tokens,
                'context_window': config.context_window,
                'cost': {
                    'input_per_1k': config.cost_per_1k_input_tokens,
                    'output_per_1k': config.cost_per_1k_output_tokens
                },
                'priority': config.priority,
                'enabled': config.enabled,
                'performance': {
                    'avg_latency_ms': metrics.avg_latency_ms if metrics else 0,
                    'success_rate': metrics.success_rate if metrics else 100.0,
                    'total_requests': metrics.total_requests if metrics else 0,
                    'total_cost': metrics.total_cost if metrics else 0.0
                } if metrics else None
            })

        return jsonify({
            'models': models,
            'count': len(models)
        }), 200

    except Exception as e:
        logger.error(f"Error listing models: {e}")
        return jsonify({'error': str(e)}), 500


@models_bp.route('/registry/<model_id>', methods=['GET'])
def get_model_details(model_id: str):
    """Get detailed information about a specific model."""
    try:
        if not orchestrator:
            return jsonify({'error': 'Model orchestrator not initialized'}), 503

        config = orchestrator.registry.get_model(model_id)
        if not config:
            return jsonify({'error': f'Model {model_id} not found'}), 404

        metrics = orchestrator.registry.get_performance_metrics(model_id)

        return jsonify({
            'model_id': model_id,
            'name': config.name,
            'provider': config.provider.value,
            'capabilities': [c.value for c in config.capabilities],
            'limits': {
                'max_tokens': config.max_tokens,
                'context_window': config.context_window
            },
            'cost': {
                'input_per_1k_tokens': config.cost_per_1k_input_tokens,
                'output_per_1k_tokens': config.cost_per_1k_output_tokens
            },
            'priority': config.priority,
            'enabled': config.enabled,
            'metadata': config.metadata,
            'performance': {
                'total_requests': metrics.total_requests,
                'successful_requests': metrics.successful_requests,
                'failed_requests': metrics.failed_requests,
                'success_rate': metrics.success_rate,
                'tokens': {
                    'total_input': metrics.total_tokens_input,
                    'total_output': metrics.total_tokens_output
                },
                'cost': {
                    'total': metrics.total_cost,
                    'avg_per_request': metrics.total_cost / metrics.total_requests if metrics.total_requests > 0 else 0
                },
                'latency': {
                    'avg_ms': metrics.avg_latency_ms,
                    'p95_ms': metrics.p95_latency_ms,
                    'p99_ms': metrics.p99_latency_ms
                },
                'last_used': metrics.last_used.isoformat() if metrics.last_used else None,
                'last_error': metrics.last_error
            } if metrics else None
        }), 200

    except Exception as e:
        logger.error(f"Error getting model details: {e}")
        return jsonify({'error': str(e)}), 500


@models_bp.route('/statistics', methods=['GET'])
def get_statistics():
    """Get orchestrator statistics and usage summary."""
    try:
        if not orchestrator:
            return jsonify({'error': 'Model orchestrator not initialized'}), 503

        hours = request.args.get('hours', 24, type=int)
        stats = orchestrator.get_statistics(hours=hours)

        return jsonify(stats), 200

    except Exception as e:
        logger.error(f"Error getting statistics: {e}")
        return jsonify({'error': str(e)}), 500


@models_bp.route('/metrics', methods=['GET'])
def get_all_metrics():
    """Get performance metrics for all models."""
    try:
        if not orchestrator:
            return jsonify({'error': 'Model orchestrator not initialized'}), 503

        all_metrics = orchestrator.registry.get_all_metrics()

        metrics_summary = {}
        for model_id, metrics in all_metrics.items():
            metrics_summary[model_id] = {
                'total_requests': metrics.total_requests,
                'successful_requests': metrics.successful_requests,
                'failed_requests': metrics.failed_requests,
                'success_rate': metrics.success_rate,
                'avg_latency_ms': metrics.avg_latency_ms,
                'p95_latency_ms': metrics.p95_latency_ms,
                'p99_latency_ms': metrics.p99_latency_ms,
                'total_cost': metrics.total_cost,
                'total_tokens': metrics.total_tokens_input + metrics.total_tokens_output,
                'last_used': metrics.last_used.isoformat() if metrics.last_used else None
            }

        return jsonify({
            'metrics': metrics_summary,
            'timestamp': datetime.utcnow().isoformat()
        }), 200

    except Exception as e:
        logger.error(f"Error getting metrics: {e}")
        return jsonify({'error': str(e)}), 500


@models_bp.route('/benchmark/run', methods=['POST'])
def run_benchmark():
    """
    Run benchmark for specific model(s).

    Request body:
    {
        "model_ids": ["gpt-3.5-turbo", "claude-3-haiku-20240307"],
        "capabilities": ["text_generation", "code_generation"],  // optional
        "tasks_per_capability": 3  // optional
    }
    """
    try:
        data = request.get_json()

        if not data or 'model_ids' not in data:
            return jsonify({'error': 'Missing model_ids field'}), 400

        model_ids = data['model_ids']
        if not isinstance(model_ids, list) or not model_ids:
            return jsonify({'error': 'model_ids must be a non-empty list'}), 400

        if not benchmark_system:
            return jsonify({'error': 'Benchmark system not initialized'}), 503

        # Generate tasks if capabilities specified
        tasks = None
        if 'capabilities' in data:
            try:
                capabilities = [ModelCapability[c.upper()] for c in data['capabilities']]
                tasks = benchmark_system.task_generator.generate_benchmark_suite(
                    capabilities,
                    tasks_per_capability=data.get('tasks_per_capability', 3)
                )
            except KeyError as e:
                return jsonify({'error': f'Invalid capability: {e}'}), 400

        # Run benchmarks
        results = {}
        for model_id in model_ids:
            try:
                logger.info(f"Running benchmark for {model_id}")
                benchmark_results = asyncio.run(
                    benchmark_system.benchmark_model(model_id, tasks)
                )
                report = benchmark_system.generate_report(model_id)

                results[model_id] = {
                    'total_tasks': report.total_tasks,
                    'successful_tasks': report.successful_tasks,
                    'failed_tasks': report.failed_tasks,
                    'avg_quality_score': report.avg_quality_score,
                    'avg_latency_ms': report.avg_latency_ms,
                    'total_cost': report.total_cost,
                    'pass_rate': report.pass_rate,
                    'recommendations': report.recommendations
                }
            except Exception as e:
                logger.error(f"Error benchmarking {model_id}: {e}")
                results[model_id] = {'error': str(e)}

        return jsonify({
            'success': True,
            'results': results,
            'timestamp': datetime.utcnow().isoformat()
        }), 200

    except Exception as e:
        logger.error(f"Error running benchmark: {e}")
        return jsonify({'error': str(e)}), 500


@models_bp.route('/benchmark/compare', methods=['POST'])
def compare_models():
    """
    Run comparative benchmark across multiple models.

    Request body:
    {
        "model_ids": ["gpt-3.5-turbo", "claude-3-haiku-20240307", "llama3.1:8b-instruct"],
        "capabilities": ["text_generation", "code_generation"]  // optional
    }
    """
    try:
        data = request.get_json()

        if not data or 'model_ids' not in data:
            return jsonify({'error': 'Missing model_ids field'}), 400

        model_ids = data['model_ids']
        if not isinstance(model_ids, list) or len(model_ids) < 2:
            return jsonify({'error': 'model_ids must contain at least 2 models'}), 400

        if not comparative_benchmark:
            return jsonify({'error': 'Comparative benchmark not initialized'}), 503

        # Generate tasks if capabilities specified
        tasks = None
        if 'capabilities' in data:
            try:
                capabilities = [ModelCapability[c.upper()] for c in data['capabilities']]
                tasks = comparative_benchmark.benchmarker.task_generator.generate_benchmark_suite(
                    capabilities,
                    tasks_per_capability=3
                )
            except KeyError as e:
                return jsonify({'error': f'Invalid capability: {e}'}), 400

        # Run comparison
        comparison = asyncio.run(
            comparative_benchmark.compare_models(model_ids, tasks)
        )

        return jsonify({
            'success': True,
            'comparison': comparison,
            'timestamp': datetime.utcnow().isoformat()
        }), 200

    except Exception as e:
        logger.error(f"Error comparing models: {e}")
        return jsonify({'error': str(e)}), 500


@models_bp.route('/benchmark/reports/<model_id>', methods=['GET'])
def get_benchmark_report(model_id: str):
    """Get benchmark report for a specific model."""
    try:
        if not benchmark_system:
            return jsonify({'error': 'Benchmark system not initialized'}), 503

        if model_id not in benchmark_system.results:
            return jsonify({'error': f'No benchmark results for model {model_id}'}), 404

        report = benchmark_system.generate_report(model_id)

        return jsonify({
            'model_id': report.model_id,
            'model_name': report.model_name,
            'provider': report.provider,
            'summary': {
                'total_tasks': report.total_tasks,
                'successful_tasks': report.successful_tasks,
                'failed_tasks': report.failed_tasks,
                'pass_rate': report.pass_rate
            },
            'performance': {
                'avg_latency_ms': report.avg_latency_ms,
                'p95_latency_ms': report.p95_latency_ms,
                'p99_latency_ms': report.p99_latency_ms
            },
            'cost': {
                'total': report.total_cost,
                'avg_per_task': report.avg_cost_per_task
            },
            'quality': {
                'avg_score': report.avg_quality_score
            },
            'recommendations': report.recommendations,
            'timestamp': report.timestamp.isoformat()
        }), 200

    except Exception as e:
        logger.error(f"Error getting benchmark report: {e}")
        return jsonify({'error': str(e)}), 500


@models_bp.route('/select', methods=['POST'])
def select_model():
    """
    Get model selection recommendation without executing.

    Request body:
    {
        "task_type": "text_generation",
        "complexity": "moderate",
        "budget_cents": 0.05,
        "latency_requirement_ms": 1500
    }
    """
    try:
        data = request.get_json()

        if not data or 'task_type' not in data:
            return jsonify({'error': 'Missing task_type field'}), 400

        # Parse task type
        try:
            task_type = ModelCapability[data['task_type'].upper()]
        except KeyError:
            return jsonify({'error': f'Invalid task_type: {data["task_type"]}'}), 400

        # Parse complexity
        complexity_str = data.get('complexity', 'moderate')
        try:
            complexity = TaskComplexity[complexity_str.upper()]
        except KeyError:
            return jsonify({'error': f'Invalid complexity: {complexity_str}'}), 400

        # Create model request (with dummy prompt for selection)
        model_request = ModelRequest(
            task_type=task_type,
            prompt="",  # Not needed for selection
            max_tokens=data.get('max_tokens', 500),
            complexity=complexity,
            budget_cents=data.get('budget_cents'),
            latency_requirement_ms=data.get('latency_requirement_ms')
        )

        if not orchestrator:
            return jsonify({'error': 'Model orchestrator not initialized'}), 503

        # Select model
        selected_model = orchestrator.selector.select_model(model_request)

        if not selected_model:
            return jsonify({'error': 'No suitable model found for requirements'}), 404

        # Get performance metrics
        metrics = orchestrator.registry.get_performance_metrics(selected_model.model_id)

        return jsonify({
            'selected_model': {
                'model_id': selected_model.model_id,
                'name': selected_model.name,
                'provider': selected_model.provider.value,
                'capabilities': [c.value for c in selected_model.capabilities],
                'priority': selected_model.priority,
                'cost': {
                    'input_per_1k': selected_model.cost_per_1k_input_tokens,
                    'output_per_1k': selected_model.cost_per_1k_output_tokens
                },
                'performance': {
                    'avg_latency_ms': metrics.avg_latency_ms if metrics else selected_model.avg_latency_ms,
                    'success_rate': metrics.success_rate if metrics else 100.0
                } if metrics else None
            },
            'selection_criteria': {
                'task_type': task_type.value,
                'complexity': complexity.value,
                'budget_cents': data.get('budget_cents'),
                'latency_requirement_ms': data.get('latency_requirement_ms')
            }
        }), 200

    except Exception as e:
        logger.error(f"Error selecting model: {e}")
        return jsonify({'error': str(e)}), 500


@models_bp.route('/health', methods=['GET'])
def health_check():
    """Health check for model orchestration system."""
    try:
        health_status = {
            'timestamp': datetime.utcnow().isoformat(),
            'components': {
                'orchestrator': 'available' if orchestrator else 'unavailable',
                'benchmark_system': 'available' if benchmark_system else 'unavailable',
                'comparative_benchmark': 'available' if comparative_benchmark else 'unavailable'
            },
            'status': 'healthy'
        }

        # Check if orchestrator is working
        if orchestrator:
            model_count = len(orchestrator.registry.models)
            health_status['model_count'] = model_count
            health_status['providers'] = list(set(
                m.provider.value for m in orchestrator.registry.models.values()
            ))

        # Check if any critical components are down
        if not orchestrator:
            health_status['status'] = 'unhealthy'

        status_code = 200 if health_status['status'] == 'healthy' else 503
        return jsonify(health_status), status_code

    except Exception as e:
        logger.error(f"Error in health check: {e}")
        return jsonify({
            'status': 'unhealthy',
            'error': str(e),
            'timestamp': datetime.utcnow().isoformat()
        }), 503


# Error handlers
@models_bp.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Endpoint not found'}), 404


@models_bp.errorhandler(500)
def internal_error(error):
    logger.error(f"Internal error: {error}")
    return jsonify({'error': 'Internal server error'}), 500
