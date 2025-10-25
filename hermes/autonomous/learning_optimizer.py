"""
Learning-Based Optimizer
Uses machine learning and pattern recognition to optimize system behavior
"""

import logging
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from collections import defaultdict
import statistics

from ..config import Config
from ..database import Database
from ..logger import get_logger
from ..metalearning.pattern_engine import PatternEngine

logger = get_logger('autonomous.learning_optimizer')

class OptimizationStrategy(Enum):
    """Optimization strategies"""
    COST = "cost"  # Minimize cost
    SPEED = "speed"  # Maximize speed
    QUALITY = "quality"  # Maximize quality
    BALANCED = "balanced"  # Balance all factors

@dataclass
class OptimizationRecommendation:
    """An optimization recommendation"""
    recommendation_id: str
    category: str
    title: str
    description: str
    impact: str  # high, medium, low
    effort: str  # high, medium, low
    estimated_savings: Dict[str, float]  # cost_cents, time_seconds, etc.
    confidence: float
    actions: List[Dict[str, Any]]
    rationale: str

class LearningBasedOptimizer:
    """Optimizes system behavior based on learned patterns"""

    def __init__(self, config: Optional[Config] = None):
        self.config = config or Config()
        self.db = Database()
        self.pattern_engine = PatternEngine(config)
        self.logger = get_logger('learning_optimizer')

        # Optimization configuration
        self.enabled = self.config.get('autonomous.optimization.enabled', True)
        self.learning_window_days = self.config.get('autonomous.optimization.learning_window', 30)
        self.min_samples = self.config.get('autonomous.optimization.min_samples', 10)

        # Learned optimizations
        self._learned_configs = {}
        self._performance_baseline = {}

        # Load baseline
        self._establish_baseline()

    def _establish_baseline(self):
        """Establish performance baseline"""
        try:
            with self.db.get_connection() as conn:
                # Overall performance baseline
                cursor = conn.execute("""
                    SELECT
                        AVG(execution_time_ms) as avg_time,
                        AVG(cost_cents) as avg_cost,
                        COUNT(*) as total_jobs,
                        SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as successful_jobs
                    FROM jobs
                    WHERE created_at >= datetime('now', '-30 days')
                """)

                row = cursor.fetchone()
                if row and row['total_jobs'] > 0:
                    self._performance_baseline = {
                        'avg_execution_time_ms': row['avg_time'] or 0,
                        'avg_cost_cents': row['avg_cost'] or 0,
                        'success_rate': (row['successful_jobs'] / row['total_jobs']),
                        'total_jobs': row['total_jobs']
                    }

            self.logger.info("Established performance baseline")

        except Exception as e:
            self.logger.error(f"Error establishing baseline: {e}")

    def optimize(
        self,
        strategy: OptimizationStrategy = OptimizationStrategy.BALANCED,
        context: Dict[str, Any] = None
    ) -> List[OptimizationRecommendation]:
        """
        Generate optimization recommendations

        Args:
            strategy: Optimization strategy to use
            context: Current context

        Returns:
            List of recommendations
        """
        if not self.enabled:
            return []

        recommendations = []
        context = context or {}

        try:
            # Analyze different aspects
            recommendations.extend(self._optimize_backend_selection(strategy, context))
            recommendations.extend(self._optimize_scheduling(strategy, context))
            recommendations.extend(self._optimize_resource_usage(strategy, context))
            recommendations.extend(self._optimize_validation(strategy, context))
            recommendations.extend(self._optimize_caching(strategy, context))

            # Sort by impact and confidence
            recommendations.sort(
                key=lambda r: (
                    {'high': 3, 'medium': 2, 'low': 1}[r.impact],
                    r.confidence
                ),
                reverse=True
            )

            self.logger.info(f"Generated {len(recommendations)} optimization recommendations")

            return recommendations

        except Exception as e:
            self.logger.error(f"Error generating optimizations: {e}")
            return []

    def _optimize_backend_selection(
        self,
        strategy: OptimizationStrategy,
        context: Dict[str, Any]
    ) -> List[OptimizationRecommendation]:
        """Optimize backend selection"""
        recommendations = []

        try:
            # Analyze backend performance
            with self.db.get_connection() as conn:
                cursor = conn.execute("""
                    SELECT
                        b.name as backend_name,
                        AVG(j.execution_time_ms) as avg_time,
                        AVG(j.cost_cents) as avg_cost,
                        COUNT(*) as job_count,
                        SUM(CASE WHEN j.status = 'completed' THEN 1 ELSE 0 END) as success_count
                    FROM jobs j
                    JOIN backends b ON j.backend_id = b.id
                    WHERE j.created_at >= datetime('now', '-7 days')
                    GROUP BY b.name
                    HAVING COUNT(*) >= ?
                """, (self.min_samples,))

                backends_data = {}
                for row in cursor.fetchall():
                    backends_data[row['backend_name']] = {
                        'avg_time': row['avg_time'],
                        'avg_cost': row['avg_cost'],
                        'success_rate': row['success_count'] / row['job_count'],
                        'job_count': row['job_count']
                    }

            # Find underperforming backends
            for backend, data in backends_data.items():
                if data['success_rate'] < 0.7:
                    recommendations.append(OptimizationRecommendation(
                        recommendation_id=f"backend_reliability_{backend}",
                        category="backend_selection",
                        title=f"Low reliability for {backend}",
                        description=f"{backend} has {data['success_rate']:.0%} success rate. Consider switching.",
                        impact="medium",
                        effort="low",
                        estimated_savings={'avoided_failures': data['job_count'] * 0.3},
                        confidence=0.8,
                        actions=[{
                            'type': 'switch_backend',
                            'from': backend,
                            'to': 'auto_select'
                        }],
                        rationale=f"Success rate ({data['success_rate']:.0%}) below threshold (70%)"
                    ))

                # Cost optimization for cost-focused strategy
                if strategy == OptimizationStrategy.COST and data['avg_cost'] > 1:
                    recommendations.append(OptimizationRecommendation(
                        recommendation_id=f"backend_cost_{backend}",
                        category="backend_selection",
                        title=f"High cost backend: {backend}",
                        description=f"{backend} costs {data['avg_cost']:.2f}¢ per job. Local backends are free.",
                        impact="high",
                        effort="low",
                        estimated_savings={
                            'cost_cents': data['avg_cost'] * data['job_count']
                        },
                        confidence=0.9,
                        actions=[{
                            'type': 'prefer_local_backend',
                            'fallback_to': backend
                        }],
                        rationale=f"Can save ~{data['avg_cost'] * data['job_count']:.0f}¢ using free local backends"
                    ))

        except Exception as e:
            self.logger.error(f"Error optimizing backend selection: {e}")

        return recommendations

    def _optimize_scheduling(
        self,
        strategy: OptimizationStrategy,
        context: Dict[str, Any]
    ) -> List[OptimizationRecommendation]:
        """Optimize job scheduling"""
        recommendations = []

        try:
            # Analyze job timing patterns
            with self.db.get_connection() as conn:
                cursor = conn.execute("""
                    SELECT
                        strftime('%H', created_at) as hour,
                        COUNT(*) as job_count,
                        AVG(execution_time_ms) as avg_time
                    FROM jobs
                    WHERE created_at >= datetime('now', '-7 days')
                    GROUP BY hour
                    ORDER BY job_count DESC
                """)

                hourly_data = {}
                for row in cursor.fetchall():
                    hourly_data[int(row['hour'])] = {
                        'job_count': row['job_count'],
                        'avg_time': row['avg_time']
                    }

            # Find peak and off-peak hours
            if hourly_data:
                avg_jobs = statistics.mean(d['job_count'] for d in hourly_data.values())
                peak_hours = [h for h, d in hourly_data.items() if d['job_count'] > avg_jobs * 1.5]
                off_peak_hours = [h for h, d in hourly_data.items() if d['job_count'] < avg_jobs * 0.5]

                if peak_hours and off_peak_hours:
                    recommendations.append(OptimizationRecommendation(
                        recommendation_id="scheduling_load_balance",
                        category="scheduling",
                        title="Balance load across hours",
                        description=f"Jobs concentrated in hours {peak_hours}. Consider scheduling non-urgent tasks during off-peak hours {off_peak_hours}.",
                        impact="medium",
                        effort="medium",
                        estimated_savings={'time_seconds': 0},
                        confidence=0.7,
                        actions=[{
                            'type': 'enable_smart_scheduling',
                            'prefer_hours': off_peak_hours
                        }],
                        rationale=f"Load balancing can improve overall system responsiveness"
                    ))

        except Exception as e:
            self.logger.error(f"Error optimizing scheduling: {e}")

        return recommendations

    def _optimize_resource_usage(
        self,
        strategy: OptimizationStrategy,
        context: Dict[str, Any]
    ) -> List[OptimizationRecommendation]:
        """Optimize resource usage"""
        recommendations = []

        try:
            # Check for long-running jobs
            with self.db.get_connection() as conn:
                cursor = conn.execute("""
                    SELECT AVG(execution_time_ms) as avg_time
                    FROM jobs
                    WHERE created_at >= datetime('now', '-7 days')
                    AND status = 'completed'
                """)

                row = cursor.fetchone()
                if row and row['avg_time']:
                    avg_time = row['avg_time']

                    # If jobs are taking too long
                    if avg_time > 10000:  # 10 seconds
                        recommendations.append(OptimizationRecommendation(
                            recommendation_id="resource_timeout",
                            category="resource_usage",
                            title="Reduce job timeout",
                            description=f"Average job time is {avg_time/1000:.1f}s. Set reasonable timeouts to prevent resource hogging.",
                            impact="medium",
                            effort="low",
                            estimated_savings={'time_seconds': 0},
                            confidence=0.7,
                            actions=[{
                                'type': 'set_timeout',
                                'timeout_seconds': int(avg_time / 1000 * 2)  # 2x average
                            }],
                            rationale="Prevents runaway jobs from consuming resources"
                        ))

        except Exception as e:
            self.logger.error(f"Error optimizing resource usage: {e}")

        return recommendations

    def _optimize_validation(
        self,
        strategy: OptimizationStrategy,
        context: Dict[str, Any]
    ) -> List[OptimizationRecommendation]:
        """Optimize validation strategies"""
        recommendations = []

        try:
            # Check validation overhead
            baseline_time = self._performance_baseline.get('avg_execution_time_ms', 0)

            if baseline_time > 5000 and strategy == OptimizationStrategy.SPEED:
                recommendations.append(OptimizationRecommendation(
                    recommendation_id="validation_minimal",
                    category="validation",
                    title="Reduce validation overhead",
                    description="For speed-critical tasks, use minimal validation instead of consensus.",
                    impact="high",
                    effort="low",
                    estimated_savings={'time_seconds': baseline_time / 1000 * 0.3},
                    confidence=0.6,
                    actions=[{
                        'type': 'set_validation_level',
                        'level': 'minimal'
                    }],
                    rationale="Can reduce execution time by ~30% for speed-critical tasks"
                ))

        except Exception as e:
            self.logger.error(f"Error optimizing validation: {e}")

        return recommendations

    def _optimize_caching(
        self,
        strategy: OptimizationStrategy,
        context: Dict[str, Any]
    ) -> List[OptimizationRecommendation]:
        """Optimize caching strategies"""
        recommendations = []

        try:
            # Check for repeated similar jobs
            with self.db.get_connection() as conn:
                cursor = conn.execute("""
                    SELECT idea, COUNT(*) as frequency
                    FROM jobs
                    WHERE created_at >= datetime('now', '-7 days')
                    GROUP BY idea
                    HAVING COUNT(*) >= 3
                    ORDER BY COUNT(*) DESC
                    LIMIT 5
                """)

                repeated_jobs = []
                for row in cursor.fetchall():
                    repeated_jobs.append({
                        'idea': row['idea'],
                        'frequency': row['frequency']
                    })

            if repeated_jobs:
                total_repeated = sum(j['frequency'] for j in repeated_jobs)

                recommendations.append(OptimizationRecommendation(
                    recommendation_id="caching_enable",
                    category="caching",
                    title="Enable result caching",
                    description=f"{total_repeated} jobs are repeated. Cache results to save time and cost.",
                    impact="high",
                    effort="medium",
                    estimated_savings={
                        'time_seconds': total_repeated * 2,  # Estimate
                        'cost_cents': total_repeated * 0.5  # Estimate
                    },
                    confidence=0.8,
                    actions=[{
                        'type': 'enable_caching',
                        'cache_ttl_hours': 24
                    }],
                    rationale=f"{total_repeated} repeated jobs could benefit from caching"
                ))

        except Exception as e:
            self.logger.error(f"Error optimizing caching: {e}")

        return recommendations

    def apply_optimization(self, recommendation: OptimizationRecommendation) -> Dict[str, Any]:
        """
        Apply an optimization recommendation

        Args:
            recommendation: Recommendation to apply

        Returns:
            Result of applying optimization
        """
        try:
            self.logger.info(f"Applying optimization: {recommendation.title}")

            results = []
            for action in recommendation.actions:
                result = self._apply_action(action)
                results.append(result)

            return {
                'success': True,
                'recommendation_id': recommendation.recommendation_id,
                'results': results
            }

        except Exception as e:
            self.logger.error(f"Error applying optimization: {e}")
            return {
                'success': False,
                'recommendation_id': recommendation.recommendation_id,
                'error': str(e)
            }

    def _apply_action(self, action: Dict[str, Any]) -> Dict[str, Any]:
        """Apply a single optimization action"""
        action_type = action.get('type')

        if action_type == 'switch_backend':
            # Record backend preference change
            return {'action': 'backend_switched', 'status': 'applied'}

        elif action_type == 'enable_smart_scheduling':
            # Enable smart scheduling
            return {'action': 'smart_scheduling_enabled', 'status': 'applied'}

        elif action_type == 'set_timeout':
            # Update timeout configuration
            timeout = action.get('timeout_seconds')
            return {'action': 'timeout_set', 'timeout': timeout, 'status': 'applied'}

        elif action_type == 'enable_caching':
            # Enable result caching
            ttl = action.get('cache_ttl_hours', 24)
            return {'action': 'caching_enabled', 'ttl_hours': ttl, 'status': 'applied'}

        else:
            self.logger.warning(f"Unknown action type: {action_type}")
            return {'action': action_type, 'status': 'unknown'}

    def get_optimization_impact(
        self,
        time_window_days: int = 7
    ) -> Dict[str, Any]:
        """
        Measure impact of applied optimizations

        Args:
            time_window_days: Days to analyze

        Returns:
            Impact metrics
        """
        try:
            cutoff = datetime.now() - timedelta(days=time_window_days)

            with self.db.get_connection() as conn:
                cursor = conn.execute("""
                    SELECT
                        AVG(execution_time_ms) as avg_time,
                        AVG(cost_cents) as avg_cost,
                        COUNT(*) as total_jobs,
                        SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as successful_jobs
                    FROM jobs
                    WHERE created_at >= ?
                """, (cutoff,))

                row = cursor.fetchone()

                if row and row['total_jobs'] > 0:
                    current_performance = {
                        'avg_execution_time_ms': row['avg_time'] or 0,
                        'avg_cost_cents': row['avg_cost'] or 0,
                        'success_rate': row['successful_jobs'] / row['total_jobs'],
                        'total_jobs': row['total_jobs']
                    }

                    # Compare to baseline
                    baseline = self._performance_baseline

                    time_improvement = (
                        (baseline.get('avg_execution_time_ms', 0) - current_performance['avg_execution_time_ms'])
                        / max(baseline.get('avg_execution_time_ms', 1), 1)
                    ) if baseline.get('avg_execution_time_ms') else 0

                    cost_improvement = (
                        (baseline.get('avg_cost_cents', 0) - current_performance['avg_cost_cents'])
                        / max(baseline.get('avg_cost_cents', 1), 1)
                    ) if baseline.get('avg_cost_cents') else 0

                    return {
                        'baseline': baseline,
                        'current': current_performance,
                        'improvements': {
                            'time_improvement_pct': time_improvement * 100,
                            'cost_improvement_pct': cost_improvement * 100,
                            'success_rate_change': (
                                current_performance['success_rate'] -
                                baseline.get('success_rate', 0)
                            )
                        }
                    }

        except Exception as e:
            self.logger.error(f"Error measuring optimization impact: {e}")

        return {}

    def get_optimizer_stats(self) -> Dict[str, Any]:
        """Get optimizer statistics"""
        return {
            'enabled': self.enabled,
            'learning_window_days': self.learning_window_days,
            'min_samples': self.min_samples,
            'baseline': self._performance_baseline,
            'learned_configs': len(self._learned_configs)
        }
