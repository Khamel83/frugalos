"""
Hermes Autonomous Development System
Self-modifying, self-healing, and self-optimizing capabilities
"""

__version__ = "0.1.0"

from .code_modifier import CodeModifier, ModificationType, ModificationSafety
from .autonomous_learner import AutonomousLearner, LearningObjective
from .self_healing import SelfHealingSystem, HealingType
from .auto_optimizer import AutoOptimizer, OptimizationStrategy

__all__ = [
    'CodeModifier',
    'ModificationType',
    'ModificationSafety',
    'AutonomousLearner',
    'LearningObjective',
    'SelfHealingSystem',
    'HealingType',
    'AutoOptimizer',
    'OptimizationStrategy',
]
