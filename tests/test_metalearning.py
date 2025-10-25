"""
Test Suite for Meta-Learning Systems
Unit and integration tests for meta-learning components
"""

import unittest
import tempfile
import os
from datetime import datetime

from hermes.config import Config
from hermes.metalearning.question_generator import QuestionGenerator
from hermes.metalearning.pattern_engine import PatternEngine
from hermes.metalearning.conversation_manager import ConversationManager
from hermes.metalearning.context_optimizer import ContextOptimizer
from hermes.metalearning.adaptive_prioritizer import AdaptivePrioritizer
from hermes.metalearning.execution_strategy import ExecutionStrategyEngine
from hermes.metalearning.metrics import MetaLearningMetrics


class TestQuestionGenerator(unittest.TestCase):
    """Test suite for Question Generator"""

    def setUp(self):
        """Set up test environment"""
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        self.temp_db.close()

        self.config = Config()
        self.config._config['database']['path'] = self.temp_db.name

        self.question_generator = QuestionGenerator(self.config)

    def tearDown(self):
        """Clean up test environment"""
        try:
            os.unlink(self.temp_db.name)
        except:
            pass

    def test_question_generation(self):
        """Test basic question generation"""
        idea = "Create a function to process data"
        conversation_id = 1

        questions = self.question_generator.generate_questions(idea, conversation_id)

        self.assertIsInstance(questions, list)
        self.assertGreater(len(questions), 0)

        for question in questions:
            self.assertIsInstance(question.question_text, str)
            self.assertGreater(len(question.question_text), 0)
            self.assertIsInstance(question.question_type, str)

    def test_idea_categorization(self):
        """Test idea categorization"""
        # Technical task
        idea = "Write a Python script to analyze CSV files"
        category = self.question_generator._categorize_idea(idea)
        self.assertEqual(category, 'technical_task')

        # Data processing
        idea = "Process large dataset and extract insights"
        category = self.question_generator._categorize_idea(idea)
        self.assertEqual(category, 'data_processing')

        # Creative task
        idea = "Write a poem about artificial intelligence"
        category = self.question_generator._categorize_idea(idea)
        self.assertEqual(category, 'creative_task')

        # Vague idea
        idea = "Something with computers"
        category = self.question_generator._categorize_idea(idea)
        self.assertEqual(category, 'vague_idea')


class TestPatternEngine(unittest.TestCase):
    """Test suite for Pattern Engine"""

    def setUp(self):
        """Set up test environment"""
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        self.temp_db.close()

        self.config = Config()
        self.config._config['database']['path'] = self.temp_db.name

        self.pattern_engine = PatternEngine(self.config)

    def tearDown(self):
        """Clean up test environment"""
        try:
            os.unlink(self.temp_db.name)
        except:
            pass

    def test_pattern_recognition(self):
        """Test pattern recognition"""
        idea = "Create a function to process data"
        context = {'task_type': 'code'}

        patterns = self.pattern_engine.recognize_patterns(idea, context)

        self.assertIsInstance(patterns, list)

    def test_pattern_learning(self):
        """Test pattern learning from interactions"""
        idea = "Create a function to process data"
        questions = [
            {'question_type': 'clarification', 'question_text': 'What data format?'}
        ]
        answers = [
            {'response_text': 'CSV files', 'confidence_score': 0.8}
        ]
        outcome = {
            'success': True,
            'execution_time_ms': 5000,
            'error_count': 0
        }

        # Learn from interaction
        self.pattern_engine.learn_from_interaction(idea, questions, answers, outcome)

        # Check pattern statistics
        stats = self.pattern_engine.get_pattern_statistics()
        self.assertIsInstance(stats, dict)

    def test_pattern_suggestions(self):
        """Test pattern-based suggestions"""
        idea = "Create a function to process data"

        suggestions = self.pattern_engine.get_suggestions(idea)

        self.assertIsInstance(suggestions, dict)


class TestConversationManager(unittest.TestCase):
    """Test suite for Conversation Manager"""

    def setUp(self):
        """Set up test environment"""
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        self.temp_db.close()

        self.config = Config()
        self.config._config['database']['path'] = self.temp_db.name

        self.conversation_manager = ConversationManager(self.config)

    def tearDown(self):
        """Clean up test environment"""
        try:
            os.unlink(self.temp_db.name)
        except:
            pass

    def test_conversation_creation(self):
        """Test conversation creation"""
        job_id = 1
        idea = "Create a function to process data"

        conversation_id = self.conversation_manager.create_conversation(job_id, idea)

        self.assertIsInstance(conversation_id, int)
        self.assertGreater(conversation_id, 0)

    def test_context_gathering(self):
        """Test context gathering"""
        job_id = 1
        idea = "Create a function to process data"

        conversation_id = self.conversation_manager.create_conversation(job_id, idea)

        questions = self.conversation_manager.start_context_gathering(conversation_id, idea)

        self.assertIsInstance(questions, list)

    def test_conversation_finalization(self):
        """Test conversation finalization and learning"""
        job_id = 1
        idea = "Create a function to process data"

        conversation_id = self.conversation_manager.create_conversation(job_id, idea)

        # Add some messages
        self.conversation_manager.add_message(
            conversation_id,
            "user",
            idea
        )

        # Finalize
        outcome = {
            'success': True,
            'execution_time_ms': 5000,
            'backend': 'local',
            'error_count': 0
        }

        result = self.conversation_manager.finalize_conversation(conversation_id, outcome)
        self.assertTrue(result)


class TestContextOptimizer(unittest.TestCase):
    """Test suite for Context Optimizer"""

    def setUp(self):
        """Set up test environment"""
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        self.temp_db.close()

        self.config = Config()
        self.config._config['database']['path'] = self.temp_db.name

        self.context_optimizer = ContextOptimizer(self.config)

    def tearDown(self):
        """Clean up test environment"""
        try:
            os.unlink(self.temp_db.name)
        except:
            pass

    def test_context_optimization(self):
        """Test context optimization"""
        # First, create a conversation with some messages
        conversation_id = 1

        # Mock conversation messages for testing
        with self.context_optimizer.db.get_connection() as conn:
            # Create conversation
            conn.execute("""
                INSERT INTO conversations (id, job_id, initial_idea, status, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (conversation_id, 1, "Test idea", "completed", datetime.now(), datetime.now()))

            # Add some messages
            conn.execute("""
                INSERT INTO conversation_messages (conversation_id, message_type, content, created_at)
                VALUES (?, ?, ?, ?), (?, ?, ?, ?)
            """, (
                conversation_id, "user", "Initial idea", datetime.now(),
                conversation_id, "assistant", "Response", datetime.now()
            ))
            conn.commit()

        # Optimize context
        optimized = self.context_optimizer.optimize_context(conversation_id)

        self.assertIsInstance(optimized, dict)
        self.assertIn('segments', optimized)
        self.assertIn('optimization_stats', optimized)

    def test_optimization_stats(self):
        """Test optimization statistics"""
        conversation_id = 1

        stats = self.context_optimizer.get_optimization_stats(conversation_id)

        self.assertIsInstance(stats, dict)


class TestAdaptivePrioritizer(unittest.TestCase):
    """Test suite for Adaptive Prioritizer"""

    def setUp(self):
        """Set up test environment"""
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        self.temp_db.close()

        self.config = Config()
        self.config._config['database']['path'] = self.temp_db.name

        self.adaptive_prioritizer = AdaptivePrioritizer(self.config)

    def tearDown(self):
        """Clean up test environment"""
        try:
            os.unlink(self.temp_db.name)
        except:
            pass

    def test_question_prioritization(self):
        """Test question prioritization"""
        questions = [
            {
                'question_id': 'q1',
                'question_text': 'What format is the data in?',
                'question_type': 'clarification',
                'priority': 5
            },
            {
                'question_id': 'q2',
                'question_text': 'What should the output format be?',
                'question_type': 'validation',
                'priority': 3
            }
        ]

        conversation_id = 1
        idea = "Create a function to process data"

        prioritized = self.adaptive_prioritizer.prioritize_questions(
            questions,
            conversation_id,
            idea
        )

        self.assertIsInstance(prioritized, list)
        self.assertEqual(len(prioritized), len(questions))

        for p in prioritized:
            self.assertIsInstance(p.question_id, str)
            self.assertIsInstance(p.dynamic_priority, float)
            self.assertIsInstance(p.skip_likelihood, float)

    def test_question_subset_suggestion(self):
        """Test question subset suggestion"""
        # Create prioritized questions
        questions = [
            {
                'question_id': 'q1',
                'question_text': 'Test question 1',
                'question_type': 'clarification',
                'priority': 5
            }
        ]

        prioritized = self.adaptive_prioritizer.prioritize_questions(
            questions,
            1,
            "Test idea"
        )

        to_ask, to_skip = self.adaptive_prioritizer.suggest_question_subset(
            prioritized,
            max_questions=3
        )

        self.assertIsInstance(to_ask, list)
        self.assertIsInstance(to_skip, list)


class TestExecutionStrategyEngine(unittest.TestCase):
    """Test suite for Execution Strategy Engine"""

    def setUp(self):
        """Set up test environment"""
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        self.temp_db.close()

        self.config = Config()
        self.config._config['database']['path'] = self.temp_db.name

        self.execution_strategy_engine = ExecutionStrategyEngine(self.config)

    def tearDown(self):
        """Clean up test environment"""
        try:
            os.unlink(self.temp_db.name)
        except:
            pass

    def test_strategy_determination(self):
        """Test execution strategy determination"""
        idea = "Create a Python function to analyze data"
        context = {}
        constraints = {}

        strategy = self.execution_strategy_engine.determine_strategy(
            idea,
            context,
            constraints
        )

        self.assertIsNotNone(strategy)
        self.assertIsInstance(strategy.mode.value, str)
        self.assertIsInstance(strategy.validation_level.value, str)
        self.assertIsInstance(strategy.backend_preference, list)
        self.assertGreater(strategy.timeout_seconds, 0)

    def test_cost_and_time_estimation(self):
        """Test cost and time estimation"""
        idea = "Simple task"
        context = {}
        constraints = {}

        strategy = self.execution_strategy_engine.determine_strategy(
            idea,
            context,
            constraints
        )

        self.assertGreaterEqual(strategy.estimated_cost_cents, 0)
        self.assertGreater(strategy.estimated_time_seconds, 0)

    def test_get_strategy_stats(self):
        """Test strategy statistics"""
        stats = self.execution_strategy_engine.get_strategy_stats()

        self.assertIsInstance(stats, dict)
        self.assertIn('execution_history', stats)
        self.assertIn('recommended_modes', stats)


if __name__ == '__main__':
    unittest.main()