"""
Proactive Suggestion Engine
Generates intelligent suggestions based on patterns, context, and user behavior
"""

import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from collections import defaultdict

from ..config import Config
from ..database import Database
from ..logger import get_logger
from ..metalearning.pattern_engine import PatternEngine
from ..metalearning.conversation_manager import ConversationManager

logger = get_logger('autonomous.suggestion_engine')

class SuggestionType(Enum):
    """Types of suggestions"""
    TASK = "task"  # Suggest a new task
    OPTIMIZATION = "optimization"  # Suggest an optimization
    PATTERN = "pattern"  # Pattern-based suggestion
    REMINDER = "reminder"  # Reminder for follow-up
    AUTOMATION = "automation"  # Suggest automation
    LEARNING = "learning"  # Learning opportunity

@dataclass
class Suggestion:
    """A proactive suggestion"""
    suggestion_id: str
    suggestion_type: SuggestionType
    title: str
    description: str
    confidence_score: float
    priority: int
    rationale: str
    action_items: List[Dict[str, Any]]
    context: Dict[str, Any]
    created_at: datetime
    expires_at: Optional[datetime]

class ProactiveSuggestionEngine:
    """Generates proactive suggestions for users"""

    def __init__(self, config: Optional[Config] = None):
        self.config = config or Config()
        self.db = Database()
        self.pattern_engine = PatternEngine(config)
        self.conversation_manager = ConversationManager(config)
        self.logger = get_logger('suggestion_engine')

        # Suggestion configuration
        self.enabled = self.config.get('autonomous.suggestions.enabled', True)
        self.min_confidence = self.config.get('autonomous.suggestions.min_confidence', 0.6)
        self.max_suggestions = self.config.get('autonomous.suggestions.max_active', 10)

        # Suggestion state
        self._active_suggestions = {}  # suggestion_id -> Suggestion
        self._dismissed_suggestions = set()
        self._accepted_suggestions = {}  # suggestion_id -> result

    def generate_suggestions(self, context: Dict[str, Any] = None) -> List[Suggestion]:
        """
        Generate proactive suggestions

        Args:
            context: Current context information

        Returns:
            List of suggestions
        """
        if not self.enabled:
            return []

        suggestions = []
        context = context or {}

        try:
            # Generate different types of suggestions
            suggestions.extend(self._generate_task_suggestions(context))
            suggestions.extend(self._generate_optimization_suggestions(context))
            suggestions.extend(self._generate_pattern_suggestions(context))
            suggestions.extend(self._generate_reminder_suggestions(context))
            suggestions.extend(self._generate_automation_suggestions(context))
            suggestions.extend(self._generate_learning_suggestions(context))

            # Filter by confidence
            suggestions = [s for s in suggestions if s.confidence_score >= self.min_confidence]

            # Sort by priority and confidence
            suggestions.sort(key=lambda s: (s.priority, -s.confidence_score))

            # Limit number
            suggestions = suggestions[:self.max_suggestions]

            # Store active suggestions
            for suggestion in suggestions:
                self._active_suggestions[suggestion.suggestion_id] = suggestion

            self.logger.info(f"Generated {len(suggestions)} proactive suggestions")

            return suggestions

        except Exception as e:
            self.logger.error(f"Error generating suggestions: {e}")
            return []

    def _generate_task_suggestions(self, context: Dict[str, Any]) -> List[Suggestion]:
        """Generate task-based suggestions"""
        suggestions = []

        try:
            # Analyze recent job patterns
            with self.db.get_connection() as conn:
                cursor = conn.execute("""
                    SELECT idea, COUNT(*) as frequency
                    FROM jobs
                    WHERE created_at >= datetime('now', '-7 days')
                    AND status = 'completed'
                    GROUP BY idea
                    HAVING COUNT(*) >= 2
                    ORDER BY COUNT(*) DESC
                    LIMIT 5
                """)

                for row in cursor.fetchall():
                    idea = row['idea']
                    frequency = row['frequency']

                    # Suggest automation for repeated tasks
                    suggestion = Suggestion(
                        suggestion_id=f"task_auto_{hash(idea) % 10000}",
                        suggestion_type=SuggestionType.TASK,
                        title=f"Automate recurring task",
                        description=f"You've run this task {frequency} times recently. Consider automating it.",
                        confidence_score=min(0.9, 0.5 + (frequency * 0.1)),
                        priority=2,
                        rationale=f"Task '{idea[:50]}...' has been executed {frequency} times in the past week",
                        action_items=[
                            {
                                'action': 'schedule_recurring',
                                'idea': idea,
                                'recurrence': 'daily'
                            }
                        ],
                        context={'original_idea': idea, 'frequency': frequency},
                        created_at=datetime.now(),
                        expires_at=datetime.now() + timedelta(days=7)
                    )

                    suggestions.append(suggestion)

        except Exception as e:
            self.logger.error(f"Error generating task suggestions: {e}")

        return suggestions

    def _generate_optimization_suggestions(self, context: Dict[str, Any]) -> List[Suggestion]:
        """Generate optimization suggestions"""
        suggestions = []

        try:
            # Check for slow jobs
            with self.db.get_connection() as conn:
                cursor = conn.execute("""
                    SELECT AVG(execution_time_ms) as avg_time, backend_id
                    FROM jobs
                    WHERE created_at >= datetime('now', '-3 days')
                    AND status = 'completed'
                    GROUP BY backend_id
                    HAVING AVG(execution_time_ms) > 5000
                """)

                for row in cursor.fetchall():
                    avg_time = row['avg_time']

                    suggestion = Suggestion(
                        suggestion_id=f"opt_speed_{int(datetime.now().timestamp())}",
                        suggestion_type=SuggestionType.OPTIMIZATION,
                        title="Optimize execution speed",
                        description=f"Jobs are taking {avg_time/1000:.1f}s on average. Consider using faster backends.",
                        confidence_score=0.7,
                        priority=3,
                        rationale=f"Average execution time ({avg_time/1000:.1f}s) exceeds recommended threshold",
                        action_items=[
                            {
                                'action': 'switch_backend',
                                'to': 'faster_local'
                            }
                        ],
                        context={'avg_time_ms': avg_time},
                        created_at=datetime.now(),
                        expires_at=datetime.now() + timedelta(days=3)
                    )

                    suggestions.append(suggestion)

        except Exception as e:
            self.logger.error(f"Error generating optimization suggestions: {e}")

        return suggestions

    def _generate_pattern_suggestions(self, context: Dict[str, Any]) -> List[Suggestion]:
        """Generate pattern-based suggestions"""
        suggestions = []

        try:
            # Get pattern statistics
            stats = self.pattern_engine.get_pattern_statistics()

            if stats.get('total_patterns', 0) > 0:
                high_conf_patterns = stats.get('high_confidence_patterns', 0)

                if high_conf_patterns > 5:
                    suggestion = Suggestion(
                        suggestion_id=f"pattern_reuse_{int(datetime.now().timestamp())}",
                        suggestion_type=SuggestionType.PATTERN,
                        title="Leverage learned patterns",
                        description=f"You have {high_conf_patterns} high-confidence patterns. Hermes can suggest optimal approaches.",
                        confidence_score=0.8,
                        priority=2,
                        rationale=f"System has learned {high_conf_patterns} reliable patterns from your usage",
                        action_items=[
                            {
                                'action': 'enable_pattern_suggestions',
                                'for_all_tasks': True
                            }
                        ],
                        context={'pattern_count': high_conf_patterns},
                        created_at=datetime.now(),
                        expires_at=None  # Doesn't expire
                    )

                    suggestions.append(suggestion)

        except Exception as e:
            self.logger.error(f"Error generating pattern suggestions: {e}")

        return suggestions

    def _generate_reminder_suggestions(self, context: Dict[str, Any]) -> List[Suggestion]:
        """Generate reminder suggestions"""
        suggestions = []

        try:
            # Check for failed jobs that might need retry
            with self.db.get_connection() as conn:
                cursor = conn.execute("""
                    SELECT id, idea, error_message, created_at
                    FROM jobs
                    WHERE status = 'failed'
                    AND created_at >= datetime('now', '-1 day')
                    ORDER BY created_at DESC
                    LIMIT 3
                """)

                for row in cursor.fetchall():
                    job_id = row['id']
                    idea = row['idea']
                    error = row['error_message']

                    suggestion = Suggestion(
                        suggestion_id=f"reminder_retry_{job_id}",
                        suggestion_type=SuggestionType.REMINDER,
                        title="Retry failed job",
                        description=f"Job failed: '{idea[:50]}...'. Would you like to retry?",
                        confidence_score=0.6,
                        priority=3,
                        rationale=f"Job failed with error: {error[:100] if error else 'Unknown error'}",
                        action_items=[
                            {
                                'action': 'retry_job',
                                'job_id': job_id,
                                'idea': idea
                            }
                        ],
                        context={'job_id': job_id, 'error': error},
                        created_at=datetime.now(),
                        expires_at=datetime.now() + timedelta(days=3)
                    )

                    suggestions.append(suggestion)

        except Exception as e:
            self.logger.error(f"Error generating reminder suggestions: {e}")

        return suggestions

    def _generate_automation_suggestions(self, context: Dict[str, Any]) -> List[Suggestion]:
        """Generate automation suggestions"""
        suggestions = []

        try:
            # Look for repetitive question patterns
            with self.db.get_connection() as conn:
                cursor = conn.execute("""
                    SELECT question_type, COUNT(*) as count
                    FROM metalearning_questions
                    WHERE asked_at >= datetime('now', '-7 days')
                    GROUP BY question_type
                    HAVING COUNT(*) > 10
                """)

                for row in cursor.fetchall():
                    qtype = row['question_type']
                    count = row['count']

                    suggestion = Suggestion(
                        suggestion_id=f"auto_questions_{qtype}",
                        suggestion_type=SuggestionType.AUTOMATION,
                        title=f"Automate {qtype} questions",
                        description=f"You've answered {count} {qtype} questions. Set defaults to skip these.",
                        confidence_score=0.75,
                        priority=2,
                        rationale=f"{qtype} questions asked {count} times in past week",
                        action_items=[
                            {
                                'action': 'set_default_answer',
                                'question_type': qtype
                            }
                        ],
                        context={'question_type': qtype, 'frequency': count},
                        created_at=datetime.now(),
                        expires_at=datetime.now() + timedelta(days=7)
                    )

                    suggestions.append(suggestion)

        except Exception as e:
            self.logger.error(f"Error generating automation suggestions: {e}")

        return suggestions

    def _generate_learning_suggestions(self, context: Dict[str, Any]) -> List[Suggestion]:
        """Generate learning opportunity suggestions"""
        suggestions = []

        try:
            # Check conversation success rate
            with self.db.get_connection() as conn:
                cursor = conn.execute("""
                    SELECT
                        COUNT(*) as total,
                        SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed
                    FROM conversations
                    WHERE created_at >= datetime('now', '-7 days')
                """)

                row = cursor.fetchone()
                if row and row['total'] > 10:
                    success_rate = row['completed'] / row['total']

                    if success_rate < 0.7:
                        suggestion = Suggestion(
                            suggestion_id=f"learning_improve_{int(datetime.now().timestamp())}",
                            suggestion_type=SuggestionType.LEARNING,
                            title="Improve task success rate",
                            description=f"Current success rate is {success_rate:.0%}. Provide more context in task descriptions.",
                            confidence_score=0.7,
                            priority=2,
                            rationale=f"Success rate ({success_rate:.0%}) is below optimal threshold (70%)",
                            action_items=[
                                {
                                    'action': 'enable_context_gathering',
                                    'for_all_tasks': True
                                }
                            ],
                            context={'success_rate': success_rate},
                            created_at=datetime.now(),
                            expires_at=datetime.now() + timedelta(days=7)
                        )

                        suggestions.append(suggestion)

        except Exception as e:
            self.logger.error(f"Error generating learning suggestions: {e}")

        return suggestions

    def get_active_suggestions(self) -> List[Suggestion]:
        """Get all active suggestions"""
        # Filter out expired suggestions
        now = datetime.now()
        active = [
            s for s in self._active_suggestions.values()
            if s.expires_at is None or s.expires_at > now
        ]

        # Remove from dismissed
        active = [s for s in active if s.suggestion_id not in self._dismissed_suggestions]

        return sorted(active, key=lambda s: (s.priority, -s.confidence_score))

    def dismiss_suggestion(self, suggestion_id: str):
        """Dismiss a suggestion"""
        self._dismissed_suggestions.add(suggestion_id)
        if suggestion_id in self._active_suggestions:
            del self._active_suggestions[suggestion_id]

        self.logger.info(f"Dismissed suggestion {suggestion_id}")

    def accept_suggestion(self, suggestion_id: str) -> Dict[str, Any]:
        """
        Accept and act on a suggestion

        Args:
            suggestion_id: ID of suggestion to accept

        Returns:
            Result of acting on suggestion
        """
        if suggestion_id not in self._active_suggestions:
            return {'success': False, 'error': 'Suggestion not found'}

        suggestion = self._active_suggestions[suggestion_id]

        try:
            # Execute action items
            results = []
            for action_item in suggestion.action_items:
                result = self._execute_action(action_item, suggestion.context)
                results.append(result)

            # Mark as accepted
            self._accepted_suggestions[suggestion_id] = {
                'accepted_at': datetime.now(),
                'results': results
            }

            # Remove from active
            del self._active_suggestions[suggestion_id]

            self.logger.info(f"Accepted and executed suggestion {suggestion_id}")

            return {
                'success': True,
                'suggestion': suggestion,
                'results': results
            }

        except Exception as e:
            self.logger.error(f"Error accepting suggestion: {e}")
            return {'success': False, 'error': str(e)}

    def _execute_action(self, action_item: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute an action from a suggestion"""
        action_type = action_item.get('action')

        if action_type == 'schedule_recurring':
            # Schedule recurring task
            from .scheduler import AutonomousScheduler, TaskPriority
            scheduler = AutonomousScheduler(self.config)
            task_id = scheduler.schedule_recurring(
                idea=action_item['idea'],
                recurrence=action_item['recurrence'],
                priority=TaskPriority.NORMAL
            )
            return {'action': 'scheduled', 'task_id': task_id}

        elif action_type == 'retry_job':
            # Retry failed job
            job_id = action_item.get('job_id')
            idea = action_item.get('idea')

            from ..queue import JobQueue
            queue = JobQueue(self.config)
            new_job_id = self.db.create_job(idea)
            queue.enqueue_job(new_job_id, idea)

            return {'action': 'retried', 'new_job_id': new_job_id}

        elif action_type == 'enable_pattern_suggestions':
            # Enable pattern-based suggestions
            return {'action': 'enabled_patterns', 'status': 'enabled'}

        else:
            # Default: just log the action
            self.logger.info(f"Executed action: {action_type}")
            return {'action': action_type, 'status': 'completed'}

    def get_suggestion_stats(self) -> Dict[str, Any]:
        """Get suggestion statistics"""
        return {
            'enabled': self.enabled,
            'active_suggestions': len(self._active_suggestions),
            'dismissed_suggestions': len(self._dismissed_suggestions),
            'accepted_suggestions': len(self._accepted_suggestions),
            'min_confidence': self.min_confidence,
            'max_suggestions': self.max_suggestions,
            'by_type': {
                stype.value: len([
                    s for s in self._active_suggestions.values()
                    if s.suggestion_type == stype
                ])
                for stype in SuggestionType
            }
        }
