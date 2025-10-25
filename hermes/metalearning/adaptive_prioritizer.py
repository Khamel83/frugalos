"""
Adaptive Question Prioritization
Dynamically prioritizes questions based on conversation context and learned patterns
"""

import logging
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime
from collections import defaultdict

from ..config import Config
from ..database import Database
from ..logger import get_logger

logger = get_logger('metalearning.adaptive_prioritizer')

@dataclass
class PrioritizedQuestion:
    """Question with dynamic priority score"""
    question_id: str
    question_text: str
    question_type: str
    base_priority: int
    dynamic_priority: float
    skip_likelihood: float
    reasoning: str
    metadata: Dict[str, Any]

class AdaptivePrioritizer:
    """Adaptively prioritizes questions based on context and patterns"""

    def __init__(self, config: Optional[Config] = None):
        self.config = config or Config()
        self.db = Database()
        self.logger = get_logger('adaptive_prioritizer')

        # Load historical question effectiveness
        self._question_effectiveness = self._load_effectiveness_data()

    def _load_effectiveness_data(self) -> Dict[str, Dict[str, Any]]:
        """Load historical data on question effectiveness"""
        effectiveness = defaultdict(lambda: {
            'asked_count': 0,
            'led_to_success': 0,
            'avg_answer_quality': 0.5,
            'avg_execution_time_improvement': 0.0
        })

        try:
            with self.db.get_connection() as conn:
                cursor = conn.execute("""
                    SELECT
                        q.question_type,
                        COUNT(*) as asked_count,
                        AVG(r.confidence_score) as avg_confidence,
                        SUM(CASE WHEN c.status = 'completed' THEN 1 ELSE 0 END) as success_count
                    FROM metalearning_questions q
                    LEFT JOIN metalearning_responses r ON q.id = r.question_id
                    LEFT JOIN conversations c ON q.conversation_id = c.id
                    GROUP BY q.question_type
                """)

                for row in cursor.fetchall():
                    qtype = row['question_type']
                    effectiveness[qtype] = {
                        'asked_count': row['asked_count'],
                        'led_to_success': row['success_count'],
                        'avg_answer_quality': row['avg_confidence'] or 0.5,
                        'success_rate': row['success_count'] / max(row['asked_count'], 1)
                    }

            self.logger.info(f"Loaded effectiveness data for {len(effectiveness)} question types")

        except Exception as e:
            self.logger.error(f"Error loading effectiveness data: {e}")

        return effectiveness

    def prioritize_questions(
        self,
        questions: List[Dict[str, Any]],
        conversation_id: int,
        idea: str
    ) -> List[PrioritizedQuestion]:
        """
        Adaptively prioritize questions based on context

        Args:
            questions: List of questions to prioritize
            conversation_id: Current conversation ID
            idea: User's idea

        Returns:
            List of prioritized questions
        """
        try:
            # Get conversation context
            context = self._get_conversation_context(conversation_id, idea)

            prioritized = []

            for question in questions:
                # Calculate dynamic priority
                dynamic_priority = self._calculate_dynamic_priority(
                    question,
                    context
                )

                # Calculate skip likelihood
                skip_likelihood = self._calculate_skip_likelihood(
                    question,
                    context
                )

                # Generate reasoning
                reasoning = self._generate_reasoning(
                    question,
                    dynamic_priority,
                    skip_likelihood,
                    context
                )

                prioritized_q = PrioritizedQuestion(
                    question_id=question.get('question_id', f"q_{len(prioritized)}"),
                    question_text=question.get('question_text', question.get('text', '')),
                    question_type=question.get('question_type', 'clarification'),
                    base_priority=question.get('priority', 5),
                    dynamic_priority=dynamic_priority,
                    skip_likelihood=skip_likelihood,
                    reasoning=reasoning,
                    metadata=question
                )

                prioritized.append(prioritized_q)

            # Sort by dynamic priority (higher = more important)
            prioritized.sort(key=lambda q: q.dynamic_priority, reverse=True)

            self.logger.info(f"Prioritized {len(prioritized)} questions for conversation {conversation_id}")

            return prioritized

        except Exception as e:
            self.logger.error(f"Error prioritizing questions: {e}")
            return []

    def _get_conversation_context(self, conversation_id: int, idea: str) -> Dict[str, Any]:
        """Get context about the conversation"""
        context = {
            'idea': idea,
            'idea_length': len(idea.split()),
            'idea_specificity': self._calculate_specificity(idea),
            'conversation_id': conversation_id,
            'message_count': 0,
            'answered_questions': 0,
            'idea_category': self._categorize_idea(idea)
        }

        try:
            with self.db.get_connection() as conn:
                # Count messages
                cursor = conn.execute("""
                    SELECT COUNT(*) as count FROM conversation_messages
                    WHERE conversation_id = ?
                """, (conversation_id,))
                row = cursor.fetchone()
                context['message_count'] = row['count'] if row else 0

                # Count answered questions
                cursor = conn.execute("""
                    SELECT COUNT(*) as count FROM metalearning_questions
                    WHERE conversation_id = ? AND answered_at IS NOT NULL
                """, (conversation_id,))
                row = cursor.fetchone()
                context['answered_questions'] = row['count'] if row else 0

        except Exception as e:
            self.logger.error(f"Error getting conversation context: {e}")

        return context

    def _calculate_specificity(self, idea: str) -> float:
        """Calculate how specific an idea is (0-1)"""
        specific_terms = ['must', 'should', 'exactly', 'specifically', 'particular', 'precise']
        vague_terms = ['something', 'anything', 'maybe', 'probably', 'some', 'any']

        specific_count = sum(1 for term in specific_terms if term in idea.lower())
        vague_count = sum(1 for term in vague_terms if term in idea.lower())

        word_count = len(idea.split())
        length_score = min(word_count / 50, 1.0)
        term_score = (specific_count * 0.2) - (vague_count * 0.2)

        return max(0.0, min(1.0, length_score + term_score))

    def _categorize_idea(self, idea: str) -> str:
        """Categorize the idea"""
        idea_lower = idea.lower()

        categories = {
            'technical': ['code', 'script', 'program', 'function', 'api', 'algorithm'],
            'data': ['analyze', 'process', 'parse', 'extract', 'transform', 'data'],
            'creative': ['write', 'create', 'generate', 'design', 'compose'],
            'analysis': ['analyze', 'evaluate', 'assess', 'compare', 'review']
        }

        for category, keywords in categories.items():
            if any(kw in idea_lower for kw in keywords):
                return category

        return 'general'

    def _calculate_dynamic_priority(
        self,
        question: Dict[str, Any],
        context: Dict[str, Any]
    ) -> float:
        """Calculate dynamic priority score for a question"""
        # Base priority (from question template)
        base = question.get('priority', 5) / 10.0  # Normalize to 0-1

        # Historical effectiveness
        qtype = question.get('question_type', 'clarification')
        effectiveness = self._question_effectiveness.get(qtype, {})
        effectiveness_score = effectiveness.get('success_rate', 0.5)

        # Context relevance
        relevance_score = self._calculate_relevance(question, context)

        # Urgency (based on idea specificity - less specific = more urgent questions)
        urgency_score = 1.0 - context.get('idea_specificity', 0.5)

        # Novelty (new question types get higher priority for exploration)
        novelty_score = self._calculate_novelty(qtype)

        # Weighted combination
        dynamic_priority = (
            base * 0.25 +
            effectiveness_score * 0.25 +
            relevance_score * 0.30 +
            urgency_score * 0.15 +
            novelty_score * 0.05
        )

        return max(0.0, min(1.0, dynamic_priority))

    def _calculate_relevance(
        self,
        question: Dict[str, Any],
        context: Dict[str, Any]
    ) -> float:
        """Calculate how relevant a question is to the current context"""
        qtype = question.get('question_type', 'clarification')
        category = context.get('idea_category', 'general')

        # Category-specific relevance
        relevance_map = {
            'technical': {
                'preference': 0.9,  # Tech stack, standards
                'validation': 0.8,  # Input/output
                'constraint': 0.6,
                'clarification': 0.7,
                'context': 0.5,
                'scope': 0.6
            },
            'data': {
                'validation': 0.9,  # Data quality
                'context': 0.8,     # Data format
                'clarification': 0.7,
                'constraint': 0.6,
                'preference': 0.5,
                'scope': 0.7
            },
            'creative': {
                'preference': 0.9,  # Style, tone
                'context': 0.8,     # Audience, purpose
                'constraint': 0.7,  # Length, format
                'clarification': 0.6,
                'validation': 0.4,
                'scope': 0.5
            },
            'general': {
                'clarification': 0.9,
                'context': 0.8,
                'scope': 0.7,
                'constraint': 0.6,
                'preference': 0.5,
                'validation': 0.5
            }
        }

        return relevance_map.get(category, relevance_map['general']).get(qtype, 0.5)

    def _calculate_novelty(self, question_type: str) -> float:
        """Calculate novelty score (encourage exploration of new question types)"""
        effectiveness = self._question_effectiveness.get(question_type, {})
        asked_count = effectiveness.get('asked_count', 0)

        # Higher novelty for less-asked questions
        if asked_count == 0:
            return 0.8  # High novelty
        elif asked_count < 5:
            return 0.6  # Moderate novelty
        elif asked_count < 20:
            return 0.4  # Low novelty
        else:
            return 0.2  # Well-explored

    def _calculate_skip_likelihood(
        self,
        question: Dict[str, Any],
        context: Dict[str, Any]
    ) -> float:
        """Calculate likelihood this question can be skipped"""
        # Required questions can't be skipped
        if question.get('required', False):
            return 0.0

        # If idea is very specific, can skip more questions
        specificity = context.get('idea_specificity', 0.5)
        if specificity > 0.8:
            return 0.7

        # If many questions already answered, can skip additional ones
        answered = context.get('answered_questions', 0)
        if answered >= 3:
            return 0.6

        # If question type has low effectiveness, higher skip likelihood
        qtype = question.get('question_type', 'clarification')
        effectiveness = self._question_effectiveness.get(qtype, {})
        success_rate = effectiveness.get('success_rate', 0.5)
        if success_rate < 0.3:
            return 0.5

        # Default: low skip likelihood
        return 0.2

    def _generate_reasoning(
        self,
        question: Dict[str, Any],
        priority: float,
        skip_likelihood: float,
        context: Dict[str, Any]
    ) -> str:
        """Generate human-readable reasoning for priority decision"""
        reasons = []

        # Priority reasoning
        if priority > 0.8:
            reasons.append("High priority - critical for understanding")
        elif priority > 0.6:
            reasons.append("Medium-high priority - important context")
        elif priority > 0.4:
            reasons.append("Medium priority - useful information")
        else:
            reasons.append("Low priority - optional details")

        # Skip reasoning
        if skip_likelihood > 0.6:
            reasons.append("can likely be skipped")
        elif skip_likelihood > 0.3:
            reasons.append("potentially skippable")

        # Context-specific reasons
        if context.get('idea_specificity', 0) > 0.7:
            reasons.append("idea already fairly specific")

        if context.get('answered_questions', 0) >= 2:
            reasons.append("sufficient context already gathered")

        # Question type effectiveness
        qtype = question.get('question_type', 'clarification')
        effectiveness = self._question_effectiveness.get(qtype, {})
        success_rate = effectiveness.get('success_rate', 0.5)
        if success_rate > 0.7:
            reasons.append(f"{qtype} questions historically effective")
        elif success_rate < 0.3:
            reasons.append(f"{qtype} questions have lower success rate")

        return "; ".join(reasons)

    def suggest_question_subset(
        self,
        prioritized_questions: List[PrioritizedQuestion],
        max_questions: int = 3
    ) -> Tuple[List[PrioritizedQuestion], List[PrioritizedQuestion]]:
        """
        Suggest which questions to ask vs skip

        Args:
            prioritized_questions: List of prioritized questions
            max_questions: Maximum questions to ask

        Returns:
            Tuple of (questions_to_ask, questions_to_skip)
        """
        to_ask = []
        to_skip = []

        for question in prioritized_questions:
            # Always ask required questions
            if question.metadata.get('required', False):
                to_ask.append(question)
                continue

            # Skip if high skip likelihood and we have enough questions
            if question.skip_likelihood > 0.6 and len(to_ask) >= max_questions:
                to_skip.append(question)
                continue

            # Ask if high priority and under limit
            if question.dynamic_priority > 0.5 and len(to_ask) < max_questions:
                to_ask.append(question)
            else:
                to_skip.append(question)

        self.logger.info(
            f"Suggested {len(to_ask)} questions to ask, {len(to_skip)} to skip"
        )

        return to_ask, to_skip

    def update_effectiveness(
        self,
        question_type: str,
        led_to_success: bool,
        answer_quality: float
    ):
        """Update effectiveness data based on outcomes"""
        try:
            current = self._question_effectiveness[question_type]
            current['asked_count'] += 1

            if led_to_success:
                current['led_to_success'] += 1

            # Update average answer quality with exponential moving average
            alpha = 0.2  # Learning rate
            current['avg_answer_quality'] = (
                (1 - alpha) * current['avg_answer_quality'] +
                alpha * answer_quality
            )

            # Update success rate
            current['success_rate'] = (
                current['led_to_success'] / current['asked_count']
            )

            self.logger.debug(f"Updated effectiveness for {question_type}")

        except Exception as e:
            self.logger.error(f"Error updating effectiveness: {e}")

    def get_prioritization_stats(self) -> Dict[str, Any]:
        """Get statistics about question prioritization"""
        return {
            'question_types_tracked': len(self._question_effectiveness),
            'effectiveness_data': {
                qtype: {
                    'asked_count': data['asked_count'],
                    'success_rate': data.get('success_rate', 0.0),
                    'avg_quality': data['avg_answer_quality']
                }
                for qtype, data in sorted(
                    self._question_effectiveness.items(),
                    key=lambda x: x[1].get('success_rate', 0),
                    reverse=True
                )
            }
        }
