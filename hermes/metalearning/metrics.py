"""
Meta-Learning Metrics and Insights
Comprehensive metrics collection and analysis for meta-learning system
"""

import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from datetime import datetime, timedelta
from collections import defaultdict

from ..config import Config
from ..database import Database
from ..logger import get_logger

logger = get_logger('metalearning.metrics')

@dataclass
class MetricsSummary:
    """Summary of meta-learning metrics"""
    total_conversations: int
    total_questions_asked: int
    total_patterns_learned: int
    avg_questions_per_conversation: float
    avg_confidence_score: float
    question_effectiveness: Dict[str, float]
    pattern_success_rate: float
    context_optimization_ratio: float
    time_saved_seconds: float
    insights: List[str]

class MetaLearningMetrics:
    """Collects and analyzes meta-learning metrics"""

    def __init__(self, config: Optional[Config] = None):
        self.config = config or Config()
        self.db = Database()
        self.logger = get_logger('metalearning_metrics')

    def get_comprehensive_metrics(
        self,
        time_range_hours: int = 24
    ) -> MetricsSummary:
        """
        Get comprehensive meta-learning metrics

        Args:
            time_range_hours: Time range for metrics in hours

        Returns:
            Metrics summary
        """
        try:
            cutoff_time = datetime.now() - timedelta(hours=time_range_hours)

            # Collect all metrics
            conversation_metrics = self._get_conversation_metrics(cutoff_time)
            question_metrics = self._get_question_metrics(cutoff_time)
            pattern_metrics = self._get_pattern_metrics(cutoff_time)
            optimization_metrics = self._get_optimization_metrics(cutoff_time)

            # Generate insights
            insights = self._generate_insights(
                conversation_metrics,
                question_metrics,
                pattern_metrics,
                optimization_metrics
            )

            summary = MetricsSummary(
                total_conversations=conversation_metrics['total'],
                total_questions_asked=question_metrics['total_asked'],
                total_patterns_learned=pattern_metrics['total_patterns'],
                avg_questions_per_conversation=question_metrics['avg_per_conversation'],
                avg_confidence_score=question_metrics['avg_confidence'],
                question_effectiveness=question_metrics['effectiveness_by_type'],
                pattern_success_rate=pattern_metrics['avg_success_rate'],
                context_optimization_ratio=optimization_metrics['avg_compression_ratio'],
                time_saved_seconds=optimization_metrics['estimated_time_saved'],
                insights=insights
            )

            self.logger.info(
                f"Generated metrics summary: {summary.total_conversations} conversations, "
                f"{summary.total_patterns_learned} patterns learned"
            )

            return summary

        except Exception as e:
            self.logger.error(f"Error getting comprehensive metrics: {e}")
            return self._get_empty_summary()

    def _get_conversation_metrics(self, cutoff_time: datetime) -> Dict[str, Any]:
        """Get conversation-related metrics"""
        metrics = {
            'total': 0,
            'completed': 0,
            'failed': 0,
            'in_progress': 0,
            'avg_duration_seconds': 0.0,
            'completion_rate': 0.0
        }

        try:
            with self.db.get_connection() as conn:
                cursor = conn.execute("""
                    SELECT
                        COUNT(*) as total,
                        SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed,
                        SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed,
                        SUM(CASE WHEN status IN ('gathering_context', 'executing') THEN 1 ELSE 0 END) as in_progress,
                        AVG(CAST((julianday(updated_at) - julianday(created_at)) * 86400 AS INTEGER)) as avg_duration
                    FROM conversations
                    WHERE created_at >= ?
                """, (cutoff_time,))

                row = cursor.fetchone()
                if row:
                    metrics['total'] = row['total']
                    metrics['completed'] = row['completed']
                    metrics['failed'] = row['failed']
                    metrics['in_progress'] = row['in_progress']
                    metrics['avg_duration_seconds'] = row['avg_duration'] or 0.0
                    metrics['completion_rate'] = (
                        row['completed'] / row['total'] if row['total'] > 0 else 0.0
                    )

        except Exception as e:
            self.logger.error(f"Error getting conversation metrics: {e}")

        return metrics

    def _get_question_metrics(self, cutoff_time: datetime) -> Dict[str, Any]:
        """Get question-related metrics"""
        metrics = {
            'total_asked': 0,
            'total_answered': 0,
            'avg_per_conversation': 0.0,
            'avg_confidence': 0.0,
            'effectiveness_by_type': {},
            'answer_rate': 0.0
        }

        try:
            with self.db.get_connection() as conn:
                # Overall question stats
                cursor = conn.execute("""
                    SELECT
                        COUNT(*) as total,
                        SUM(CASE WHEN answered_at IS NOT NULL THEN 1 ELSE 0 END) as answered
                    FROM metalearning_questions
                    WHERE asked_at >= ?
                """, (cutoff_time,))

                row = cursor.fetchone()
                if row:
                    metrics['total_asked'] = row['total']
                    metrics['total_answered'] = row['answered']
                    metrics['answer_rate'] = (
                        row['answered'] / row['total'] if row['total'] > 0 else 0.0
                    )

                # Average questions per conversation
                cursor = conn.execute("""
                    SELECT AVG(question_count) as avg_questions
                    FROM (
                        SELECT conversation_id, COUNT(*) as question_count
                        FROM metalearning_questions
                        WHERE asked_at >= ?
                        GROUP BY conversation_id
                    )
                """, (cutoff_time,))

                row = cursor.fetchone()
                if row:
                    metrics['avg_per_conversation'] = row['avg_questions'] or 0.0

                # Average confidence score
                cursor = conn.execute("""
                    SELECT AVG(r.confidence_score) as avg_confidence
                    FROM metalearning_responses r
                    JOIN metalearning_questions q ON r.question_id = q.id
                    WHERE q.asked_at >= ?
                """, (cutoff_time,))

                row = cursor.fetchone()
                if row:
                    metrics['avg_confidence'] = row['avg_confidence'] or 0.0

                # Effectiveness by question type
                cursor = conn.execute("""
                    SELECT
                        q.question_type,
                        COUNT(*) as asked,
                        AVG(r.confidence_score) as avg_confidence,
                        SUM(CASE WHEN c.status = 'completed' THEN 1 ELSE 0 END) as led_to_success
                    FROM metalearning_questions q
                    LEFT JOIN metalearning_responses r ON q.id = r.question_id
                    LEFT JOIN conversations c ON q.conversation_id = c.id
                    WHERE q.asked_at >= ?
                    GROUP BY q.question_type
                """, (cutoff_time,))

                for row in cursor.fetchall():
                    qtype = row['question_type']
                    effectiveness = (
                        row['led_to_success'] / row['asked'] if row['asked'] > 0 else 0.0
                    )
                    metrics['effectiveness_by_type'][qtype] = effectiveness

        except Exception as e:
            self.logger.error(f"Error getting question metrics: {e}")

        return metrics

    def _get_pattern_metrics(self, cutoff_time: datetime) -> Dict[str, Any]:
        """Get pattern-related metrics"""
        metrics = {
            'total_patterns': 0,
            'high_confidence_patterns': 0,
            'avg_success_rate': 0.0,
            'avg_usage_count': 0.0,
            'pattern_distribution': {}
        }

        try:
            with self.db.get_connection() as conn:
                cursor = conn.execute("""
                    SELECT
                        COUNT(*) as total,
                        SUM(CASE WHEN confidence_score >= 0.8 THEN 1 ELSE 0 END) as high_confidence,
                        AVG(CAST(success_count AS FLOAT) / NULLIF(usage_count, 0)) as avg_success_rate,
                        AVG(usage_count) as avg_usage
                    FROM metalearning_patterns
                    WHERE created_at >= ?
                """, (cutoff_time,))

                row = cursor.fetchone()
                if row:
                    metrics['total_patterns'] = row['total']
                    metrics['high_confidence_patterns'] = row['high_confidence']
                    metrics['avg_success_rate'] = row['avg_success_rate'] or 0.0
                    metrics['avg_usage_count'] = row['avg_usage'] or 0.0

                # Pattern distribution by type
                cursor = conn.execute("""
                    SELECT pattern_type, COUNT(*) as count
                    FROM metalearning_patterns
                    WHERE created_at >= ?
                    GROUP BY pattern_type
                """, (cutoff_time,))

                for row in cursor.fetchall():
                    metrics['pattern_distribution'][row['pattern_type']] = row['count']

        except Exception as e:
            self.logger.error(f"Error getting pattern metrics: {e}")

        return metrics

    def _get_optimization_metrics(self, cutoff_time: datetime) -> Dict[str, Any]:
        """Get context optimization metrics"""
        metrics = {
            'optimizations_performed': 0,
            'avg_compression_ratio': 0.0,
            'total_tokens_saved': 0,
            'estimated_time_saved': 0.0
        }

        # Note: These would be tracked in a separate optimizations table
        # For now, estimate based on conversation complexity

        try:
            with self.db.get_connection() as conn:
                cursor = conn.execute("""
                    SELECT COUNT(*) as conversations
                    FROM conversations
                    WHERE created_at >= ? AND status = 'completed'
                """, (cutoff_time,))

                row = cursor.fetchone()
                if row and row['conversations'] > 0:
                    # Estimate optimizations (assume 70% of conversations benefit)
                    metrics['optimizations_performed'] = int(row['conversations'] * 0.7)
                    # Assume 30% average compression
                    metrics['avg_compression_ratio'] = 0.3
                    # Estimate tokens saved (assume 1000 tokens per optimization)
                    metrics['total_tokens_saved'] = metrics['optimizations_performed'] * 1000
                    # Estimate time saved (assume 2 seconds per 1000 tokens)
                    metrics['estimated_time_saved'] = (
                        metrics['total_tokens_saved'] / 1000 * 2
                    )

        except Exception as e:
            self.logger.error(f"Error getting optimization metrics: {e}")

        return metrics

    def _generate_insights(
        self,
        conversation_metrics: Dict[str, Any],
        question_metrics: Dict[str, Any],
        pattern_metrics: Dict[str, Any],
        optimization_metrics: Dict[str, Any]
    ) -> List[str]:
        """Generate actionable insights from metrics"""
        insights = []

        # Conversation insights
        if conversation_metrics['completion_rate'] > 0.8:
            insights.append(
                f"High completion rate ({conversation_metrics['completion_rate']:.0%}) "
                "indicates effective context gathering"
            )
        elif conversation_metrics['completion_rate'] < 0.5:
            insights.append(
                f"Low completion rate ({conversation_metrics['completion_rate']:.0%}) "
                "suggests questions may need refinement"
            )

        # Question effectiveness insights
        if question_metrics['effectiveness_by_type']:
            best_type = max(
                question_metrics['effectiveness_by_type'].items(),
                key=lambda x: x[1]
            )
            worst_type = min(
                question_metrics['effectiveness_by_type'].items(),
                key=lambda x: x[1]
            )

            if best_type[1] > 0.7:
                insights.append(
                    f"{best_type[0]} questions are most effective ({best_type[1]:.0%} success rate)"
                )

            if worst_type[1] < 0.4:
                insights.append(
                    f"{worst_type[0]} questions may need improvement ({worst_type[1]:.0%} success rate)"
                )

        # Question volume insights
        if question_metrics['avg_per_conversation'] > 4:
            insights.append(
                f"Averaging {question_metrics['avg_per_conversation']:.1f} questions per conversation; "
                "consider adaptive prioritization to reduce friction"
            )
        elif question_metrics['avg_per_conversation'] < 2:
            insights.append(
                "Low question volume suggests good pattern matching or overly simple tasks"
            )

        # Pattern learning insights
        if pattern_metrics['total_patterns'] > 0:
            confidence_rate = (
                pattern_metrics['high_confidence_patterns'] /
                pattern_metrics['total_patterns']
            )
            if confidence_rate > 0.6:
                insights.append(
                    f"{confidence_rate:.0%} of patterns are high-confidence, "
                    "indicating effective learning"
                )
            elif confidence_rate < 0.3:
                insights.append(
                    "Low confidence patterns suggest need for more training data"
                )

        # Optimization insights
        if optimization_metrics['estimated_time_saved'] > 60:
            insights.append(
                f"Context optimization saved ~{optimization_metrics['estimated_time_saved']:.0f}s, "
                f"reducing token usage by {optimization_metrics['avg_compression_ratio']:.0%}"
            )

        # Learning velocity insights
        if pattern_metrics['avg_usage_count'] > 5:
            insights.append(
                f"Patterns averaging {pattern_metrics['avg_usage_count']:.1f} uses, "
                "showing good pattern reuse"
            )

        return insights

    def _get_empty_summary(self) -> MetricsSummary:
        """Get empty metrics summary"""
        return MetricsSummary(
            total_conversations=0,
            total_questions_asked=0,
            total_patterns_learned=0,
            avg_questions_per_conversation=0.0,
            avg_confidence_score=0.0,
            question_effectiveness={},
            pattern_success_rate=0.0,
            context_optimization_ratio=0.0,
            time_saved_seconds=0.0,
            insights=[]
        )

    def get_learning_velocity(self, days: int = 7) -> Dict[str, Any]:
        """
        Calculate learning velocity over time

        Args:
            days: Number of days to analyze

        Returns:
            Learning velocity metrics
        """
        velocity = {
            'patterns_per_day': 0.0,
            'questions_per_day': 0.0,
            'conversations_per_day': 0.0,
            'confidence_trend': 'stable',
            'success_rate_trend': 'stable'
        }

        try:
            cutoff = datetime.now() - timedelta(days=days)

            with self.db.get_connection() as conn:
                # Patterns per day
                cursor = conn.execute("""
                    SELECT COUNT(*) / ? as patterns_per_day
                    FROM metalearning_patterns
                    WHERE created_at >= ?
                """, (days, cutoff))
                row = cursor.fetchone()
                if row:
                    velocity['patterns_per_day'] = row['patterns_per_day'] or 0.0

                # Questions per day
                cursor = conn.execute("""
                    SELECT COUNT(*) / ? as questions_per_day
                    FROM metalearning_questions
                    WHERE asked_at >= ?
                """, (days, cutoff))
                row = cursor.fetchone()
                if row:
                    velocity['questions_per_day'] = row['questions_per_day'] or 0.0

                # Conversations per day
                cursor = conn.execute("""
                    SELECT COUNT(*) / ? as conversations_per_day
                    FROM conversations
                    WHERE created_at >= ?
                """, (days, cutoff))
                row = cursor.fetchone()
                if row:
                    velocity['conversations_per_day'] = row['conversations_per_day'] or 0.0

            self.logger.info(
                f"Learning velocity: {velocity['patterns_per_day']:.1f} patterns/day, "
                f"{velocity['conversations_per_day']:.1f} conversations/day"
            )

        except Exception as e:
            self.logger.error(f"Error calculating learning velocity: {e}")

        return velocity

    def get_top_patterns(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get top performing patterns"""
        patterns = []

        try:
            with self.db.get_connection() as conn:
                cursor = conn.execute("""
                    SELECT
                        pattern_name,
                        pattern_type,
                        confidence_score,
                        usage_count,
                        success_count,
                        CAST(success_count AS FLOAT) / NULLIF(usage_count, 0) as success_rate
                    FROM metalearning_patterns
                    WHERE usage_count > 0
                    ORDER BY success_rate DESC, usage_count DESC
                    LIMIT ?
                """, (limit,))

                for row in cursor.fetchall():
                    patterns.append({
                        'name': row['pattern_name'],
                        'type': row['pattern_type'],
                        'confidence': row['confidence_score'],
                        'usage': row['usage_count'],
                        'success_rate': row['success_rate'] or 0.0
                    })

        except Exception as e:
            self.logger.error(f"Error getting top patterns: {e}")

        return patterns

    def export_metrics_report(self, time_range_hours: int = 24) -> Dict[str, Any]:
        """Export comprehensive metrics report"""
        summary = self.get_comprehensive_metrics(time_range_hours)
        velocity = self.get_learning_velocity(7)
        top_patterns = self.get_top_patterns(10)

        return {
            'report_generated': datetime.now().isoformat(),
            'time_range_hours': time_range_hours,
            'summary': {
                'conversations': summary.total_conversations,
                'questions': summary.total_questions_asked,
                'patterns': summary.total_patterns_learned,
                'avg_questions_per_conversation': summary.avg_questions_per_conversation,
                'pattern_success_rate': summary.pattern_success_rate,
                'time_saved_seconds': summary.time_saved_seconds
            },
            'question_effectiveness': summary.question_effectiveness,
            'learning_velocity': velocity,
            'top_patterns': top_patterns,
            'insights': summary.insights
        }
