"""
Hermes Autonomous Operation System
Autonomous scheduling, proactive suggestions, and intelligent automation
"""

__version__ = "0.1.0"

from .scheduler import AutonomousScheduler, ScheduledTask, TaskPriority
from .suggestion_engine import ProactiveSuggestionEngine, Suggestion, SuggestionType
from .context_automation import ContextAwareAutomation, AutomationRule, AutomationTrigger
from .learning_optimizer import LearningBasedOptimizer, OptimizationStrategy

__all__ = [
    'AutonomousScheduler',
    'ScheduledTask',
    'TaskPriority',
    'ProactiveSuggestionEngine',
    'Suggestion',
    'SuggestionType',
    'ContextAwareAutomation',
    'AutomationRule',
    'AutomationTrigger',
    'LearningBasedOptimizer',
    'OptimizationStrategy',
]
