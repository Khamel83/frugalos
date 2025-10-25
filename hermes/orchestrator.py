"""
Unified Hermes Orchestrator
Integrates all Hermes systems into a cohesive whole
"""

import logging
import threading
from typing import Dict, Any, List, Optional
from datetime import datetime

from .config import Config
from .database import Database
from .logger import get_logger, setup_logger
from .queue import JobQueue

# Backend Management
from .backends.health_monitor import BackendHealthMonitor
from .backends.load_balancer import BackendLoadBalancer
from .backends.failover_manager import FailoverManager
from .backends.cost_tracker import BackendCostTracker

# Meta-Learning
from .metalearning.conversation_manager import ConversationManager
from .metalearning.pattern_engine import PatternEngine
from .metalearning.context_optimizer import ContextOptimizer
from .metalearning.adaptive_prioritizer import AdaptivePrioritizer
from .metalearning.execution_strategy import ExecutionStrategyEngine
from .metalearning.metrics import MetaLearningMetrics

# Autonomous Operations
from .autonomous.scheduler import AutonomousScheduler
from .autonomous.suggestion_engine import ProactiveSuggestionEngine
from .autonomous.context_automation import ContextAwareAutomation
from .autonomous.learning_optimizer import LearningBasedOptimizer, OptimizationStrategy

# Monitoring
from .monitoring import get_metrics_collector

logger = get_logger('orchestrator')

class HermesOrchestrator:
    """
    Unified orchestrator for all Hermes systems

    Coordinates:
    - Job queue and execution
    - Backend health and load balancing
    - Meta-learning and pattern recognition
    - Autonomous scheduling and optimization
    - Monitoring and metrics
    """

    def __init__(self, config: Optional[Config] = None):
        self.config = config or Config()
        self.db = Database()
        self.logger = setup_logger('hermes.orchestrator')

        self._initialized = False
        self._running = False

        # Core components
        self.job_queue = None

        # Backend management
        self.health_monitor = None
        self.load_balancer = None
        self.failover_manager = None
        self.cost_tracker = None

        # Meta-learning
        self.conversation_manager = None
        self.pattern_engine = None
        self.context_optimizer = None
        self.adaptive_prioritizer = None
        self.execution_strategy_engine = None
        self.metalearning_metrics = None

        # Autonomous operations
        self.scheduler = None
        self.suggestion_engine = None
        self.automation = None
        self.optimizer = None

        # Monitoring
        self.metrics_collector = None

    def initialize(self):
        """Initialize all Hermes systems"""
        if self._initialized:
            self.logger.warning("Orchestrator already initialized")
            return

        try:
            self.logger.info("Initializing Hermes Orchestrator...")

            # Initialize database
            self.db.initialize()

            # Initialize backend management
            self.logger.info("Initializing backend management...")
            self.health_monitor = BackendHealthMonitor(self.config)
            self.load_balancer = BackendLoadBalancer(self.health_monitor, self.config)
            self.failover_manager = FailoverManager(
                self.health_monitor,
                self.load_balancer,
                self.config
            )
            self.cost_tracker = BackendCostTracker(self.config)

            # Initialize meta-learning
            self.logger.info("Initializing meta-learning systems...")
            self.conversation_manager = ConversationManager(self.config)
            self.pattern_engine = PatternEngine(self.config)
            self.context_optimizer = ContextOptimizer(self.config)
            self.adaptive_prioritizer = AdaptivePrioritizer(self.config)
            self.execution_strategy_engine = ExecutionStrategyEngine(self.config)
            self.metalearning_metrics = MetaLearningMetrics(self.config)

            # Initialize autonomous operations
            self.logger.info("Initializing autonomous operations...")
            self.scheduler = AutonomousScheduler(self.config)
            self.suggestion_engine = ProactiveSuggestionEngine(self.config)
            self.automation = ContextAwareAutomation(self.config)
            self.optimizer = LearningBasedOptimizer(self.config)

            # Initialize monitoring
            self.logger.info("Initializing monitoring...")
            self.metrics_collector = get_metrics_collector(self.config)

            # Initialize job queue
            self.logger.info("Initializing job queue...")
            self.job_queue = JobQueue(self.config)

            self._initialized = True
            self.logger.info("✓ Hermes Orchestrator initialized successfully")

        except Exception as e:
            self.logger.error(f"Error initializing orchestrator: {e}")
            raise

    def start(self):
        """Start all Hermes systems"""
        if not self._initialized:
            self.initialize()

        if self._running:
            self.logger.warning("Orchestrator already running")
            return

        try:
            self.logger.info("Starting Hermes systems...")

            # Start backend monitoring
            self.health_monitor.start_monitoring()

            # Start job queue
            self.job_queue.start()

            # Start autonomous scheduler
            self.scheduler.start_scheduler()

            # Start metrics collection
            self.metrics_collector.start()

            self._running = True
            self.logger.info("✓ All Hermes systems started")

        except Exception as e:
            self.logger.error(f"Error starting orchestrator: {e}")
            raise

    def stop(self):
        """Stop all Hermes systems"""
        if not self._running:
            return

        try:
            self.logger.info("Stopping Hermes systems...")

            # Stop in reverse order
            if self.metrics_collector:
                self.metrics_collector.stop()

            if self.scheduler:
                self.scheduler.stop_scheduler()

            if self.job_queue:
                self.job_queue.stop()

            if self.health_monitor:
                self.health_monitor.stop_monitoring()

            self._running = False
            self.logger.info("✓ All Hermes systems stopped")

        except Exception as e:
            self.logger.error(f"Error stopping orchestrator: {e}")

    def submit_job(
        self,
        idea: str,
        priority: int = 3,
        context: Dict[str, Any] = None,
        interactive: bool = False
    ) -> Dict[str, Any]:
        """
        Submit a job with full orchestration

        Args:
            idea: Job description
            priority: Job priority (1-5)
            context: Additional context
            interactive: Whether to gather context interactively

        Returns:
            Job submission result
        """
        try:
            context = context or {}

            # Create conversation for meta-learning
            conversation_id = self.conversation_manager.create_conversation(-1, idea)

            # Check if we should gather more context
            if interactive and self.conversation_manager.should_gather_context(idea):
                questions = self.conversation_manager.start_context_gathering(
                    conversation_id,
                    idea
                )

                # In non-interactive mode, skip questions
                # In interactive mode, questions would be presented to user
                if not interactive:
                    questions = []

            # Get execution strategy recommendation
            strategy = self.execution_strategy_engine.determine_strategy(
                idea,
                context,
                constraints={
                    'max_cost_cents': self.cost_tracker.get_daily_budget_remaining()
                }
            )

            # Select optimal backend
            available_backends = strategy.backend_preference
            backend = self.load_balancer.select_backend(
                available_backends,
                strategy=self.load_balancer.default_strategy
            )

            # Create job
            job_id = self.db.create_job(idea)

            # Enqueue with strategy
            self.job_queue.enqueue_job(
                job_id,
                idea,
                priority=priority,
                backend_preference=backend,
                conversation_id=conversation_id,
                **context
            )

            self.logger.info(
                f"Job {job_id} submitted: {idea[:50]}... "
                f"(backend: {backend}, strategy: {strategy.mode.value})"
            )

            return {
                'success': True,
                'job_id': job_id,
                'conversation_id': conversation_id,
                'backend': backend,
                'strategy': strategy.mode.value,
                'estimated_cost_cents': strategy.estimated_cost_cents,
                'estimated_time_seconds': strategy.estimated_time_seconds
            }

        except Exception as e:
            self.logger.error(f"Error submitting job: {e}")
            return {
                'success': False,
                'error': str(e)
            }

    def get_system_status(self) -> Dict[str, Any]:
        """Get comprehensive system status"""
        try:
            return {
                'initialized': self._initialized,
                'running': self._running,
                'timestamp': datetime.now().isoformat(),

                # Job queue status
                'queue': self.job_queue.get_queue_status() if self.job_queue else {},

                # Backend health
                'backends': {
                    'health_summary': self.health_monitor.get_health_summary() if self.health_monitor else {},
                    'load_distribution': self.load_balancer.get_load_distribution() if self.load_balancer else {},
                    'failover_stats': self.failover_manager.get_failover_stats() if self.failover_manager else {},
                    'cost_summary': self.cost_tracker.get_cost_summary() if self.cost_tracker else {}
                },

                # Meta-learning
                'metalearning': {
                    'pattern_stats': self.pattern_engine.get_pattern_statistics() if self.pattern_engine else {},
                    'metrics_summary': self.metalearning_metrics.get_comprehensive_metrics(24).__dict__ if self.metalearning_metrics else {}
                },

                # Autonomous operations
                'autonomous': {
                    'scheduler_stats': self.scheduler.get_scheduler_stats() if self.scheduler else {},
                    'suggestion_stats': self.suggestion_engine.get_suggestion_stats() if self.suggestion_engine else {},
                    'automation_stats': self.automation.get_automation_stats() if self.automation else {},
                    'optimizer_stats': self.optimizer.get_optimizer_stats() if self.optimizer else {}
                },

                # Monitoring
                'monitoring': self.metrics_collector.get_current_metrics() if self.metrics_collector else {}
            }

        except Exception as e:
            self.logger.error(f"Error getting system status: {e}")
            return {'error': str(e)}

    def get_suggestions(self) -> List[Dict[str, Any]]:
        """Get proactive suggestions"""
        try:
            suggestions = self.suggestion_engine.generate_suggestions()

            return [
                {
                    'suggestion_id': s.suggestion_id,
                    'type': s.suggestion_type.value,
                    'title': s.title,
                    'description': s.description,
                    'confidence': s.confidence_score,
                    'priority': s.priority,
                    'rationale': s.rationale
                }
                for s in suggestions
            ]

        except Exception as e:
            self.logger.error(f"Error getting suggestions: {e}")
            return []

    def get_optimizations(self, strategy: OptimizationStrategy = OptimizationStrategy.BALANCED) -> List[Dict[str, Any]]:
        """Get optimization recommendations"""
        try:
            recommendations = self.optimizer.optimize(strategy)

            return [
                {
                    'recommendation_id': r.recommendation_id,
                    'category': r.category,
                    'title': r.title,
                    'description': r.description,
                    'impact': r.impact,
                    'effort': r.effort,
                    'estimated_savings': r.estimated_savings,
                    'confidence': r.confidence,
                    'rationale': r.rationale
                }
                for r in recommendations
            ]

        except Exception as e:
            self.logger.error(f"Error getting optimizations: {e}")
            return []

    def execute_with_intelligence(
        self,
        idea: str,
        context: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Execute job with full intelligence stack

        Uses all Hermes capabilities:
        - Pattern recognition
        - Intelligent backend selection
        - Automatic failover
        - Cost optimization
        - Meta-learning

        Args:
            idea: Job description
            context: Additional context

        Returns:
            Execution result
        """
        try:
            context = context or {}

            # Get matched patterns
            patterns = self.pattern_engine.recognize_patterns(idea, context)

            # Get execution strategy
            strategy = self.execution_strategy_engine.determine_strategy(
                idea,
                context,
                constraints={
                    'max_cost_cents': self.cost_tracker.get_daily_budget_remaining()
                }
            )

            # Get backend list with fallbacks
            backends = strategy.backend_preference

            # Execute with failover
            def execute_on_backend(backend_name: str) -> Any:
                """Execute on specific backend"""
                # This would call the actual backend
                # For now, return a mock result
                return {
                    'backend': backend_name,
                    'result': f"Executed on {backend_name}",
                    'success': True
                }

            result = self.failover_manager.execute_with_failover(
                backends,
                execute_on_backend,
                strategy=self.failover_manager.default_strategy,
                context=context
            )

            # Record cost if successful
            if result.get('success'):
                backend_used = result.get('backend_used')
                if backend_used:
                    # Estimate tokens (would be actual in production)
                    self.cost_tracker.record_request_cost(
                        backend_used,
                        input_tokens=100,
                        output_tokens=200
                    )

            # Learn from execution
            if patterns and result.get('success'):
                # Update pattern success
                self.logger.info("Learning from successful execution with patterns")

            return {
                'success': result.get('success', False),
                'result': result.get('result'),
                'backend_used': result.get('backend_used'),
                'patterns_matched': len(patterns),
                'strategy_used': strategy.mode.value,
                'failover_occurred': result.get('failover_occurred', False)
            }

        except Exception as e:
            self.logger.error(f"Error in intelligent execution: {e}")
            return {
                'success': False,
                'error': str(e)
            }

    def get_dashboard_data(self) -> Dict[str, Any]:
        """Get comprehensive dashboard data"""
        try:
            return {
                'system': {
                    'status': 'operational' if self._running else 'stopped',
                    'uptime_seconds': 0,  # Would track actual uptime
                    'version': '0.3.0'
                },
                'jobs': {
                    'queue_status': self.job_queue.get_queue_status() if self.job_queue else {},
                    'recent_jobs': self.db.get_recent_jobs(10)
                },
                'backends': {
                    'health': self.health_monitor.get_health_summary() if self.health_monitor else {},
                    'load': self.load_balancer.get_load_stats() if self.load_balancer else {},
                    'cost': self.cost_tracker.get_cost_summary() if self.cost_tracker else {}
                },
                'learning': {
                    'patterns': self.pattern_engine.get_pattern_statistics() if self.pattern_engine else {},
                    'metrics': self.metalearning_metrics.export_metrics_report(24) if self.metalearning_metrics else {},
                    'top_patterns': self.metalearning_metrics.get_top_patterns(5) if self.metalearning_metrics else []
                },
                'autonomous': {
                    'scheduled_tasks': len(self.scheduler.get_scheduled_tasks()) if self.scheduler else 0,
                    'active_suggestions': len(self.suggestion_engine.get_active_suggestions()) if self.suggestion_engine else 0,
                    'automation_rules': self.automation.get_automation_stats() if self.automation else {}
                },
                'optimizations': self.get_optimizations(OptimizationStrategy.BALANCED)[:3],
                'suggestions': self.get_suggestions()[:5]
            }

        except Exception as e:
            self.logger.error(f"Error getting dashboard data: {e}")
            return {'error': str(e)}

# Global orchestrator instance
_orchestrator_instance = None
_orchestrator_lock = threading.Lock()

def get_orchestrator(config: Optional[Config] = None) -> HermesOrchestrator:
    """Get global orchestrator instance (singleton)"""
    global _orchestrator_instance

    if _orchestrator_instance is None:
        with _orchestrator_lock:
            if _orchestrator_instance is None:
                _orchestrator_instance = HermesOrchestrator(config)

    return _orchestrator_instance
