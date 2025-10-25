"""
Pattern-Based Execution Strategy
Determines optimal execution approach based on learned patterns
"""

import logging
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
from datetime import datetime

from ..config import Config
from ..database import Database
from ..logger import get_logger
from .pattern_engine import PatternEngine

logger = get_logger('metalearning.execution_strategy')

class ExecutionMode(Enum):
    """Execution modes"""
    LOCAL_ONLY = "local_only"
    REMOTE_PREFERRED = "remote_preferred"
    HYBRID = "hybrid"
    CONSENSUS = "consensus"
    FAST_TRACK = "fast_track"

class ValidationLevel(Enum):
    """Validation strictness levels"""
    MINIMAL = "minimal"
    STANDARD = "standard"
    STRICT = "strict"
    CONSENSUS = "consensus"

@dataclass
class ExecutionStrategy:
    """Complete execution strategy with reasoning"""
    mode: ExecutionMode
    validation_level: ValidationLevel
    backend_preference: List[str]
    timeout_seconds: int
    retry_strategy: Dict[str, Any]
    context_optimization: Dict[str, Any]
    confidence_score: float
    reasoning: str
    estimated_cost_cents: float
    estimated_time_seconds: float

class ExecutionStrategyEngine:
    """Determines optimal execution strategy based on patterns"""

    def __init__(self, config: Optional[Config] = None):
        self.config = config or Config()
        self.db = Database()
        self.pattern_engine = PatternEngine(config)
        self.logger = get_logger('execution_strategy')

        # Load historical execution data
        self._execution_history = self._load_execution_history()

    def _load_execution_history(self) -> Dict[str, Any]:
        """Load historical execution data for strategy optimization"""
        history = {
            'total_jobs': 0,
            'successful_jobs': 0,
            'by_mode': {},
            'by_validation': {},
            'avg_cost_cents': 0,
            'avg_time_seconds': 0
        }

        try:
            with self.db.get_connection() as conn:
                # Overall statistics
                cursor = conn.execute("""
                    SELECT
                        COUNT(*) as total,
                        SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as successful,
                        AVG(cost_cents) as avg_cost,
                        AVG(execution_time_ms) as avg_time
                    FROM jobs
                """)
                row = cursor.fetchone()

                if row:
                    history['total_jobs'] = row['total']
                    history['successful_jobs'] = row['successful']
                    history['avg_cost_cents'] = row['avg_cost'] or 0
                    history['avg_time_seconds'] = (row['avg_time'] or 0) / 1000

            self.logger.info(
                f"Loaded execution history: {history['total_jobs']} jobs, "
                f"{history['successful_jobs']} successful"
            )

        except Exception as e:
            self.logger.error(f"Error loading execution history: {e}")

        return history

    def determine_strategy(
        self,
        idea: str,
        context: Dict[str, Any] = None,
        constraints: Dict[str, Any] = None
    ) -> ExecutionStrategy:
        """
        Determine optimal execution strategy

        Args:
            idea: User's idea/task
            context: Additional context
            constraints: Execution constraints (budget, time, etc.)

        Returns:
            Recommended execution strategy
        """
        try:
            # Get matched patterns
            patterns = self.pattern_engine.recognize_patterns(idea, context)

            # Extract constraints
            constraints = constraints or {}
            max_cost = constraints.get('max_cost_cents', float('inf'))
            max_time = constraints.get('max_time_seconds', 300)
            require_local = constraints.get('require_local', False)
            privacy_level = constraints.get('privacy_level', 'P1')

            # Analyze idea characteristics
            characteristics = self._analyze_idea_characteristics(idea)

            # Determine execution mode
            mode = self._determine_mode(
                patterns,
                characteristics,
                require_local,
                privacy_level
            )

            # Determine validation level
            validation_level = self._determine_validation_level(
                patterns,
                characteristics,
                constraints
            )

            # Determine backend preference
            backend_preference = self._determine_backend_preference(
                mode,
                patterns,
                characteristics
            )

            # Determine timeout
            timeout = self._determine_timeout(
                patterns,
                characteristics,
                max_time
            )

            # Determine retry strategy
            retry_strategy = self._determine_retry_strategy(
                patterns,
                characteristics
            )

            # Determine context optimization
            context_optimization = self._determine_context_optimization(
                characteristics
            )

            # Estimate cost and time
            estimated_cost, estimated_time = self._estimate_resources(
                mode,
                validation_level,
                backend_preference,
                characteristics
            )

            # Calculate confidence
            confidence = self._calculate_strategy_confidence(patterns, characteristics)

            # Generate reasoning
            reasoning = self._generate_strategy_reasoning(
                mode,
                validation_level,
                patterns,
                characteristics
            )

            strategy = ExecutionStrategy(
                mode=mode,
                validation_level=validation_level,
                backend_preference=backend_preference,
                timeout_seconds=timeout,
                retry_strategy=retry_strategy,
                context_optimization=context_optimization,
                confidence_score=confidence,
                reasoning=reasoning,
                estimated_cost_cents=estimated_cost,
                estimated_time_seconds=estimated_time
            )

            self.logger.info(
                f"Determined strategy: {mode.value}, {validation_level.value}, "
                f"confidence: {confidence:.2f}"
            )

            return strategy

        except Exception as e:
            self.logger.error(f"Error determining strategy: {e}")
            # Return safe default strategy
            return self._get_default_strategy()

    def _analyze_idea_characteristics(self, idea: str) -> Dict[str, Any]:
        """Analyze characteristics of the idea"""
        idea_lower = idea.lower()

        return {
            'complexity': self._estimate_complexity(idea),
            'is_code_task': any(kw in idea_lower for kw in ['code', 'script', 'program', 'function']),
            'is_data_task': any(kw in idea_lower for kw in ['data', 'analyze', 'process', 'extract']),
            'is_creative_task': any(kw in idea_lower for kw in ['write', 'create', 'generate', 'design']),
            'requires_accuracy': any(kw in idea_lower for kw in ['accurate', 'precise', 'exact', 'correct']),
            'is_time_sensitive': any(kw in idea_lower for kw in ['quick', 'fast', 'urgent', 'asap']),
            'word_count': len(idea.split()),
            'has_examples': 'example' in idea_lower or 'like' in idea_lower
        }

    def _estimate_complexity(self, idea: str) -> str:
        """Estimate task complexity (low, medium, high)"""
        word_count = len(idea.split())
        complexity_keywords = ['complex', 'advanced', 'sophisticated', 'multiple', 'integrate']
        simple_keywords = ['simple', 'basic', 'quick', 'just', 'only']

        has_complexity = any(kw in idea.lower() for kw in complexity_keywords)
        has_simple = any(kw in idea.lower() for kw in simple_keywords)

        if has_simple and not has_complexity:
            return 'low'
        elif has_complexity or word_count > 50:
            return 'high'
        else:
            return 'medium'

    def _determine_mode(
        self,
        patterns: List[Any],
        characteristics: Dict[str, Any],
        require_local: bool,
        privacy_level: str
    ) -> ExecutionMode:
        """Determine execution mode"""
        # Privacy requirements
        if require_local or privacy_level == 'P2':
            return ExecutionMode.LOCAL_ONLY

        # Fast track for simple tasks with high-confidence patterns
        if patterns and patterns[0].confidence_score > 0.9 and characteristics['complexity'] == 'low':
            return ExecutionMode.FAST_TRACK

        # Consensus for high-accuracy requirements
        if characteristics['requires_accuracy']:
            return ExecutionMode.CONSENSUS

        # Hybrid for complex tasks
        if characteristics['complexity'] == 'high':
            return ExecutionMode.HYBRID

        # Remote preferred for creative tasks
        if characteristics['is_creative_task']:
            return ExecutionMode.REMOTE_PREFERRED

        # Default: local only
        return ExecutionMode.LOCAL_ONLY

    def _determine_validation_level(
        self,
        patterns: List[Any],
        characteristics: Dict[str, Any],
        constraints: Dict[str, Any]
    ) -> ValidationLevel:
        """Determine validation strictness"""
        # High accuracy needs = strict validation
        if characteristics['requires_accuracy']:
            return ValidationLevel.STRICT

        # Code tasks need consensus validation
        if characteristics['is_code_task']:
            return ValidationLevel.CONSENSUS

        # Simple tasks with high confidence can use minimal
        if patterns and patterns[0].confidence_score > 0.8 and characteristics['complexity'] == 'low':
            return ValidationLevel.MINIMAL

        # Default: standard validation
        return ValidationLevel.STANDARD

    def _determine_backend_preference(
        self,
        mode: ExecutionMode,
        patterns: List[Any],
        characteristics: Dict[str, Any]
    ) -> List[str]:
        """Determine preferred backend order"""
        backends = []

        if mode == ExecutionMode.LOCAL_ONLY or mode == ExecutionMode.FAST_TRACK:
            # Local backends only
            if characteristics['is_code_task']:
                backends = ['ollama:qwen2.5-coder:7b', 'ollama:llama3.1:8b-instruct']
            else:
                backends = ['ollama:llama3.1:8b-instruct', 'ollama:qwen2.5-coder:7b']

        elif mode == ExecutionMode.REMOTE_PREFERRED:
            # Remote first, local backup
            backends = ['openrouter:anthropic/claude-3.5-sonnet', 'ollama:llama3.1:8b-instruct']

        elif mode == ExecutionMode.HYBRID:
            # Mix of local and remote
            backends = [
                'ollama:llama3.1:8b-instruct',
                'openrouter:anthropic/claude-3.5-sonnet',
                'ollama:qwen2.5-coder:7b'
            ]

        elif mode == ExecutionMode.CONSENSUS:
            # Multiple backends for consensus
            backends = [
                'ollama:llama3.1:8b-instruct',
                'ollama:qwen2.5-coder:7b',
                'openrouter:anthropic/claude-3.5-sonnet'
            ]

        return backends

    def _determine_timeout(
        self,
        patterns: List[Any],
        characteristics: Dict[str, Any],
        max_time: int
    ) -> int:
        """Determine appropriate timeout"""
        # Base timeout on complexity
        base_timeout = {
            'low': 60,
            'medium': 180,
            'high': 300
        }.get(characteristics['complexity'], 180)

        # Adjust for time sensitivity
        if characteristics['is_time_sensitive']:
            base_timeout = min(base_timeout, 60)

        # Pattern-based adjustment
        if patterns:
            avg_time = patterns[0].pattern_data.get('execution_time', 0) / 1000
            if avg_time > 0:
                base_timeout = int(avg_time * 1.5)  # 50% buffer

        # Respect max time constraint
        return min(base_timeout, max_time)

    def _determine_retry_strategy(
        self,
        patterns: List[Any],
        characteristics: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Determine retry strategy"""
        # Base retry configuration
        strategy = {
            'max_retries': 2,
            'backoff_multiplier': 1.5,
            'retry_on': ['timeout', 'api_error'],
            'escalate_on_retry': False
        }

        # Adjust based on complexity
        if characteristics['complexity'] == 'high':
            strategy['max_retries'] = 3
            strategy['escalate_on_retry'] = True

        # Adjust based on accuracy requirements
        if characteristics['requires_accuracy']:
            strategy['retry_on'].append('validation_failed')

        return strategy

    def _determine_context_optimization(
        self,
        characteristics: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Determine context optimization settings"""
        return {
            'enabled': True,
            'max_tokens': 4000 if characteristics['complexity'] == 'high' else 2000,
            'min_importance': 0.3,
            'preserve_examples': characteristics['has_examples']
        }

    def _estimate_resources(
        self,
        mode: ExecutionMode,
        validation_level: ValidationLevel,
        backends: List[str],
        characteristics: Dict[str, Any]
    ) -> Tuple[float, float]:
        """Estimate cost and time"""
        # Estimate time
        time_estimates = {
            'low': 30,
            'medium': 90,
            'high': 180
        }
        estimated_time = time_estimates.get(characteristics['complexity'], 90)

        # Adjust for mode
        if mode == ExecutionMode.CONSENSUS:
            estimated_time *= 1.5
        elif mode == ExecutionMode.FAST_TRACK:
            estimated_time *= 0.5

        # Estimate cost
        estimated_cost = 0.0

        # Count remote backend calls
        remote_calls = sum(1 for b in backends if not b.startswith('ollama'))

        # Cost per remote call (rough estimate)
        cost_per_call = {
            'claude-3.5-sonnet': 1.0,  # cents
            'gpt-4': 0.8,
            'gpt-3.5-turbo': 0.1
        }

        for backend in backends:
            if 'claude' in backend.lower():
                estimated_cost += cost_per_call['claude-3.5-sonnet']
            elif 'gpt-4' in backend.lower():
                estimated_cost += cost_per_call['gpt-4']
            elif 'gpt-3.5' in backend.lower():
                estimated_cost += cost_per_call['gpt-3.5-turbo']

        # Multiply by validation samples
        if validation_level == ValidationLevel.CONSENSUS:
            estimated_cost *= 3

        return estimated_cost, estimated_time

    def _calculate_strategy_confidence(
        self,
        patterns: List[Any],
        characteristics: Dict[str, Any]
    ) -> float:
        """Calculate confidence in strategy recommendation"""
        # Base confidence
        confidence = 0.5

        # Pattern-based confidence
        if patterns:
            pattern_confidence = patterns[0].confidence_score
            pattern_usage = min(patterns[0].usage_count / 10, 1.0)
            confidence += (pattern_confidence * 0.3 + pattern_usage * 0.2)

        # Characteristic-based confidence
        if characteristics['complexity'] == 'low':
            confidence += 0.1  # Simple tasks are more predictable

        # Execution history confidence
        if self._execution_history['total_jobs'] > 10:
            success_rate = (
                self._execution_history['successful_jobs'] /
                self._execution_history['total_jobs']
            )
            confidence += success_rate * 0.1

        return max(0.0, min(1.0, confidence))

    def _generate_strategy_reasoning(
        self,
        mode: ExecutionMode,
        validation_level: ValidationLevel,
        patterns: List[Any],
        characteristics: Dict[str, Any]
    ) -> str:
        """Generate human-readable reasoning"""
        reasons = []

        # Mode reasoning
        mode_reasons = {
            ExecutionMode.LOCAL_ONLY: "local execution for privacy/cost",
            ExecutionMode.REMOTE_PREFERRED: "remote backend for higher quality",
            ExecutionMode.HYBRID: "hybrid approach for complex task",
            ExecutionMode.CONSENSUS: "consensus validation for accuracy",
            ExecutionMode.FAST_TRACK: "fast track for simple task"
        }
        reasons.append(mode_reasons.get(mode, "standard execution"))

        # Validation reasoning
        val_reasons = {
            ValidationLevel.MINIMAL: "minimal validation sufficient",
            ValidationLevel.STANDARD: "standard validation applied",
            ValidationLevel.STRICT: "strict validation for accuracy",
            ValidationLevel.CONSENSUS: "consensus validation required"
        }
        reasons.append(val_reasons.get(validation_level, "standard validation"))

        # Pattern-based reasoning
        if patterns:
            pattern = patterns[0]
            reasons.append(
                f"matched pattern with {pattern.confidence_score:.0%} confidence "
                f"({pattern.usage_count} prior uses)"
            )

        # Characteristic-based reasoning
        if characteristics['complexity'] == 'high':
            reasons.append("high complexity task")
        elif characteristics['complexity'] == 'low':
            reasons.append("simple task")

        if characteristics['requires_accuracy']:
            reasons.append("accuracy requirements")

        if characteristics['is_time_sensitive']:
            reasons.append("time-sensitive")

        return "; ".join(reasons)

    def _get_default_strategy(self) -> ExecutionStrategy:
        """Get safe default strategy"""
        return ExecutionStrategy(
            mode=ExecutionMode.LOCAL_ONLY,
            validation_level=ValidationLevel.STANDARD,
            backend_preference=['ollama:llama3.1:8b-instruct'],
            timeout_seconds=180,
            retry_strategy={
                'max_retries': 2,
                'backoff_multiplier': 1.5,
                'retry_on': ['timeout', 'api_error'],
                'escalate_on_retry': False
            },
            context_optimization={
                'enabled': True,
                'max_tokens': 2000,
                'min_importance': 0.3,
                'preserve_examples': False
            },
            confidence_score=0.5,
            reasoning="default safe strategy",
            estimated_cost_cents=0.0,
            estimated_time_seconds=180.0
        )

    def get_strategy_stats(self) -> Dict[str, Any]:
        """Get statistics about execution strategies"""
        return {
            'execution_history': self._execution_history,
            'recommended_modes': {
                'local_only': 'Privacy-focused, zero cost',
                'remote_preferred': 'Higher quality, moderate cost',
                'hybrid': 'Balanced approach',
                'consensus': 'Maximum accuracy, higher cost',
                'fast_track': 'Speed-optimized for simple tasks'
            }
        }
