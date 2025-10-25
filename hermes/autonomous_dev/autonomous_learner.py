"""
Autonomous Learning System
Self-learning system that continuously improves from experience
"""

import logging
import numpy as np
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from collections import defaultdict
import json

from ..config import Config
from ..database import Database
from ..logger import get_logger

logger = get_logger('autonomous_dev.autonomous_learner')

class LearningObjective(Enum):
    """Types of learning objectives"""
    PERFORMANCE_OPTIMIZATION = "performance_optimization"
    COST_REDUCTION = "cost_reduction"
    ACCURACY_IMPROVEMENT = "accuracy_improvement"
    EFFICIENCY_GAIN = "efficiency_gain"
    ERROR_REDUCTION = "error_reduction"

@dataclass
class LearningPattern:
    """A learned pattern"""
    pattern_id: str
    objective: LearningObjective
    input_features: Dict[str, Any]
    output_features: Dict[str, Any]
    success_rate: float
    confidence: float
    usage_count: int
    last_used: datetime
    effectiveness_score: float

class AutonomousLearner:
    """Self-learning system that continuously improves"""

    def __init__(self, config: Optional[Config] = None):
        self.config = config or Config()
        self.db = Database()
        self.logger = get_logger('autonomous_learner')

        # Configuration
        self.enabled = self.config.get('autonomous_dev.learner.enabled', True)
        self.learning_rate = self.config.get('autonomous_dev.learner.learning_rate', 0.1)
        self.min_confidence = self.config.get('autonomous_dev.learner.min_confidence', 0.6)
        self.max_patterns = self.config.get('autonomous_dev.learner.max_patterns', 1000)

        # Learning state
        self._patterns = {}  # pattern_id -> LearningPattern
        self._feature_stats = defaultdict(lambda: {'count': 0, 'sum': 0.0, 'sum_sq': 0.0})
        self._experience_buffer = []
        self._learning_history = []

        # Performance tracking
        self._performance_metrics = defaultdict(list)

    def learn_from_experience(
        self,
        experience: Dict[str, Any],
        outcome: Dict[str, Any]
    ) -> bool:
        """
        Learn from a single experience

        Args:
            experience: Input experience with features
            outcome: Result of the experience

        Returns:
            True if learning occurred
        """
        if not self.enabled:
            return False

        try:
            # Extract features
            input_features = self._extract_features(experience)
            output_features = self._extract_features(outcome)

            # Calculate success metrics
            success_metrics = self._calculate_success_metrics(experience, outcome)

            # Update feature statistics
            self._update_feature_stats(input_features, success_metrics)

            # Find or create patterns
            pattern = self._find_or_create_pattern(
                LearningObjective.PERFORMANCE_OPTIMIZATION,
                input_features,
                output_features,
                success_metrics
            )

            # Update pattern
            self._update_pattern(pattern, success_metrics)

            # Add to experience buffer
            self._experience_buffer.append({
                'experience': experience,
                'outcome': outcome,
                'success_metrics': success_metrics,
                'timestamp': datetime.now()
            })

            # Limit buffer size
            if len(self._experience_buffer) > 10000:
                self._experience_buffer = self._experience_buffer[-5000:]

            # Trigger periodic learning
            if len(self._experience_buffer) % 100 == 0:
                self._trigger_periodic_learning()

            self.logger.debug(f"Learned from experience: success_score={success_metrics.get('success_score', 0):.2f}")

            return True

        except Exception as e:
            self.logger.error(f"Error learning from experience: {e}")
            return False

    def get_best_practice(
        self,
        context: Dict[str, Any],
        objective: LearningObjective = LearningObjective.PERFORMANCE_OPTIMIZATION
    ) -> Optional[LearningPattern]:
        """
        Get best practice pattern for given context

        Args:
            context: Current context
            objective: Learning objective

        Returns:
            Best matching pattern or None
        """
        if not self.enabled:
            return None

        try:
            # Find relevant patterns
            relevant_patterns = [
                pattern for pattern in self._patterns.values()
                if pattern.objective == objective and pattern.confidence >= self.min_confidence
            ]

            if not relevant_patterns:
                return None

            # Calculate similarity scores
            context_features = self._extract_features(context)
            scored_patterns = []

            for pattern in relevant_patterns:
                similarity = self._calculate_similarity(
                    context_features,
                    pattern.input_features
                )

                if similarity > 0.5:  # Minimum similarity threshold
                    scored_patterns.append((pattern, similarity))

            # Sort by effectiveness and similarity
            scored_patterns.sort(
                key=lambda x: (x[0].effectiveness_score, x[1]),
                reverse=True
            )

            if scored_patterns:
                best_pattern = scored_patterns[0][0]

                # Update usage
                best_pattern.usage_count += 1
                best_pattern.last_used = datetime.now()

                self.logger.debug(f"Selected best practice pattern: {best_pattern.pattern_id}")

                return best_pattern

            return None

        except Exception as e:
            self.logger.error(f"Error getting best practice: {e}")
            return None

    def learn_optimization_strategies(self) -> List[Dict[str, Any]]:
        """Learn optimization strategies from experience buffer"""
        strategies = []

        if len(self._experience_buffer) < 50:
            return strategies

        try:
            # Group experiences by success level
            successful_experiences = [
                exp for exp in self._experience_buffer
                if exp['success_metrics'].get('success_score', 0) > 0.7
            ]

            failed_experiences = [
                exp for exp in self._experience_buffer
                if exp['success_metrics'].get('success_score', 0) < 0.5
            ]

            # Analyze successful patterns
            if successful_experiences:
                strategy = self._analyze_strategy_pattern(successful_experiences, "successful")
                if strategy:
                    strategies.append(strategy)

            # Analyze failure patterns
            if failed_experiences:
                strategy = self._analyze_strategy_pattern(failed_experiences, "failure")
                if strategy:
                    strategies.append(strategy)

            # Learn parameter optimizations
            param_strategies = self._learn_parameter_optimizations(successful_experiences)
            strategies.extend(param_strategies)

        except Exception as e:
            self.logger.error(f"Error learning optimization strategies: {e}")

        return strategies

    def _extract_features(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract features from data"""
        features = {}

        # Extract numeric features
        for key, value in data.items():
            if isinstance(value, (int, float)):
                features[f"num_{key}"] = float(value)
            elif isinstance(value, str):
                features[f"str_{key}_len"] = len(value)
                features[f"str_{key}_words"] = len(value.split())
            elif isinstance(value, (list, dict)):
                features[f"col_{key}_size"] = len(value)

        # Extract time-based features
        if 'created_at' in data:
            created_at = data['created_at']
            if isinstance(created_at, str):
                created_at = datetime.fromisoformat(created_at)

            features['hour_of_day'] = created_at.hour
            features['day_of_week'] = created_at.weekday()

        # Extract categorical features
        categorical_keys = ['backend_used', 'status', 'task_type']
        for key in categorical_keys:
            if key in data:
                features[f"cat_{key}"] = str(data[key])

        return features

    def _calculate_success_metrics(self, experience: Dict[str, Any], outcome: Dict[str, Any]) -> Dict[str, float]:
        """Calculate success metrics from experience and outcome"""
        metrics = {}

        # Execution success
        metrics['execution_success'] = 1.0 if outcome.get('status') == 'completed' else 0.0

        # Performance metrics
        if 'execution_time_ms' in outcome:
            expected_time = experience.get('expected_time_ms', 10000)
            actual_time = outcome['execution_time_ms']
            metrics['time_performance'] = min(expected_time / actual_time, 1.0)

        # Cost metrics
        if 'cost_cents' in outcome:
            expected_cost = experience.get('expected_cost_cents', 10)
            actual_cost = outcome['cost_cents']
            metrics['cost_performance'] = min(expected_cost / actual_cost, 1.0)

        # Accuracy metrics
        if 'accuracy' in outcome:
            metrics['accuracy'] = outcome['accuracy']

        # Overall success score
        scores = [
            metrics['execution_success'],
            metrics.get('time_performance', 0.5),
            metrics.get('cost_performance', 0.5)
        ]

        if 'accuracy' in metrics:
            scores.append(metrics['accuracy'])

        metrics['success_score'] = sum(scores) / len(scores)

        return metrics

    def _update_feature_stats(self, features: Dict[str, Any], metrics: Dict[str, float]):
        """Update feature statistics for learning"""
        for feature_name, feature_value in features.items():
            if isinstance(feature_value, (int, float)):
                stats = self._feature_stats[feature_name]
                stats['count'] += 1
                stats['sum'] += feature_value
                stats['sum_sq'] += feature_value * feature_value

    def _find_or_create_pattern(
        self,
        objective: LearningObjective,
        input_features: Dict[str, Any],
        output_features: Dict[str, Any],
        success_metrics: Dict[str, float]
    ) -> LearningPattern:
        """Find existing pattern or create new one"""
        # Look for similar existing patterns
        similar_patterns = [
            pattern for pattern in self._patterns.values()
            if (pattern.objective == objective and
                self._calculate_similarity(input_features, pattern.input_features) > 0.8)
        ]

        if similar_patterns:
            # Use most similar pattern
            pattern = max(similar_patterns, key=lambda p: p.confidence)
        else:
            # Create new pattern
            pattern = LearningPattern(
                pattern_id=self._generate_pattern_id(),
                objective=objective,
                input_features=input_features.copy(),
                output_features=output_features.copy(),
                success_rate=success_metrics.get('success_score', 0.0),
                confidence=0.5,
                usage_count=0,
                last_used=datetime.now(),
                effectiveness_score=success_metrics.get('success_score', 0.0)
            )

            self._patterns[pattern.pattern_id] = pattern

        return pattern

    def _update_pattern(self, pattern: LearningPattern, metrics: Dict[str, float]):
        """Update pattern with new experience"""
        success_score = metrics.get('success_score', 0.0)

        # Update success rate (exponential moving average)
        alpha = self.learning_rate
        pattern.success_rate = (
            (1 - alpha) * pattern.success_rate + alpha * success_score
        )

        # Update confidence
        pattern.confidence = min(1.0, pattern.confidence + alpha * 0.1)

        # Update effectiveness score
        pattern.effectiveness_score = (
            (1 - alpha) * pattern.effectiveness_score + alpha * success_score
        )

        # Update output features
        for key, value in metrics.items():
            if key in pattern.output_features:
                pattern.output_features[key] = (
                    (1 - alpha) * pattern.output_features[key] + alpha * value
                )

    def _calculate_similarity(self, features1: Dict[str, Any], features2: Dict[str, Any]) -> float:
        """Calculate similarity between two feature sets"""
        if not features1 or not features2:
            return 0.0

        # Get common features
        common_features = set(features1.keys()) & set(features2.keys())

        if not common_features:
            return 0.0

        # Calculate similarity for each feature
        similarities = []
        for feature in common_features:
            val1 = features1[feature]
            val2 = features2[feature]

            if isinstance(val1, (int, float)) and isinstance(val2, (int, float)):
                # Numeric similarity
                max_val = max(abs(val1), abs(val2), 1.0)
                similarity = 1.0 - (abs(val1 - val2) / max_val)
                similarities.append(similarity)
            elif isinstance(val1, str) and isinstance(val2, str):
                # String similarity
                if val1 == val2:
                    similarities.append(1.0)
                else:
                    similarities.append(0.0)
            else:
                # Categorical similarity
                similarities.append(1.0 if val1 == val2 else 0.0)

        # Return average similarity
        return sum(similarities) / len(similarities)

    def _trigger_periodic_learning(self):
        """Trigger periodic learning and pattern optimization"""
        try:
            # Remove low-confidence patterns
            self._cleanup_low_confidence_patterns()

            # Merge similar patterns
            self._merge_similar_patterns()

            # Update performance metrics
            self._update_performance_metrics()

            self.logger.debug("Periodic learning completed")

        except Exception as e:
            self.logger.error(f"Error in periodic learning: {e}")

    def _cleanup_low_confidence_patterns(self):
        """Remove patterns with low confidence"""
        to_remove = [
            pattern_id for pattern_id, pattern in self._patterns.items()
            if pattern.confidence < self.min_confidence and pattern.usage_count < 5
        ]

        for pattern_id in to_remove:
            del self._patterns[pattern_id]

        if to_remove:
            self.logger.debug(f"Removed {len(to_remove)} low-confidence patterns")

    def _merge_similar_patterns(self):
        """Merge very similar patterns"""
        pattern_list = list(self._patterns.values())
        merged_patterns = set()

        for i, pattern1 in enumerate(pattern_list):
            if pattern1.pattern_id in merged_patterns:
                continue

            for pattern2 in pattern_list[i+1:]:
                if pattern2.pattern_id in merged_patterns:
                    continue

                similarity = self._calculate_similarity(
                    pattern1.input_features,
                    pattern2.input_features
                )

                if similarity > 0.9:  # Very similar
                    # Merge patterns (keep the better one)
                    if pattern1.effectiveness_score >= pattern2.effectiveness_score:
                        del self._patterns[pattern2.pattern_id]
                        merged_patterns.add(pattern2.pattern_id)
                    else:
                        del self._patterns[pattern1.pattern_id]
                        merged_patterns.add(pattern1.pattern_id)
                        break

    def _update_performance_metrics(self):
        """Update performance tracking metrics"""
        if not self._experience_buffer:
            return

        # Calculate recent performance
        recent_experiences = self._experience_buffer[-100:]  # Last 100 experiences
        success_scores = [exp['success_metrics'].get('success_score', 0) for exp in recent_experiences]

        if success_scores:
            avg_success = sum(success_scores) / len(success_scores)
            self._performance_metrics['success_rate'].append(avg_success)

            # Keep only last 1000 data points
            if len(self._performance_metrics['success_rate']) > 1000:
                self._performance_metrics['success_rate'] = self._performance_metrics['success_rate'][-500:]

    def _analyze_strategy_pattern(self, experiences: List[Dict[str, Any]], strategy_type: str) -> Optional[Dict[str, Any]]:
        """Analyze patterns in experiences to extract strategies"""
        if len(experiences) < 10:
            return None

        try:
            # Extract common features
            all_features = []
            for exp in experiences:
                features = self._extract_features(exp['experience'])
                all_features.append(features)

            # Find most common values for categorical features
            categorical_features = {}
            for features in all_features:
                for key, value in features.items():
                    if key.startswith('cat_'):
                        if key not in categorical_features:
                            categorical_features[key] = defaultdict(int)
                        categorical_features[key][value] += 1

            # Find average values for numeric features
            numeric_features = {}
            for features in all_features:
                for key, value in features.items():
                    if key.startswith('num_'):
                        if key not in numeric_features:
                            numeric_features[key] = []
                        numeric_features[key].append(value)

            # Create strategy description
            strategy = {
                'type': strategy_type,
                'pattern_count': len(experiences),
                'success_rate': sum(
                    exp['success_metrics'].get('success_score', 0) for exp in experiences
                ) / len(experiences),
                'categorical_patterns': {
                    key: dict(sorted(values.items(), key=lambda x: x[1], reverse=True)[:3])
                    for key, values in categorical_features.items()
                },
                'numeric_averages': {
                    key: sum(values) / len(values)
                    for key, values in numeric_features.items()
                }
            }

            return strategy

        except Exception as e:
            self.logger.error(f"Error analyzing strategy pattern: {e}")
            return None

    def _learn_parameter_optimizations(self, experiences: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Learn parameter optimizations from successful experiences"""
        optimizations = []

        if len(experiences) < 20:
            return optimizations

        try:
            # Group by backend
            backend_groups = defaultdict(list)
            for exp in experiences:
                backend = exp['outcome'].get('backend_used', 'unknown')
                backend_groups[backend].append(exp)

            # Find optimal parameters for each backend
            for backend, group in backend_groups.items():
                if len(group) < 5:
                    continue

                # Analyze successful vs failed
                successful = [exp for exp in group if exp['success_metrics'].get('success_score', 0) > 0.7]
                failed = [exp for exp in group if exp['success_metrics'].get('success_score', 0) < 0.5]

                if len(successful) > 0:
                    optimization = self._find_parameter_optimizations(backend, successful, failed)
                    if optimization:
                        optimizations.append(optimization)

        except Exception as e:
            self.logger.error(f"Error learning parameter optimizations: {e}")

        return optimizations

    def _find_parameter_optimizations(
        self,
        backend: str,
        successful: List[Dict[str, Any]],
        failed: List[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        """Find parameter optimizations from successful vs failed experiences"""
        try:
            # Compare common features
            success_features = [self._extract_features(exp['experience']) for exp in successful]
            fail_features = [self._extract_features(exp['experience']) for exp in failed]

            # Find differences in numeric features
            numeric_differences = {}
            for feature in set(
                f for features in success_features + fail_features
                for f in features.keys()
                if f.startswith('num_')
            ):
                success_vals = [f.get(feature) for f in success_features if feature in f]
                fail_vals = [f.get(feature) for f in fail_features if feature in f]

                if success_vals and fail_vals:
                    success_avg = sum(success_vals) / len(success_vals)
                    fail_avg = sum(fail_vals) / len(fail_vals)

                    if abs(success_avg - fail_avg) > 0.1:  # Significant difference
                        numeric_differences[feature] = {
                            'successful_avg': success_avg,
                            'failed_avg': fail_avg,
                            'improvement': success_avg - fail_avg
                        }

            if numeric_differences:
                return {
                    'backend': backend,
                    'type': 'parameter_optimization',
                    'differences': numeric_differences,
                    'success_rate': len(successful) / (len(successful) + len(failed)),
                    'sample_size': len(successful) + len(failed)
                }

            return None

        except Exception as e:
            self.logger.error(f"Error finding parameter optimizations: {e}")
            return None

    def _generate_pattern_id(self) -> str:
        """Generate unique pattern ID"""
        import time
        return f"pattern_{int(time.time() * 1000)}_{hash(time.time()) % 10000}"

    def get_learning_stats(self) -> Dict[str, Any]:
        """Get learning statistics"""
        return {
            'total_patterns': len(self._patterns),
            'experience_buffer_size': len(self._experience_buffer),
            'feature_stats_count': len(self._feature_stats),
            'performance_metrics_size': sum(len(metrics) for metrics in self._performance_metrics.values()),
            'patterns_by_objective': {
                obj.value: len([p for p in self._patterns.values() if p.objective == obj])
                for obj in LearningObjective
            },
            'avg_pattern_confidence': (
                sum(p.confidence for p in self._patterns.values()) / len(self._patterns)
                if self._patterns else 0
            )
        }