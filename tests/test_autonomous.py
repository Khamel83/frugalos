"""
Test Suite for Autonomous Systems
Unit and integration tests for autonomous operation components
"""

import unittest
import tempfile
import os
from datetime import datetime, timedelta

from hermes.config import Config
from hermes.autonomous.scheduler import AutonomousScheduler, TaskPriority
from hermes.autonomous.suggestion_engine import ProactiveSuggestionEngine, SuggestionType
from hermes.autonomous.context_automation import ContextAwareAutomation, AutomationTrigger
from hermes.autonomous.learning_optimizer import LearningBasedOptimizer, OptimizationStrategy


class TestAutonomousScheduler(unittest.TestCase):
    """Test suite for Autonomous Scheduler"""

    def setUp(self):
        """Set up test environment"""
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        self.temp_db.close()

        self.config = Config()
        self.config._config['database']['path'] = self.temp_db.name
        self.config._config['autonomous']['scheduler']['enabled'] = True

        self.scheduler = AutonomousScheduler(self.config)

    def tearDown(self):
        """Clean up test environment"""
        try:
            self.scheduler.stop_scheduler()
            os.unlink(self.temp_db.name)
        except:
            pass

    def test_scheduler_initialization(self):
        """Test scheduler initialization"""
        self.assertIsNotNone(self.scheduler._task_queue)
        self.assertIsNotNone(self.scheduler._scheduled_tasks)
        self.assertIsNotNone(self.scheduler._running_tasks)

    def test_task_scheduling(self):
        """Test task scheduling"""
        from hermes.autonomous.scheduler import ScheduledTask

        task = ScheduledTask(
            task_id="test_task",
            idea="Test task",
            priority=TaskPriority.NORMAL,
            scheduled_time=datetime.now() + timedelta(minutes=5),
            deadline=None,
            recurrence=None,
            dependencies=[],
            context={},
            auto_generated=False,
            confidence_score=1.0
        )

        self.scheduler.schedule_task(task, persist=False)

        # Check task is in scheduled tasks
        self.assertIn(task.task_id, self.scheduler._scheduled_tasks)

        # Check task is in queue
        scheduled_tasks = self.scheduler.get_scheduled_tasks()
        task_ids = [t.task_id for t in scheduled_tasks]
        self.assertIn(task.task_id, task_ids)

    def test_task_cancellation(self):
        """Test task cancellation"""
        from hermes.autonomous.scheduler import ScheduledTask

        task = ScheduledTask(
            task_id="cancel_test",
            idea="Task to cancel",
            priority=TaskPriority.NORMAL,
            scheduled_time=datetime.now() + timedelta(minutes=5),
            deadline=None,
            recurrence=None,
            dependencies=[],
            context={},
            auto_generated=False,
            confidence_score=1.0
        )

        self.scheduler.schedule_task(task, persist=False)

        # Cancel task
        self.scheduler.cancel_task(task.task_id)

        # Task should be removed
        self.assertNotIn(task.task_id, self.scheduler._scheduled_tasks)

    def test_scheduler_stats(self):
        """Test scheduler statistics"""
        stats = self.scheduler.get_scheduler_stats()

        self.assertIn('enabled', stats)
        self.assertIn('running', stats)
        self.assertIn('scheduled_tasks', stats)
        self.assertIn('running_tasks', stats)
        self.assertIn('max_concurrent', stats)

    def test_schedule_at(self):
        """Test scheduling task at specific time"""
        idea = "Test task"
        scheduled_time = datetime.now() + timedelta(minutes=10)

        task_id = self.scheduler.schedule_at(
            idea=idea,
            scheduled_time=scheduled_time,
            priority=TaskPriority.NORMAL
        )

        self.assertIsInstance(task_id, str)
        self.assertIn(task_id, self.scheduler._scheduled_tasks)

    def test_schedule_recurring(self):
        """Test scheduling recurring task"""
        idea = "Daily backup"
        recurrence = "daily"

        task_id = self.scheduler.schedule_recurring(
            idea=idea,
            recurrence=recurrence,
            priority=TaskPriority.HIGH
        )

        self.assertIsInstance(task_id, str)
        self.assertIn(task_id, self.scheduler._scheduled_tasks)


class TestProactiveSuggestionEngine(unittest.TestCase):
    """Test suite for Proactive Suggestion Engine"""

    def setUp(self):
        """Set up test environment"""
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        self.temp_db.close()

        self.config = Config()
        self.config._config['database']['path'] = self.temp_db.name
        self.config._config['autonomous']['suggestions']['enabled'] = True

        self.suggestion_engine = ProactiveSuggestionEngine(self.config)

    def tearDown(self):
        """Clean up test environment"""
        try:
            os.unlink(self.temp_db.name)
        except:
            pass

    def test_suggestion_generation(self):
        """Test suggestion generation"""
        context = {
            'current_time': datetime.now(),
            'user_preferences': {}
        }

        suggestions = self.suggestion_engine.generate_suggestions(context)

        self.assertIsInstance(suggestions, list)

        # Each suggestion should have required fields
        for suggestion in suggestions:
            self.assertIsInstance(suggestion.suggestion_id, str)
            self.assertIsInstance(suggestion.suggestion_type, SuggestionType)
            self.assertIsInstance(suggestion.title, str)
            self.assertIsInstance(suggestion.description, str)
            self.assertIsInstance(suggestion.confidence_score, float)
            self.assertGreaterEqual(suggestion.confidence_score, 0)
            self.assertLessEqual(suggestion.confidence_score, 1)

    def test_task_suggestions(self):
        """Test task-based suggestions"""
        # Create mock repeated job data
        with self.suggestion_engine.db.get_connection() as conn:
            conn.execute("""
                INSERT INTO jobs (id, idea, status, created_at, cost_cents)
                VALUES (1, 'Process daily report', 'completed', datetime('now', '-1 day'), 10),
                       (2, 'Process daily report', 'completed', datetime('now', '-2 days'), 10),
                       (3, 'Process daily report', 'completed', datetime('now', '-3 days'), 10)
            """)
            conn.commit()

        suggestions = self.suggestion_engine.generate_suggestions()

        # Should have a task automation suggestion
        task_suggestions = [
            s for s in suggestions
            if s.suggestion_type == SuggestionType.TASK
        ]

        self.assertGreater(len(task_suggestions), 0)

    def test_suggestion_acceptance(self):
        """Test suggestion acceptance and action"""
        # Create a test suggestion
        suggestion = self.suggestion_engine._generate_optimization_suggestions({})

        if suggestion:
            suggestion_id = suggestion[0].suggestion_id

            result = self.suggestion_engine.accept_suggestion(suggestion_id)

            self.assertIsInstance(result, dict)

            # Suggestion should be removed from active
            active = self.suggestion_engine.get_active_suggestions()
            active_ids = [s.suggestion_id for s in active]
            self.assertNotIn(suggestion_id, active_ids)

    def test_suggestion_dismissal(self):
        """Test suggestion dismissal"""
        # Create a test suggestion
        suggestion = self.suggestion_engine._generate_optimization_suggestions({})

        if suggestion:
            suggestion_id = suggestion[0].suggestion_id

            self.suggestion_engine.dismiss_suggestion(suggestion_id)

            # Suggestion should be removed from active
            active = self.suggestion_engine.get_active_suggestions()
            active_ids = [s.suggestion_id for s in active]
            self.assertNotIn(suggestion_id, active_ids)

    def test_suggestion_stats(self):
        """Test suggestion statistics"""
        stats = self.suggestion_engine.get_suggestion_stats()

        self.assertIn('enabled', stats)
        self.assertIn('active_suggestions', stats)
        self.assertIn('dismissed_suggestions', stats)
        self.assertIn('accepted_suggestions', stats)


class TestContextAwareAutomation(unittest.TestCase):
    """Test suite for Context-Aware Automation"""

    def setUp(self):
        """Set up test environment"""
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        self.temp_db.close()

        self.config = Config()
        self.config._config['database']['path'] = self.temp_db.name
        self.config._config['autonomous']['automation']['enabled'] = True

        self.automation = ContextAwareAutomation(self.config)

    def tearDown(self):
        """Clean up test environment"""
        try:
            os.unlink(self.temp_db.name)
        except:
            pass

    def test_automation_rule_creation(self):
        """Test automation rule creation"""
        rule_id = self.automation.create_rule(
            name="Daily Health Check",
            description="Run system health check daily",
            trigger_type=AutomationTrigger.TIME_BASED,
            trigger_config={
                'time': '09:00',
                'days': ['monday', 'tuesday', 'wednesday', 'thursday', 'friday']
            },
            actions=[
                {
                    'type': 'run_job',
                    'idea': 'Run system health check',
                    'context': {'system': 'health'}
                }
            ],
            priority=3
        )

        self.assertIsInstance(rule_id, str)
        self.assertIn(rule_id, self.automation._rules)

    def test_trigger_evaluation(self):
        """Test trigger evaluation"""
        # Create a time-based rule
        rule_id = self.automation.create_rule(
            name="Test Rule",
            description="Test rule",
            trigger_type=AutomationTrigger.TIME_BASED,
            trigger_config={'time': '23:59'},  # Unlikely to match current time
            actions=[],
            priority=5
        )

        rule = self.automation._rules[rule_id]

        # Should not trigger (wrong time)
        context = self.automation._get_current_context()
        should_trigger = self.automation._should_trigger(rule, context)
        self.assertFalse(should_trigger)

    def test_condition_evaluation(self):
        """Test condition evaluation"""
        # Rule with condition
        condition = {
            'type': 'not_recently_triggered',
            'min_interval_minutes': 60
        }

        context = self.automation._get_current_context()
        result = self.automation._evaluate_condition(condition, context)

        self.assertIsInstance(result, bool)

    def test_action_execution(self):
        """Test action execution"""
        action = {
            'type': 'log_event',
            'message': 'Test automation action'
        }

        context = {}
        result = self.automation._execute_action(action, context)

        self.assertIn('action', result)
        self.assertIn('status', result)

    def test_automation_stats(self):
        """Test automation statistics"""
        stats = self.automation.get_automation_stats()

        self.assertIn('enabled', stats)
        self.assertIn('total_rules', stats)
        self.assertIn('active_automations', stats)


class TestLearningBasedOptimizer(unittest.TestCase):
    """Test suite for Learning-Based Optimizer"""

    def setUp(self):
        """Set up test environment"""
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        self.temp_db.close()

        self.config = Config()
        self.config._config['database']['path'] = self.temp_db.name
        self.config._config['autonomous']['optimization']['enabled'] = True

        self.optimizer = LearningBasedOptimizer(self.config)

    def tearDown(self):
        """Clean up test environment"""
        try:
            os.unlink(self.temp_db.name)
        except:
            pass

    def test_optimization_generation(self):
        """Test optimization recommendation generation"""
        context = {
            'current_time': datetime.now(),
            'system_load': 0.5
        }

        recommendations = self.optimizer.optimize(
            strategy=OptimizationStrategy.BALANCED,
            context=context
        )

        self.assertIsInstance(recommendations, list)

        # Each recommendation should have required fields
        for rec in recommendations:
            self.assertIsInstance(rec.recommendation_id, str)
            self.assertIsInstance(rec.category, str)
            self.assertIsInstance(rec.title, str)
            self.assertIsInstance(rec.description, str)
            self.assertIn(rec.impact, ['high', 'medium', 'low'])
            self.assertIn(rec.effort, ['high', 'medium', 'low'])
            self.assertIsInstance(rec.confidence, float)

    def test_backend_optimization(self):
        """Test backend optimization recommendations"""
        context = {}

        recommendations = self.optimizer._optimize_backend_selection(
            OptimizationStrategy.COST,
            context
        )

        self.assertIsInstance(recommendations, list)

    def test_scheduling_optimization(self):
        """Test scheduling optimization recommendations"""
        context = {}

        recommendations = self.optimizer._optimize_scheduling(
            OptimizationStrategy.SPEED,
            context
        )

        self.assertIsInstance(recommendations, list)

    def test_optimization_application(self):
        """Test optimization recommendation application"""
        from hermes.autonomous.learning_optimizer import OptimizationRecommendation

        rec = OptimizationRecommendation(
            recommendation_id="test_opt",
            category="test",
            title="Test optimization",
            description="Test description",
            impact="low",
            effort="low",
            estimated_savings={},
            confidence=0.8,
            actions=[{
                'type': 'log_event',
                'message': 'Test optimization applied'
            }],
            rationale="Test"
        )

        result = self.optimizer.apply_optimization(rec)

        self.assertIsInstance(result, dict)
        self.assertIn('success', result)

    def test_optimizer_stats(self):
        """Test optimizer statistics"""
        stats = self.optimizer.get_optimizer_stats()

        self.assertIn('enabled', stats)
        self.assertIn('learning_window_days', stats)
        self.assertIn('min_samples', stats)
        self.assertIn('baseline', stats)


if __name__ == '__main__':
    unittest.main()