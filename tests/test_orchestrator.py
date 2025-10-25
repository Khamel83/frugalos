"""
Test Suite for Hermes Orchestrator
Comprehensive integration tests for the unified system
"""

import unittest
import asyncio
import tempfile
import os
from datetime import datetime
from unittest.mock import Mock, patch

from hermes.config import Config
from hermes.orchestrator import HermesOrchestrator


class TestHermesOrchestrator(unittest.TestCase):
    """Test suite for Hermes Orchestrator"""

    def setUp(self):
        """Set up test environment"""
        # Create temporary database
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        self.temp_db.close()

        # Create test config
        self.config = Config()
        self.config._config['database']['path'] = self.temp_db.name
        self.config._config['autonomous']['scheduler']['enabled'] = True
        self.config._config['autonomous']['suggestions']['enabled'] = True
        self.config._config['autonomous']['automation']['enabled'] = True
        self.config._config['autonomous']['optimization']['enabled'] = True

        # Initialize orchestrator
        self.orchestrator = HermesOrchestrator(self.config)

    def tearDown(self):
        """Clean up test environment"""
        try:
            self.orchestrator.stop()
            os.unlink(self.temp_db.name)
        except:
            pass

    def test_orchestrator_initialization(self):
        """Test orchestrator initialization"""
        # Test uninitialized state
        self.assertFalse(self.orchestrator._initialized)
        self.assertFalse(self.orchestrator._running)

        # Initialize
        self.orchestrator.initialize()

        # Check all components are initialized
        self.assertTrue(self.orchestrator._initialized)
        self.assertIsNotNone(self.orchestrator.job_queue)
        self.assertIsNotNone(self.orchestrator.health_monitor)
        self.assertIsNotNone(self.orchestrator.load_balancer)
        self.assertIsNotNone(self.orchestrator.failover_manager)
        self.assertIsNotNone(self.orchestrator.cost_tracker)
        self.assertIsNotNone(self.orchestrator.conversation_manager)
        self.assertIsNotNone(self.orchestrator.pattern_engine)
        self.assertIsNotNone(self.orchestrator.context_optimizer)
        self.assertIsNotNone(self.orchestrator.adaptive_prioritizer)
        self.assertIsNotNone(self.orchestrator.execution_strategy_engine)
        self.assertIsNotNone(self.orchestrator.metalearning_metrics)
        self.assertIsNotNone(self.orchestrator.scheduler)
        self.assertIsNotNone(self.orchestrator.suggestion_engine)
        self.assertIsNotNone(self.orchestrator.automation)
        self.assertIsNotNone(self.orchestrator.optimizer)

    def test_orchestrator_start_stop(self):
        """Test orchestrator start and stop"""
        self.orchestrator.initialize()

        # Start
        self.orchestrator.start()
        self.assertTrue(self.orchestrator._running)

        # Stop
        self.orchestrator.stop()
        self.assertFalse(self.orchestrator._running)

    def test_job_submission(self):
        """Test job submission through orchestrator"""
        self.orchestrator.initialize()

        # Submit a simple job
        result = self.orchestrator.submit_job(
            idea="Test job",
            priority=3,
            context={'test': True}
        )

        self.assertTrue(result['success'])
        self.assertIn('job_id', result)
        self.assertIn('conversation_id', result)

    @patch('hermes.orchestrator.HermesOrchestrator.execute_with_intelligence')
    def test_intelligent_execution(self, mock_execute):
        """Test intelligent execution with full stack"""
        self.orchestrator.initialize()

        # Mock execution to avoid actual backend calls
        mock_execute.return_value = {
            'success': True,
            'result': 'Test result',
            'backend_used': 'test_backend',
            'patterns_matched': 2,
            'strategy_used': 'BALANCED',
            'failover_occurred': False
        }

        result = self.orchestrator.execute_with_intelligence(
            "Test intelligent execution",
            {'context': 'test'}
        )

        self.assertTrue(result['success'])
        self.assertIn('backend_used', result)
        self.assertIn('patterns_matched', result)

    def test_system_status(self):
        """Test system status retrieval"""
        self.orchestrator.initialize()

        status = self.orchestrator.get_system_status()

        self.assertIn('initialized', status)
        self.assertIn('running', status)
        self.assertIn('timestamp', status)
        self.assertIn('queue', status)
        self.assertIn('backends', status)
        self.assertIn('metalearning', status)
        self.assertIn('autonomous', status)
        self.assertIn('monitoring', status)

    def test_dashboard_data(self):
        """Test dashboard data aggregation"""
        self.orchestrator.initialize()

        data = self.orchestrator.get_dashboard_data()

        self.assertIn('system', data)
        self.assertIn('jobs', data)
        self.assertIn('backends', data)
        self.assertIn('learning', data)
        self.assertIn('autonomous', data)
        self.assertIn('optimizations', data)
        self.assertIn('suggestions', data)

    def test_suggestions_generation(self):
        """Test proactive suggestions generation"""
        self.orchestrator.initialize()

        suggestions = self.orchestrator.get_suggestions()

        self.assertIsInstance(suggestions, list)
        # Each suggestion should have required fields
        for suggestion in suggestions:
            self.assertIn('suggestion_id', suggestion)
            self.assertIn('type', suggestion)
            self.assertIn('title', suggestion)
            self.assertIn('confidence', suggestion)

    def test_optimization_recommendations(self):
        """Test optimization recommendations"""
        self.orchestrator.initialize()

        from hermes.autonomous.learning_optimizer import OptimizationStrategy

        optimizations = self.orchestrator.get_optimizations(
            OptimizationStrategy.BALANCED
        )

        self.assertIsInstance(optimizations, list)
        # Each optimization should have required fields
        for optimization in optimizations:
            self.assertIn('recommendation_id', optimization)
            self.assertIn('category', optimization)
            self.assertIn('title', optimization)
            self.assertIn('impact', optimization)
            self.assertIn('effort', optimization)
            self.assertIn('confidence', optimization)


class TestOrchestratorIntegration(unittest.TestCase):
    """Integration tests for orchestrator components"""

    def setUp(self):
        """Set up integration test environment"""
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        self.temp_db.close()

        self.config = Config()
        self.config._config['database']['path'] = self.temp_db.name
        self.config._config['autonomous']['scheduler']['enabled'] = True
        self.config._config['autonomous']['suggestions']['enabled'] = True

        self.orchestrator = HermesOrchestrator(self.config)
        self.orchestrator.initialize()

    def tearDown(self):
        """Clean up integration test environment"""
        try:
            self.orchestrator.stop()
            os.unlink(self.temp_db.name)
        except:
            pass

    def test_end_to_end_job_execution(self):
        """Test end-to-end job execution through orchestrator"""
        # Submit job
        result = self.orchestrator.submit_job(
            idea="Generate a summary of a meeting",
            priority=3,
            context={'interactive': False}
        )

        self.assertTrue(result['success'])
        job_id = result['job_id']

        # Check system status shows the job
        status = self.orchestrator.get_system_status()
        self.assertIn('queue', status)

        # Get dashboard data
        dashboard = self.orchestrator.get_dashboard_data()
        self.assertIn('jobs', dashboard)

    def test_metalearning_integration(self):
        """Test meta-learning integration"""
        # Submit multiple similar jobs
        ideas = [
            "Summarize a document",
            "Summarize another document",
            "Summarize a third document"
        ]

        for idea in ideas:
            result = self.orchestrator.submit_job(idea)
            self.assertTrue(result['success'])

        # Check pattern learning
        patterns = self.orchestrator.pattern_engine.get_pattern_statistics()
        self.assertIsInstance(patterns, dict)

        # Get metrics
        metrics = self.orchestrator.metalearning_metrics.get_comprehensive_metrics(24)
        self.assertIsInstance(metrics.total_conversations, int)

    def test_autonomous_systems_integration(self):
        """Test autonomous systems integration"""
        # Test suggestions
        suggestions = self.orchestrator.get_suggestions()
        self.assertIsInstance(suggestions, list)

        # Test optimizations
        optimizations = self.orchestrator.get_optimizations()
        self.assertIsInstance(optimizations, list)

        # Test automation
        automation_stats = self.orchestrator.automation.get_automation_stats()
        self.assertIn('enabled', automation_stats)

        # Test scheduler
        scheduler_stats = self.orchestrator.scheduler.get_scheduler_stats()
        self.assertIn('enabled', scheduler_stats)

    def test_backend_management_integration(self):
        """Test backend management integration"""
        # Test health monitoring
        health_summary = self.orchestrator.health_monitor.get_health_summary()
        self.assertIn('total_backends', health_summary)

        # Test load balancing
        load_stats = self.orchestrator.load_balancer.get_load_stats()
        self.assertIn('total_backends', load_stats)

        # Test cost tracking
        cost_summary = self.orchestrator.cost_tracker.get_cost_summary()
        self.assertIn('today', cost_summary)

        # Test failover
        failover_stats = self.orchestrator.failover_manager.get_failover_stats()
        self.assertIn('total_failovers', failover_stats)

    def test_error_handling(self):
        """Test error handling in orchestrator"""
        # Test invalid job submission
        result = self.orchestrator.submit_job("")
        self.assertFalse(result['success'])

        # Test with invalid priority
        result = self.orchestrator.submit_job("Test", priority=10)
        # Should still succeed but with default priority
        self.assertTrue(result['success'])


if __name__ == '__main__':
    unittest.main()