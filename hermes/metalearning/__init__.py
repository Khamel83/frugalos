"""
Hermes Meta-Learning System
Intelligent question generation, pattern recognition, and adaptive execution
"""

__version__ = "0.2.0"

from .question_generator import QuestionGenerator, Question, QuestionType
from .pattern_engine import PatternEngine, Pattern
from .conversation_manager import ConversationManager, ConversationState
from .context_optimizer import ContextOptimizer, ContextSegment
from .adaptive_prioritizer import AdaptivePrioritizer, PrioritizedQuestion
from .execution_strategy import ExecutionStrategyEngine, ExecutionStrategy, ExecutionMode, ValidationLevel
from .metrics import MetaLearningMetrics, MetricsSummary

__all__ = [
    'QuestionGenerator',
    'Question',
    'QuestionType',
    'PatternEngine',
    'Pattern',
    'ConversationManager',
    'ConversationState',
    'ContextOptimizer',
    'ContextSegment',
    'AdaptivePrioritizer',
    'PrioritizedQuestion',
    'ExecutionStrategyEngine',
    'ExecutionStrategy',
    'ExecutionMode',
    'ValidationLevel',
    'MetaLearningMetrics',
    'MetricsSummary',
]