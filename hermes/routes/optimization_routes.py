"""
Optimization and performance monitoring routes for Hermes AI Assistant.

This module provides REST API endpoints for:
- Performance monitoring and metrics
- Database query optimization
- Cache management
- Resource optimization
- Auto-scaling management
- Cost analysis
"""

import asyncio
from datetime import datetime
from typing import Dict, Any, Optional
from flask import Blueprint, jsonify, request
import logging

logger = logging.getLogger(__name__)

# Create blueprint for optimization routes
optimization_bp = Blueprint('optimization', __name__, url_prefix='/api/optimization')


@optimization_bp.route('/performance/summary', methods=['GET'])
def get_performance_summary():
    """Get comprehensive performance summary."""
    try:
        from hermes.monitoring.performance_monitor import performance_collector
        from hermes.optimization.resource_optimizer import resource_monitor

        hours = request.args.get('hours', 1, type=int)

        summary = {}

        # Get performance metrics
        if performance_collector and performance_collector.metrics_history:
            summary['performance'] = performance_collector.get_metrics_summary(hours)

        # Get resource metrics
        if resource_monitor and resource_monitor.metrics_history:
            summary['resources'] = resource_monitor.get_metrics_summary(hours)

        summary['timestamp'] = datetime.utcnow().isoformat()

        return jsonify(summary), 200

    except Exception as e:
        logger.error(f"Error getting performance summary: {e}")
        return jsonify({'error': str(e)}), 500


@optimization_bp.route('/database/slow-queries', methods=['GET'])
def get_slow_queries():
    """Get slow database queries."""
    try:
        from hermes.monitoring.database_optimizer import db_performance_monitor

        if not db_performance_monitor:
            return jsonify({'error': 'Database monitoring not available'}), 503

        limit = request.args.get('limit', 10, type=int)
        slow_queries = db_performance_monitor.slow_queries[-limit:]

        return jsonify({
            'slow_queries': slow_queries,
            'count': len(slow_queries),
            'threshold': db_performance_monitor.query_analyzer.slow_query_threshold if hasattr(db_performance_monitor, 'query_analyzer') else 0.5
        }), 200

    except Exception as e:
        logger.error(f"Error getting slow queries: {e}")
        return jsonify({'error': str(e)}), 500


@optimization_bp.route('/database/report', methods=['GET'])
def get_database_performance_report():
    """Get comprehensive database performance report."""
    try:
        from hermes.monitoring.database_optimizer import db_performance_monitor

        if not db_performance_monitor:
            return jsonify({'error': 'Database monitoring not available'}), 503

        # Get performance report
        report = asyncio.run(db_performance_monitor.get_performance_report())

        return jsonify(report), 200

    except Exception as e:
        logger.error(f"Error getting database report: {e}")
        return jsonify({'error': str(e)}), 500


@optimization_bp.route('/database/index-recommendations', methods=['GET'])
def get_index_recommendations():
    """Get index optimization recommendations."""
    try:
        from hermes.monitoring.database_optimizer import db_performance_monitor

        if not db_performance_monitor:
            return jsonify({'error': 'Database monitoring not available'}), 503

        table_name = request.args.get('table')

        # Get index recommendations
        recommendations = asyncio.run(
            db_performance_monitor.index_optimizer.suggest_indexes(table_name)
        )

        return jsonify({
            'recommendations': [
                {
                    'table': rec.table_name,
                    'columns': rec.columns,
                    'type': rec.index_type,
                    'estimated_improvement': rec.estimated_improvement,
                    'reason': rec.reason
                }
                for rec in recommendations
            ],
            'count': len(recommendations)
        }), 200

    except Exception as e:
        logger.error(f"Error getting index recommendations: {e}")
        return jsonify({'error': str(e)}), 500


@optimization_bp.route('/cache/stats', methods=['GET'])
def get_cache_stats():
    """Get cache performance statistics."""
    try:
        from hermes.caching.advanced_cache import multi_tier_cache

        if not multi_tier_cache:
            return jsonify({'error': 'Cache system not available'}), 503

        stats = multi_tier_cache.get_stats()

        return jsonify(stats), 200

    except Exception as e:
        logger.error(f"Error getting cache stats: {e}")
        return jsonify({'error': str(e)}), 500


@optimization_bp.route('/cache/invalidate', methods=['POST'])
def invalidate_cache():
    """Invalidate cache entries by tag."""
    try:
        from hermes.caching.advanced_cache import multi_tier_cache

        if not multi_tier_cache:
            return jsonify({'error': 'Cache system not available'}), 503

        data = request.get_json()
        tag = data.get('tag')

        if not tag:
            return jsonify({'error': 'Tag is required'}), 400

        # Invalidate cache
        count = asyncio.run(multi_tier_cache.invalidate_by_tag(tag))

        return jsonify({
            'success': True,
            'entries_invalidated': count,
            'tag': tag
        }), 200

    except Exception as e:
        logger.error(f"Error invalidating cache: {e}")
        return jsonify({'error': str(e)}), 500


@optimization_bp.route('/cache/clear', methods=['POST'])
def clear_cache():
    """Clear entire cache."""
    try:
        from hermes.caching.advanced_cache import multi_tier_cache

        if not multi_tier_cache:
            return jsonify({'error': 'Cache system not available'}), 503

        # Clear L1 cache
        multi_tier_cache.l1_cache.clear()

        return jsonify({
            'success': True,
            'message': 'Cache cleared successfully'
        }), 200

    except Exception as e:
        logger.error(f"Error clearing cache: {e}")
        return jsonify({'error': str(e)}), 500


@optimization_bp.route('/resources/current', methods=['GET'])
def get_current_resources():
    """Get current resource usage."""
    try:
        from hermes.optimization.resource_optimizer import resource_monitor

        if not resource_monitor:
            return jsonify({'error': 'Resource monitoring not available'}), 503

        # Get current metrics
        metrics = asyncio.run(resource_monitor.collect_metrics())

        return jsonify({
            'timestamp': metrics.timestamp.isoformat(),
            'cpu_percent': metrics.cpu_percent,
            'memory_percent': metrics.memory_percent,
            'memory_used_mb': metrics.memory_used_mb,
            'disk_usage_percent': metrics.disk_usage_percent,
            'network': {
                'bytes_sent': metrics.network_bytes_sent,
                'bytes_recv': metrics.network_bytes_recv
            },
            'gpu': {
                'utilization': metrics.gpu_utilization,
                'memory_used': metrics.gpu_memory_used
            } if metrics.gpu_utilization else None,
            'kubernetes': {
                'pod_count': metrics.pod_count,
                'node_count': metrics.node_count
            } if metrics.pod_count else None
        }), 200

    except Exception as e:
        logger.error(f"Error getting current resources: {e}")
        return jsonify({'error': str(e)}), 500


@optimization_bp.route('/resources/prediction', methods=['GET'])
def get_resource_prediction():
    """Get resource usage predictions."""
    try:
        from hermes.optimization.resource_optimizer import resource_monitor, ResourcePredictor, ResourceType

        if not resource_monitor:
            return jsonify({'error': 'Resource monitoring not available'}), 503

        resource_type_str = request.args.get('type', 'cpu')
        prediction_window = request.args.get('window', 60, type=int)

        # Map resource type
        resource_type_map = {
            'cpu': ResourceType.CPU,
            'memory': ResourceType.MEMORY,
            'disk': ResourceType.DISK
        }

        resource_type = resource_type_map.get(resource_type_str)
        if not resource_type:
            return jsonify({'error': f'Invalid resource type: {resource_type_str}'}), 400

        # Get prediction
        predictor = ResourcePredictor(prediction_window=prediction_window)
        prediction = predictor.predict_resource_usage(
            resource_monitor.metrics_history,
            resource_type
        )

        return jsonify(prediction), 200

    except Exception as e:
        logger.error(f"Error getting resource prediction: {e}")
        return jsonify({'error': str(e)}), 500


@optimization_bp.route('/scaling/decisions', methods=['GET'])
def get_scaling_decisions():
    """Get recent auto-scaling decisions."""
    try:
        from hermes.optimization.resource_optimizer import auto_scaler

        if not auto_scaler:
            return jsonify({'error': 'Auto-scaler not available'}), 503

        limit = request.args.get('limit', 10, type=int)
        decisions = list(auto_scaler.scaling_history)[-limit:]

        return jsonify({
            'decisions': [
                {
                    'timestamp': d['timestamp'].isoformat(),
                    'resource_type': d['decision'].resource_type.value,
                    'direction': d['decision'].direction.value,
                    'current_value': d['decision'].current_value,
                    'threshold': d['decision'].threshold_value,
                    'target_replicas': d['decision'].target_replicas,
                    'reason': d['decision'].reason,
                    'confidence': d['decision'].confidence,
                    'cost_impact': d['decision'].estimated_cost_impact
                }
                for d in decisions
            ],
            'count': len(decisions)
        }), 200

    except Exception as e:
        logger.error(f"Error getting scaling decisions: {e}")
        return jsonify({'error': str(e)}), 500


@optimization_bp.route('/scaling/evaluate', methods=['POST'])
def evaluate_scaling():
    """Manually trigger scaling evaluation."""
    try:
        from hermes.optimization.resource_optimizer import auto_scaler, resource_monitor

        if not auto_scaler or not resource_monitor:
            return jsonify({'error': 'Auto-scaler not available'}), 503

        # Get current metrics and evaluate
        current_metrics = asyncio.run(resource_monitor.collect_metrics())
        decisions = asyncio.run(
            auto_scaler.evaluate_scaling(current_metrics, resource_monitor.metrics_history)
        )

        return jsonify({
            'decisions': [
                {
                    'resource_type': d.resource_type.value,
                    'direction': d.direction.value,
                    'current_value': d.current_value,
                    'threshold': d.threshold_value,
                    'target_replicas': d.target_replicas,
                    'reason': d.reason,
                    'confidence': d.confidence,
                    'cost_impact': d.estimated_cost_impact
                }
                for d in decisions
            ],
            'count': len(decisions),
            'timestamp': datetime.utcnow().isoformat()
        }), 200

    except Exception as e:
        logger.error(f"Error evaluating scaling: {e}")
        return jsonify({'error': str(e)}), 500


@optimization_bp.route('/cost/estimate', methods=['GET'])
def get_cost_estimate():
    """Get current resource cost estimate."""
    try:
        from hermes.optimization.resource_optimizer import cost_optimizer, resource_monitor

        if not cost_optimizer or not resource_monitor:
            return jsonify({'error': 'Cost optimizer not available'}), 503

        hours = request.args.get('hours', 24, type=float)

        # Get current metrics
        current_metrics = asyncio.run(resource_monitor.collect_metrics())

        # Calculate cost
        cost_breakdown = cost_optimizer.calculate_resource_cost(current_metrics, hours)

        return jsonify({
            'cost_breakdown': cost_breakdown,
            'period_hours': hours,
            'timestamp': datetime.utcnow().isoformat()
        }), 200

    except Exception as e:
        logger.error(f"Error getting cost estimate: {e}")
        return jsonify({'error': str(e)}), 500


@optimization_bp.route('/cost/optimizations', methods=['GET'])
def get_cost_optimizations():
    """Get cost optimization suggestions."""
    try:
        from hermes.optimization.resource_optimizer import cost_optimizer, resource_monitor

        if not cost_optimizer or not resource_monitor:
            return jsonify({'error': 'Cost optimizer not available'}), 503

        # Performance requirements from query params
        max_cpu = request.args.get('max_cpu', 80, type=float)
        max_memory = request.args.get('max_memory', 85, type=float)

        performance_requirements = {
            'max_cpu': max_cpu,
            'max_memory': max_memory
        }

        # Get suggestions
        suggestions = cost_optimizer.suggest_cost_optimizations(
            resource_monitor.metrics_history,
            performance_requirements
        )

        return jsonify({
            'suggestions': suggestions,
            'count': len(suggestions),
            'timestamp': datetime.utcnow().isoformat()
        }), 200

    except Exception as e:
        logger.error(f"Error getting cost optimizations: {e}")
        return jsonify({'error': str(e)}), 500


@optimization_bp.route('/performance/recommendations', methods=['GET'])
def get_performance_recommendations():
    """Get performance optimization recommendations."""
    try:
        from hermes.optimization.resource_optimizer import performance_optimizer

        if not performance_optimizer:
            return jsonify({'error': 'Performance optimizer not available'}), 503

        # Get recommendations
        recommendations = asyncio.run(performance_optimizer.analyze_and_optimize())

        return jsonify({
            'recommendations': recommendations,
            'count': len(recommendations),
            'timestamp': datetime.utcnow().isoformat()
        }), 200

    except Exception as e:
        logger.error(f"Error getting performance recommendations: {e}")
        return jsonify({'error': str(e)}), 500


@optimization_bp.route('/load-test/results', methods=['GET'])
def get_load_test_results():
    """Get recent load test results."""
    try:
        from hermes.testing.advanced_load_testing import progressive_tester

        if not progressive_tester:
            return jsonify({'error': 'Load tester not available'}), 503

        limit = request.args.get('limit', 5, type=int)
        results = progressive_tester.test_results[-limit:]

        return jsonify({
            'results': [
                {
                    'scenario': r.scenario_name,
                    'duration': r.test_duration,
                    'total_requests': r.total_requests,
                    'successful_requests': r.successful_requests,
                    'failed_requests': r.failed_requests,
                    'rps': r.requests_per_second,
                    'avg_response_time': r.average_response_time,
                    'p95_response_time': r.p95_response_time,
                    'p99_response_time': r.p99_response_time,
                    'concurrent_users': r.concurrent_users,
                    'error_rate': (r.failed_requests / r.total_requests * 100) if r.total_requests > 0 else 0
                }
                for r in results
            ],
            'count': len(results)
        }), 200

    except Exception as e:
        logger.error(f"Error getting load test results: {e}")
        return jsonify({'error': str(e)}), 500


@optimization_bp.route('/health', methods=['GET'])
def optimization_health():
    """Health check for optimization systems."""
    try:
        from hermes.monitoring.performance_monitor import performance_collector
        from hermes.optimization.resource_optimizer import resource_monitor
        from hermes.caching.advanced_cache import multi_tier_cache

        health_status = {
            'timestamp': datetime.utcnow().isoformat(),
            'components': {
                'performance_monitoring': 'active' if performance_collector and performance_collector.is_collecting else 'inactive',
                'resource_monitoring': 'active' if resource_monitor and resource_monitor.is_collecting else 'inactive',
                'cache_system': 'available' if multi_tier_cache else 'unavailable',
                'auto_scaling': 'available' if 'auto_scaler' in globals() else 'unavailable'
            },
            'status': 'healthy'
        }

        # Check if any critical components are down
        if health_status['components']['performance_monitoring'] == 'inactive':
            health_status['status'] = 'degraded'

        return jsonify(health_status), 200 if health_status['status'] == 'healthy' else 503

    except Exception as e:
        logger.error(f"Error in optimization health check: {e}")
        return jsonify({
            'status': 'unhealthy',
            'error': str(e),
            'timestamp': datetime.utcnow().isoformat()
        }), 503


# Error handlers
@optimization_bp.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Endpoint not found'}), 404


@optimization_bp.errorhandler(500)
def internal_error(error):
    logger.error(f"Internal error: {error}")
    return jsonify({'error': 'Internal server error'}), 500
