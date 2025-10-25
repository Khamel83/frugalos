"""
Autonomous Optimization System
Self-optimizing system that continuously improves performance and efficiency
"""

import logging
import time
import threading
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from collections import defaultdict
import statistics

from ..config import Config
from ..database import Database
from ..logger import get_logger

logger = get_logger('autonomous_dev.auto_optimizer')

class OptimizationStrategy(Enum):
    """Optimization strategies"""
    PERFORMANCE = "performance"
    COST = "cost"
    QUALITY = "quality"
    EFFICIENCY = "efficiency"
    RELIABILITY = "reliability"
    RESOURCE_USAGE = "resource_usage"

class OptimizationImpact(Enum):
    """Optimization impact levels"""
    MINOR = "minor"
    MODERATE = "moderate"
    SIGNIFICANT = "significant"
    CRITICAL = "critical"

@dataclass
class OptimizationTarget:
    """An optimization target"""
    target_id: str
    name: str
    strategy: OptimizationStrategy
    component: str
    current_value: float
    target_value: float
    unit: str
    improvement_pct: float
    impact: OptimizationImpact
    confidence: float
    created_at: datetime

@dataclass
class OptimizationAction:
    """An optimization action"""
    action_id: str
    target_id: str
    action_type: str
    description: str
    implementation: Dict[str, Any]
    expected_improvement: float
    risk_level: str
    rollback_plan: Dict[str, Any]
    applied_at: Optional[datetime]
    success: Optional[bool]
    result_metrics: Dict[str, float]

class AutoOptimizer:
    """Autonomous optimization system"""

    def __init__(self, config: Optional[Config] = None):
        self.config = config or Config()
        self.db = Database()
        self.logger = get_logger('auto_optimizer')

        # Configuration
        self.enabled = self.config.get('autonomous_dev.optimizer.enabled', True)
        self.optimization_interval = self.config.get('autonomous_dev.optimizer.interval', 3600)  # 1 hour
        self.confidence_threshold = self.config.get('autonomous_dev.optimizer.confidence_threshold', 0.7)
        self.auto_apply_safe = self.config.get('autonomous_dev.optimizer.auto_apply_safe', True)

        # Optimization state
        self._targets = {}  # target_id -> OptimizationTarget
        self._actions = {}  # action_id -> OptimizationAction
        self._performance_history = defaultdict(list)
        self._optimization_history = []
        self._active_optimizations = set()

        # Monitoring thread
        self._monitoring_thread = None
        self._running = False

        # Initialize optimization targets
        self._initialize_optimization_targets()

    def _initialize_optimization_targets(self):
        """Initialize default optimization targets"""
        # Performance targets
        self.add_optimization_target(OptimizationTarget(
            target_id="avg_response_time",
            name="Average Response Time",
            strategy=OptimizationStrategy.PERFORMANCE,
            component="system",
            current_value=0.0,
            target_value=5000.0,  # 5 seconds
            unit="ms",
            improvement_pct=0.2,
            impact=OptimizationImpact.SIGNIFICANT,
            confidence=0.8,
            created_at=datetime.now()
        ))

        # Cost targets
        self.add_optimization_target(OptimizationTarget(
            target_id="daily_cost",
            name="Daily Cost",
            strategy=OptimizationStrategy.COST,
            component="system",
            current_value=0.0,
            target_value=50.0,  # $0.50
            unit="dollars",
            improvement_pct=0.15,
            impact=OptimizationImpact.MODERATE,
            confidence=0.7,
            created_at=datetime.now()
        ))

        # Quality targets
        self.add_optimization_target(OptimizationTarget(
            target_id="success_rate",
            name="Success Rate",
            strategy=OptimizationStrategy.QUALITY,
            component="system",
            current_value=0.0,
            target_value=0.95,  # 95%
            unit="percentage",
            improvement_pct=0.05,
            impact=OptimizationImpact.SIGNIFICANT,
            confidence=0.9,
            created_at=datetime.now()
        ))

        # Efficiency targets
        self.add_optimization_target(OptimizationTarget(
            target_id="cache_hit_rate",
            name="Cache Hit Rate",
            strategy=OptimizationStrategy.EFFICIENCY,
            component="cache",
            current_value=0.0,
            target_value=0.8,  # 80%
            unit="percentage",
            improvement_pct=0.1,
            impact=OptimizationImpact.MODERATE,
            confidence=0.6,
            created_at=datetime.now()
        ))

    def start_optimization(self):
        """Start autonomous optimization"""
        if not self.enabled:
            self.logger.info("Autonomous optimizer is disabled")
            return

        if self._running:
            self.logger.warning("Autonomous optimizer already running")
            return

        self._running = True
        self._monitoring_thread = threading.Thread(target=self._optimization_loop, daemon=True)
        self._monitoring_thread.start()
        self.logger.info("Autonomous optimization started")

    def stop_optimization(self):
        """Stop autonomous optimization"""
        self._running = False
        if self._monitoring_thread:
            self._monitoring_thread.join(timeout=10)
        self.logger.info("Autonomous optimization stopped")

    def _optimization_loop(self):
        """Main optimization loop"""
        while self._running:
            try:
                # Collect current metrics
                self._collect_current_metrics()

                # Analyze performance trends
                self._analyze_performance_trends()

                # Identify optimization opportunities
                opportunities = self._identify_optimization_opportunities()

                # Apply safe optimizations automatically
                self._apply_safe_optimizations(opportunities)

                # Update targets
                self._update_targets()

                time.sleep(self.optimization_interval)

            except Exception as e:
                self.logger.error(f"Error in optimization loop: {e}")
                time.sleep(300)  # Wait 5 minutes on error

    def _collect_current_metrics(self):
        """Collect current system metrics"""
        timestamp = datetime.now()

        # Collect response time metrics
        try:
            with self.db.get_connection() as conn:
                cursor = conn.execute("""
                    SELECT AVG(execution_time_ms) as avg_time
                    FROM jobs
                    WHERE created_at >= datetime('now', '-1 hour')
                    AND status = 'completed'
                """)
                row = cursor.fetchone()
                if row and row['avg_time']:
                    self._performance_history['avg_response_time'].append({
                        'timestamp': timestamp,
                        'value': row['avg_time']
                    })
        except Exception as e:
            self.logger.error(f"Error collecting response time metrics: {e}")

        # Collect cost metrics
        try:
            with self.db.get_connection() as conn:
                cursor = conn.execute("""
                    SELECT SUM(cost_cents) as total_cost
                    FROM jobs
                    WHERE created_at >= datetime('now', '-24 hours')
                """)
                row = cursor.fetchone()
                if row and row['total_cost']:
                    self._performance_history['daily_cost'].append({
                        'timestamp': timestamp,
                        'value': row['total_cost'] / 100  # Convert to dollars
                    })
        except Exception as e:
            self.logger.error(f"Error collecting cost metrics: {e}")

        # Collect success rate metrics
        try:
            with self.db.get_connection() as conn:
                cursor = conn.execute("""
                    SELECT
                        COUNT(*) as total,
                        SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed
                    FROM jobs
                    WHERE created_at >= datetime('now', '-1 hour')
                """)
                row = cursor.fetchone()
                if row and row['total'] > 0:
                    success_rate = row['completed'] / row['total']
                    self._performance_history['success_rate'].append({
                        'timestamp': timestamp,
                        'value': success_rate
                    })
        except Exception as e:
            self.logger.error(f"Error collecting success rate metrics: {e}")

        # Collect cache metrics
        try:
            from ..cache.cache_manager import CacheManager
            cache = CacheManager(self.config)
            stats = cache.get_stats()

            self._performance_history['cache_hit_rate'].append({
                'timestamp': timestamp,
                'value': stats.hit_rate
            })
        except Exception as e:
            self.logger.error(f"Error collecting cache metrics: {e}")

        # Limit history size
        for metric in self._performance_history:
            if len(self._performance_history[metric]) > 1000:
                self._performance_history[metric] = self._performance_history[metric][-500:]

    def _analyze_performance_trends(self):
        """Analyze performance trends"""
        for metric_name, history in self._performance_history.items():
            if len(history) < 10:
                continue

            # Calculate trend over last hour
            recent_values = [entry['value'] for entry in history[-10:]]

            # Simple linear regression for trend
            n = len(recent_values)
            x = list(range(n))
            y = recent_values

            if n > 1:
                # Calculate slope
                x_mean = sum(x) / n
                y_mean = sum(y) / n
                numerator = sum((x[i] - x_mean) * (y[i] - y_mean) for i in range(n))
                denominator = sum((x[i] - x_mean) ** 2 for i in range(n))

                if denominator != 0:
                    slope = numerator / denominator
                    trend_direction = "improving" if slope < 0 else "degrading"

                    # Update corresponding target
                    if metric_name == "avg_response_time":
                        target_id = "avg_response_time"
                    elif metric_name == "daily_cost":
                        target_id = "daily_cost"
                    elif metric_name == "success_rate":
                        target_id = "success_rate"
                    elif metric_name == "cache_hit_rate":
                        target_id = "cache_hit_rate"
                    else:
                        continue

                    if target_id in self._targets:
                        target = self._targets[target_id]
                        target.current_value = recent_values[-1]

                        # Update confidence based on trend consistency
                        if abs(slope) > 0.1:  # Significant trend
                            target.confidence = min(1.0, target.confidence + 0.1)
                        elif abs(slope) < 0.01:  # Stable
                            target.confidence = max(0.5, target.confidence - 0.05)

    def _identify_optimization_opportunities(self) -> List[Dict[str, Any]]:
        """Identify optimization opportunities"""
        opportunities = []

        for target_id, target in self._targets.items():
            # Check if target needs optimization
            if self._needs_optimization(target):
                opportunity = {
                    'target_id': target_id,
                    'target': target,
                    'current_value': target.current_value,
                    'target_value': target.target_value,
                    'gap': abs(target.target_value - target.current_value),
                    'gap_percentage': abs((target.target_value - target.current_value) / target.target_value),
                    'confidence': target.confidence
                }

                opportunities.append(opportunity)

        # Sort by gap and confidence
        opportunities.sort(
            key=lambda x: (x['gap_percentage'], x['confidence']),
            reverse=True
        )

        return opportunities

    def _needs_optimization(self, target: OptimizationTarget) -> bool:
        """Check if target needs optimization"""
        if target.strategy == OptimizationStrategy.PERFORMANCE:
            return target.current_value > target.target_value
        elif target.strategy == OptimizationStrategy.COST:
            return target.current_value > target.target_value
        elif target.strategy == OptimizationStrategy.QUALITY:
            return target.current_value < target.target_value
        elif target.strategy == OptimizationStrategy.EFFICIENCY:
            return target.current_value < target.target_value
        else:
            return False

    def _apply_safe_optimizations(self, opportunities: List[Dict[str, Any]]):
        """Apply safe optimizations automatically"""
        for opportunity in opportunities[:3]:  # Top 3 opportunities
            target = opportunity['target']

            # Only apply safe optimizations automatically
            if (target.confidence >= self.confidence_threshold and
                target.impact in [OptimizationImpact.MINOR, OptimizationImpact.MODERATE] and
                self.auto_apply_safe):

                actions = self._generate_optimization_actions(opportunity)

                for action in actions:
                    if action['risk_level'] == 'low':
                        self._apply_optimization_action(action)

    def _generate_optimization_actions(self, opportunity: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate optimization actions for an opportunity"""
        target = opportunity['target']
        actions = []

        if target.strategy == OptimizationStrategy.PERFORMANCE:
            actions.extend(self._generate_performance_actions(opportunity))
        elif target.strategy == OptimizationStrategy.COST:
            actions.extend(self._generate_cost_actions(opportunity))
        elif target.strategy == OptimizationStrategy.EFFICIENCY:
            actions.extend(self._generate_efficiency_actions(opportunity))
        elif target.strategy == OptimizationStrategy.QUALITY:
            actions.extend(self._generate_quality_actions(opportunity))

        return actions

    def _generate_performance_actions(self, opportunity: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate performance optimization actions"""
        actions = []

        target = opportunity['target']
        current_value = target.current_value

        # Suggest cache optimization
        if current_value > 10000:  # > 10 seconds
            actions.append({
                'action_type': 'cache_optimization',
                'description': 'Optimize cache configuration to improve response time',
                'implementation': {
                    'action': 'increase_cache_size',
                    'params': {'max_memory_items': 2000, 'max_memory_size_mb': 200}
                },
                'expected_improvement': 0.2,
                'risk_level': 'low',
                'rollback_plan': {
                    'action': 'restore_cache_config',
                    'original_config': 'current'
                }
            })

        # Suggest backend optimization
        if current_value > 15000:  # > 15 seconds
            actions.append({
                'action_type': 'backend_optimization',
                'description': 'Switch to faster backends for performance-critical tasks',
                'implementation': {
                    'action': 'update_backend_priority',
                    'params': {'prioritize_speed': True}
                },
                'expected_improvement': 0.3,
                'risk_level': 'low',
                'rollback_plan': {
                    'action': 'restore_backend_config',
                    'original_config': 'current'
                }
            })

        return actions

    def _generate_cost_actions(self, opportunity: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate cost optimization actions"""
        actions = []

        target = opportunity['target']
        current_cost = target.current_value

        # Suggest cost threshold optimization
        if current_cost > target.target_value * 1.5:
            actions.append({
                'action_type': 'cost_threshold_optimization',
                'description': 'Implement stricter cost thresholds to prevent overruns',
                'implementation': {
                    'action': 'update_cost_policy',
                    'params': {'max_cost_per_job': target.target_value * 0.1}
                },
                'expected_improvement': 0.25,
                'risk_level': 'low',
                'rollback_plan': {
                    'action': 'restore_cost_policy',
                    'original_policy': 'current'
                }
            })

        # Suggest backend switching
        actions.append({
            'action_type': 'backend_cost_optimization',
            'description': 'Prefer free local backends to reduce costs',
            'implementation': {
                'action': 'update_backend_preferences',
                'params': {'prefer_local': True, 'max_cost_cents': 10}
            },
            'expected_improvement': 0.15,
            'risk_level': 'low',
            'rollback_plan': {
                'action': 'restore_backend_preferences',
                'original_preferences': 'current'
            }
        })

        return actions

    def _generate_efficiency_actions(self, opportunity: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate efficiency optimization actions"""
        actions = []

        target = opportunity['target']
        current_value = target.current_value

        # Suggest cache tuning
        if current_value < 0.7:  # < 70% hit rate
            actions.append({
                'action_type': 'cache_tuning',
                'description': 'Tune cache configuration for better hit rates',
                'implementation': {
                    'action': 'optimize_cache_settings',
                    'params': {'default_ttl_seconds': 7200, 'cleanup_interval': 600}
                },
                'expected_improvement': 0.15,
                'risk_level': 'low',
                'rollback_plan': {
                    'action': 'restore_cache_settings',
                    'original_settings': 'current'
                }
            })

        return actions

    def _generate_quality_actions(self, opportunity: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate quality improvement actions"""
        actions = []

        target = opportunity['target']
        current_value = target.current_value

        # Suggest validation optimization
        if current_value < 0.9:  # < 90% success rate
            actions.append({
                'action_type': 'validation_optimization',
                'description': 'Improve validation and error handling',
                'implementation': {
                    'action': 'update_validation_policy',
                    'params': {'validation_level': 'strict', 'retry_attempts': 3}
                },
                'expected_improvement': 0.1,
                'risk_level': 'low',
                'rollback_plan': {
                    'action': 'restore_validation_policy',
                    'original_policy': 'current'
                }
            })

        return actions

    def _apply_optimization_action(self, action: Dict[str, Any]) -> bool:
        """Apply an optimization action"""
        action_id = self._generate_action_id()

        try:
            # Create optimization action record
            opt_action = OptimizationAction(
                action_id=action_id,
                target_id=action.get('target_id', 'unknown'),
                action_type=action['action_type'],
                description=action['description'],
                implementation=action['implementation'],
                expected_improvement=action['expected_improvement'],
                risk_level=action['risk_level'],
                rollback_plan=action['rollback_plan'],
                applied_at=datetime.now(),
                success=None,
                result_metrics={}
            )

            self._actions[action_id] = opt_action

            # Apply the action based on type
            success = False
            if action['action_type'] == 'cache_optimization':
                success = self._apply_cache_optimization(action['implementation'])
            elif action['action_type'] == 'backend_optimization':
                success = self._apply_backend_optimization(action['implementation'])
            elif action['action_type'] == 'cost_threshold_optimization':
                success = self._apply_cost_threshold_optimization(action['implementation'])
            elif action['action_type'] == 'cache_tuning':
                success = self._apply_cache_tuning(action['implementation'])

            # Update action result
            opt_action.success = success

            if success:
                self._active_optimizations.add(action_id)
                self.logger.info(f"Applied optimization action {action_id}: {action['description']}")
            else:
                self.logger.warning(f"Failed to apply optimization action {action_id}")

            # Store optimization event
            self._store_optimization_event(opt_action)

            return success

        except Exception as e:
            self.logger.error(f"Error applying optimization action: {e}")
            return False

    def _apply_cache_optimization(self, implementation: Dict[str, Any]) -> bool:
        """Apply cache optimization"""
        try:
            # Update cache configuration
            if hasattr(self.config, '_config'):
                if 'cache' not in self.config._config:
                    self.config._config['cache'] = {}

                for key, value in implementation['params'].items():
                    self.config._config['cache'][key] = value

            return True
        except Exception as e:
            self.logger.error(f"Error applying cache optimization: {e}")
            return False

    def _apply_backend_optimization(self, implementation: Dict[str, Any]) -> bool:
        """Apply backend optimization"""
        try:
            # Update backend preferences
            if hasattr(self.config, '_config'):
                if 'backends' not in self.config._config:
                    self.config._config['backends'] = {}

                for key, value in implementation['params'].items():
                    self.config._config['backends'][key] = value

            return True
        except Exception as e:
            self.logger.error(f"Error applying backend optimization: {e}")
            return False

    def _apply_cost_threshold_optimization(self, implementation: Dict[str, Any]) -> bool:
        """Apply cost threshold optimization"""
        try:
            # Update cost policy
            if hasattr(self.config, '_config'):
                self.config._config['backends']['daily_budget_cents'] = implementation['params']['max_cost_per_job'] * 100

            return True
        except Exception as e:
            self.logger.error(f"Error applying cost threshold optimization: {e}")
            return False

    def _apply_cache_tuning(self, implementation: Dict[str, Any]) -> bool:
        """Apply cache tuning"""
        try:
            # Update cache configuration
            if hasattr(self.config, '_config'):
                if 'cache' not in self.config._config:
                    self.config._config['cache'] = {}

                for key, value in implementation['params'].items():
                    self.config._config['cache'][key] = value

            return True
        except Exception as e:
            self.logger.error(f"Error applying cache tuning: {e}")
            return False

    def _update_targets(self):
        """Update optimization targets with current values"""
        for target_id, target in self._targets.items():
            # Get current value from performance history
            if target_id == "avg_response_time" and "avg_response_time" in self._performance_history:
                if self._performance_history["avg_response_time"]:
                    target.current_value = self._performance_history["avg_response_time"][-1]['value']
            elif target_id == "daily_cost" and "daily_cost" in self._performance_history:
                if self._performance_history["daily_cost"]:
                    target.current_value = self._performance_history["daily_cost"][-1]['value']
            elif target_id == "success_rate" and "success_rate" in self._performance_history:
                if self._performance_history["success_rate"]:
                    target.current_value = self._performance_history["success_rate"][-1]['value']
            elif target_id == "cache_hit_rate" and "cache_hit_rate" in self._performance_history:
                if self._performance_history["cache_hit_rate"]:
                    target.current_value = self._performance_history["cache_hit_rate"][-1]['value']

    def add_optimization_target(self, target: OptimizationTarget):
        """Add a new optimization target"""
        self._targets[target.target_id] = target
        self.logger.info(f"Added optimization target: {target.name}")

    def get_optimization_stats(self) -> Dict[str, Any]:
        """Get optimization statistics"""
        total_actions = len(self._actions)
        successful_actions = sum(1 for action in self._actions.values() if action.success)

        return {
            'total_targets': len(self._targets),
            'total_actions': total_actions,
            'successful_actions': successful_actions,
            'success_rate': successful_actions / total_actions if total_actions > 0 else 0,
            'active_optimizations': len(self._active_optimizations),
            'targets_status': {
                target_id: {
                    'name': target.name,
                    'current_value': target.current_value,
                    'target_value': target.target_value,
                    'gap_percentage': abs((target.target_value - target.current_value) / target.target_value) if target.target_value != 0 else 0,
                    'confidence': target.confidence
                }
                for target_id, target in self._targets.items()
            }
        }

    def _store_optimization_event(self, action: OptimizationAction):
        """Store optimization event in database"""
        try:
            with self.db.get_connection() as conn:
                conn.execute("""
                    INSERT INTO optimization_events (
                        action_id, target_id, action_type, description, implementation,
                        expected_improvement, risk_level, applied_at, success
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    action.action_id,
                    action.target_id,
                    action.action_type,
                    action.description,
                    str(action.implementation),
                    action.expected_improvement,
                    action.risk_level,
                    action.applied_at.isoformat() if action.applied_at else None,
                    int(action.success) if action.success is not None else None
                ))
                conn.commit()

        except Exception as e:
            self.logger.error(f"Error storing optimization event: {e}")

    def _generate_action_id(self) -> str:
        """Generate unique action ID"""
        return f"opt_action_{int(time.time() * 1000)}_{hash(time.time()) % 10000}"