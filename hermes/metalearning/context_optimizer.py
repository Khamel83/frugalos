"""
Meta-Learning Context Optimizer
Optimizes conversation context for token efficiency while maintaining quality
"""

import logging
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime

from ..config import Config
from ..database import Database
from ..logger import get_logger

logger = get_logger('metalearning.context_optimizer')

@dataclass
class ContextSegment:
    """A segment of context with metadata"""
    segment_id: str
    content: str
    segment_type: str  # 'question', 'answer', 'system', 'result'
    importance_score: float
    token_count: int
    timestamp: datetime
    metadata: Dict[str, Any]

class ContextOptimizer:
    """Optimizes conversation context for efficient token usage"""

    def __init__(self, config: Optional[Config] = None):
        self.config = config or Config()
        self.db = Database()
        self.max_tokens = self.config.get('metalearning.max_context_tokens', 4000)
        self.min_importance = self.config.get('metalearning.min_importance', 0.3)
        self.logger = get_logger('context_optimizer')

    def optimize_context(
        self,
        conversation_id: int,
        target_tokens: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Optimize conversation context for token efficiency

        Args:
            conversation_id: Conversation ID
            target_tokens: Target token count (uses max_tokens if not specified)

        Returns:
            Optimized context dictionary
        """
        target = target_tokens or self.max_tokens

        try:
            # Get all context segments
            segments = self._get_context_segments(conversation_id)

            # Calculate importance scores
            scored_segments = self._score_segments(segments, conversation_id)

            # Select segments within token budget
            selected_segments = self._select_segments(scored_segments, target)

            # Build optimized context
            optimized_context = self._build_context(selected_segments)

            # Add metadata
            optimized_context['optimization_stats'] = {
                'original_segments': len(segments),
                'selected_segments': len(selected_segments),
                'original_tokens': sum(s.token_count for s in segments),
                'optimized_tokens': sum(s.token_count for s in selected_segments),
                'compression_ratio': self._calculate_compression_ratio(segments, selected_segments),
                'avg_importance': sum(s.importance_score for s in selected_segments) / len(selected_segments) if selected_segments else 0
            }

            self.logger.info(
                f"Optimized context for conversation {conversation_id}: "
                f"{optimized_context['optimization_stats']['original_tokens']} → "
                f"{optimized_context['optimization_stats']['optimized_tokens']} tokens "
                f"({optimized_context['optimization_stats']['compression_ratio']:.1%} compression)"
            )

            return optimized_context

        except Exception as e:
            self.logger.error(f"Error optimizing context: {e}")
            return {'error': str(e)}

    def _get_context_segments(self, conversation_id: int) -> List[ContextSegment]:
        """Get all context segments from conversation"""
        segments = []

        try:
            with self.db.get_connection() as conn:
                # Get conversation messages
                cursor = conn.execute("""
                    SELECT * FROM conversation_messages
                    WHERE conversation_id = ?
                    ORDER BY created_at
                """, (conversation_id,))

                for row in cursor.fetchall():
                    segment = ContextSegment(
                        segment_id=f"msg_{row['id']}",
                        content=row['content'],
                        segment_type=row['message_type'],
                        importance_score=0.5,  # Will be calculated later
                        token_count=self._estimate_tokens(row['content']),
                        timestamp=row['created_at'],
                        metadata={'message_id': row['id']}
                    )
                    segments.append(segment)

                # Get questions and answers
                cursor = conn.execute("""
                    SELECT q.*, r.response_text
                    FROM metalearning_questions q
                    LEFT JOIN metalearning_responses r ON q.id = r.question_id
                    WHERE q.conversation_id = ?
                    ORDER BY q.asked_at
                """, (conversation_id,))

                for row in cursor.fetchall():
                    # Question segment
                    segments.append(ContextSegment(
                        segment_id=f"q_{row['id']}",
                        content=row['question_text'],
                        segment_type='question',
                        importance_score=0.7,  # Questions are important
                        token_count=self._estimate_tokens(row['question_text']),
                        timestamp=row['asked_at'],
                        metadata={'question_id': row['id'], 'type': row['question_type']}
                    ))

                    # Answer segment
                    if row['response_text']:
                        segments.append(ContextSegment(
                            segment_id=f"a_{row['id']}",
                            content=row['response_text'],
                            segment_type='answer',
                            importance_score=0.8,  # Answers are very important
                            token_count=self._estimate_tokens(row['response_text']),
                            timestamp=row['answered_at'] if row['answered_at'] else row['asked_at'],
                            metadata={'question_id': row['id']}
                        ))

            return segments

        except Exception as e:
            self.logger.error(f"Error getting context segments: {e}")
            return []

    def _estimate_tokens(self, text: str) -> int:
        """Estimate token count for text (rough approximation)"""
        # Simple approximation: ~4 characters per token
        return max(1, len(text) // 4)

    def _score_segments(
        self,
        segments: List[ContextSegment],
        conversation_id: int
    ) -> List[ContextSegment]:
        """Calculate importance scores for segments"""
        scored_segments = []

        for segment in segments:
            # Base score from segment type
            base_score = {
                'user': 0.9,  # User messages are very important
                'answer': 0.8,  # Answers are important
                'question': 0.7,  # Questions provide context
                'assistant': 0.6,  # Assistant messages
                'system': 0.4   # System messages less critical
            }.get(segment.segment_type, 0.5)

            # Recency bonus (more recent = more important)
            recency_score = self._calculate_recency_score(segment.timestamp)

            # Length penalty (very long segments get penalized)
            length_penalty = self._calculate_length_penalty(segment.token_count)

            # Content quality score
            quality_score = self._calculate_quality_score(segment.content)

            # Combined importance score
            importance = (
                base_score * 0.4 +
                recency_score * 0.2 +
                quality_score * 0.3 +
                length_penalty * 0.1
            )

            segment.importance_score = max(0.0, min(1.0, importance))
            scored_segments.append(segment)

        return scored_segments

    def _calculate_recency_score(self, timestamp: datetime) -> float:
        """Calculate recency score (0-1)"""
        try:
            if isinstance(timestamp, str):
                timestamp = datetime.fromisoformat(timestamp)

            age_seconds = (datetime.now() - timestamp).total_seconds()
            # Exponential decay: half-life of 1 hour
            return max(0.2, min(1.0, 2 ** (-age_seconds / 3600)))

        except Exception:
            return 0.5

    def _calculate_length_penalty(self, token_count: int) -> float:
        """Calculate length penalty (penalize very long segments)"""
        if token_count < 100:
            return 1.0
        elif token_count < 500:
            return 0.9
        elif token_count < 1000:
            return 0.7
        else:
            return 0.5

    def _calculate_quality_score(self, content: str) -> float:
        """Calculate content quality score"""
        # Longer, more detailed content scores higher
        word_count = len(content.split())

        if word_count < 3:
            return 0.3  # Very short
        elif word_count < 10:
            return 0.6  # Short
        elif word_count < 50:
            return 0.9  # Good detail
        else:
            return 1.0  # Very detailed

    def _select_segments(
        self,
        segments: List[ContextSegment],
        target_tokens: int
    ) -> List[ContextSegment]:
        """Select segments within token budget"""
        # Sort by importance
        sorted_segments = sorted(segments, key=lambda s: s.importance_score, reverse=True)

        selected = []
        current_tokens = 0

        # Always include the most important segments first
        for segment in sorted_segments:
            if segment.importance_score < self.min_importance:
                continue

            if current_tokens + segment.token_count <= target_tokens:
                selected.append(segment)
                current_tokens += segment.token_count
            else:
                # Try to fit smaller segments
                if segment.token_count < target_tokens * 0.1:  # Small segment
                    if current_tokens + segment.token_count <= target_tokens * 1.1:  # 10% overflow allowed
                        selected.append(segment)
                        current_tokens += segment.token_count

        # Sort back to chronological order
        selected.sort(key=lambda s: s.timestamp)

        return selected

    def _build_context(self, segments: List[ContextSegment]) -> Dict[str, Any]:
        """Build context dictionary from selected segments"""
        context = {
            'segments': [],
            'summary': '',
            'key_points': [],
            'questions_and_answers': []
        }

        key_points = []

        for segment in segments:
            context['segments'].append({
                'type': segment.segment_type,
                'content': segment.content,
                'importance': segment.importance_score,
                'timestamp': str(segment.timestamp)
            })

            # Extract key points from high-importance segments
            if segment.importance_score >= 0.7:
                key_points.append(segment.content[:200])  # First 200 chars

            # Group questions with answers
            if segment.segment_type in ['question', 'answer']:
                context['questions_and_answers'].append({
                    'type': segment.segment_type,
                    'content': segment.content
                })

        # Create summary from key points
        context['summary'] = self._create_summary(segments)
        context['key_points'] = key_points[:5]  # Top 5 key points

        return context

    def _create_summary(self, segments: List[ContextSegment]) -> str:
        """Create a summary of the conversation"""
        # Get the initial idea (first user message)
        initial_idea = next(
            (s.content for s in segments if s.segment_type == 'user'),
            "No initial idea found"
        )

        # Count questions and answers
        question_count = sum(1 for s in segments if s.segment_type == 'question')
        answer_count = sum(1 for s in segments if s.segment_type == 'answer')

        summary = (
            f"Initial idea: {initial_idea[:100]}...\n"
            f"Questions asked: {question_count}\n"
            f"Answers provided: {answer_count}\n"
            f"Total segments: {len(segments)}"
        )

        return summary

    def _calculate_compression_ratio(
        self,
        original: List[ContextSegment],
        optimized: List[ContextSegment]
    ) -> float:
        """Calculate compression ratio"""
        original_tokens = sum(s.token_count for s in original)
        optimized_tokens = sum(s.token_count for s in optimized)

        if original_tokens == 0:
            return 0.0

        return 1.0 - (optimized_tokens / original_tokens)

    def get_optimization_stats(self, conversation_id: int) -> Dict[str, Any]:
        """Get optimization statistics for a conversation"""
        try:
            segments = self._get_context_segments(conversation_id)
            total_tokens = sum(s.token_count for s in segments)

            return {
                'conversation_id': conversation_id,
                'total_segments': len(segments),
                'total_tokens': total_tokens,
                'segment_breakdown': {
                    segment_type: {
                        'count': sum(1 for s in segments if s.segment_type == segment_type),
                        'tokens': sum(s.token_count for s in segments if s.segment_type == segment_type)
                    }
                    for segment_type in set(s.segment_type for s in segments)
                },
                'max_tokens': self.max_tokens,
                'needs_optimization': total_tokens > self.max_tokens
            }

        except Exception as e:
            self.logger.error(f"Error getting optimization stats: {e}")
            return {'error': str(e)}
