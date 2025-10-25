"""
Meta-Learning Pattern Recognition Engine
Learns from interactions and recognizes patterns
"""

import logging
import json
import hashlib
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta
from collections import defaultdict

from ..config import Config
from ..database import Database
from ..logger import get_logger

logger = get_logger('metalearning.patterns')

@dataclass
class Pattern:
    """Recognized pattern with metadata"""
    pattern_id: str
    pattern_name: str
    pattern_type: str
    pattern_data: Dict[str, Any]
    confidence_score: float
    usage_count: int
    success_count: int
    created_at: datetime
    updated_at: datetime

class PatternEngine:
    """Recognizes and learns from patterns in user interactions"""

    def __init__(self, config: Optional[Config] = None):
        self.config = config or Config()
        self.db = Database()
        self.min_confidence = self.config.get('metalearning.min_confidence', 0.7)
        self.learning_rate = self.config.get('metalearning.learning_rate', 0.1)
        self.logger = get_logger('pattern_engine')

        # In-memory pattern cache
        self._pattern_cache = {}
        self._load_patterns()

    def _load_patterns(self):
        """Load existing patterns from database"""
        try:
            with self.db.get_connection() as conn:
                cursor = conn.execute("""
                    SELECT * FROM metalearning_patterns
                    WHERE confidence_score >= ?
                    ORDER BY usage_count DESC
                """, (self.min_confidence,))

                for row in cursor.fetchall():
                    pattern = Pattern(
                        pattern_id=row['pattern_name'],
                        pattern_name=row['pattern_name'],
                        pattern_type=row['pattern_type'],
                        pattern_data=json.loads(row['pattern_data']),
                        confidence_score=row['confidence_score'],
                        usage_count=row['usage_count'],
                        success_count=row['success_count'],
                        created_at=row['created_at'],
                        updated_at=row['updated_at']
                    )
                    self._pattern_cache[pattern.pattern_id] = pattern

            self.logger.info(f"Loaded {len(self._pattern_cache)} patterns from database")

        except Exception as e:
            self.logger.error(f"Error loading patterns: {e}")

    def recognize_patterns(self, idea: str, context: Dict[str, Any] = None) -> List[Pattern]:
        """
        Recognize patterns in an idea

        Args:
            idea: User's idea/task description
            context: Additional context information

        Returns:
            List of matching patterns
        """
        matched_patterns = []

        try:
            # Extract features from idea
            features = self._extract_features(idea, context)

            # Check against known patterns
            for pattern in self._pattern_cache.values():
                similarity = self._calculate_similarity(features, pattern.pattern_data)

                if similarity >= self.min_confidence:
                    matched_patterns.append(pattern)
                    self.logger.info(f"Matched pattern: {pattern.pattern_name} (confidence: {similarity:.2f})")

            # Sort by confidence
            matched_patterns.sort(key=lambda p: p.confidence_score, reverse=True)

            return matched_patterns

        except Exception as e:
            self.logger.error(f"Error recognizing patterns: {e}")
            return []

    def learn_from_interaction(
        self,
        idea: str,
        questions: List[Dict[str, Any]],
        answers: List[Dict[str, Any]],
        outcome: Dict[str, Any]
    ):
        """
        Learn from a complete interaction

        Args:
            idea: Original idea
            questions: Questions asked
            answers: Answers provided
            outcome: Job execution outcome
        """
        try:
            # Extract pattern from interaction
            pattern_data = {
                'idea_features': self._extract_features(idea),
                'question_types': [q.get('question_type') for q in questions],
                'answer_patterns': self._extract_answer_patterns(answers),
                'outcome_success': outcome.get('success', False),
                'execution_time': outcome.get('execution_time_ms', 0),
                'error_count': outcome.get('error_count', 0)
            }

            # Generate pattern identifier
            pattern_id = self._generate_pattern_id(pattern_data)

            # Check if pattern exists
            if pattern_id in self._pattern_cache:
                # Update existing pattern
                self._update_pattern(pattern_id, pattern_data, outcome.get('success', False))
            else:
                # Create new pattern
                self._create_pattern(pattern_id, pattern_data, outcome.get('success', False))

            self.logger.info(f"Learned from interaction, pattern: {pattern_id}")

        except Exception as e:
            self.logger.error(f"Error learning from interaction: {e}")

    def _extract_features(self, idea: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Extract features from an idea"""
        features = {
            'length': len(idea.split()),
            'has_code_keywords': any(kw in idea.lower() for kw in ['code', 'script', 'function', 'program']),
            'has_data_keywords': any(kw in idea.lower() for kw in ['data', 'analyze', 'process', 'extract']),
            'has_creative_keywords': any(kw in idea.lower() for kw in ['write', 'create', 'generate', 'design']),
            'has_technical_keywords': any(kw in idea.lower() for kw in ['api', 'database', 'algorithm', 'optimize']),
            'question_marks': idea.count('?'),
            'specificity_score': self._calculate_specificity(idea)
        }

        if context:
            features['context_provided'] = True
            features['context_keys'] = list(context.keys())

        return features

    def _calculate_specificity(self, idea: str) -> float:
        """Calculate how specific an idea is"""
        # Specific indicators
        specific_terms = ['must', 'should', 'exactly', 'specifically', 'particular', 'precise']
        vague_terms = ['something', 'anything', 'maybe', 'probably', 'some', 'any']

        specific_count = sum(1 for term in specific_terms if term in idea.lower())
        vague_count = sum(1 for term in vague_terms if term in idea.lower())

        word_count = len(idea.split())

        # More words generally means more specific
        length_score = min(word_count / 50, 1.0)

        # Specific terms increase, vague terms decrease
        term_score = (specific_count * 0.2) - (vague_count * 0.2)

        return max(0.0, min(1.0, length_score + term_score))

    def _extract_answer_patterns(self, answers: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Extract patterns from answers"""
        return {
            'answer_count': len(answers),
            'avg_length': sum(len(a.get('response_text', '').split()) for a in answers) / max(len(answers), 1),
            'confidence_scores': [a.get('confidence_score', 0.5) for a in answers],
            'avg_confidence': sum(a.get('confidence_score', 0.5) for a in answers) / max(len(answers), 1)
        }

    def _calculate_similarity(self, features1: Dict[str, Any], features2: Dict[str, Any]) -> float:
        """Calculate similarity between two feature sets"""
        # Simple similarity based on common features
        common_features = set(features1.keys()) & set(features2.keys())

        if not common_features:
            return 0.0

        similarity_scores = []

        for feature in common_features:
            val1 = features1[feature]
            val2 = features2.get('idea_features', {}).get(feature)

            if val2 is None:
                continue

            # Boolean features
            if isinstance(val1, bool) and isinstance(val2, bool):
                similarity_scores.append(1.0 if val1 == val2 else 0.0)

            # Numeric features
            elif isinstance(val1, (int, float)) and isinstance(val2, (int, float)):
                max_val = max(abs(val1), abs(val2), 1)
                similarity_scores.append(1.0 - abs(val1 - val2) / max_val)

        return sum(similarity_scores) / len(similarity_scores) if similarity_scores else 0.0

    def _generate_pattern_id(self, pattern_data: Dict[str, Any]) -> str:
        """Generate unique pattern identifier"""
        # Create a hash of key pattern features
        pattern_str = json.dumps({
            'idea_features': pattern_data.get('idea_features', {}),
            'question_types': sorted(pattern_data.get('question_types', []))
        }, sort_keys=True)

        return hashlib.sha256(pattern_str.encode()).hexdigest()[:16]

    def _create_pattern(self, pattern_id: str, pattern_data: Dict[str, Any], success: bool):
        """Create a new pattern"""
        try:
            pattern = Pattern(
                pattern_id=pattern_id,
                pattern_name=f"pattern_{pattern_id[:8]}",
                pattern_type='interaction',
                pattern_data=pattern_data,
                confidence_score=0.5,  # Start with medium confidence
                usage_count=1,
                success_count=1 if success else 0,
                created_at=datetime.now(),
                updated_at=datetime.now()
            )

            # Store in database
            with self.db.get_connection() as conn:
                conn.execute("""
                    INSERT INTO metalearning_patterns (
                        pattern_name, pattern_type, pattern_data,
                        confidence_score, usage_count, success_count
                    ) VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    pattern.pattern_name,
                    pattern.pattern_type,
                    json.dumps(pattern.pattern_data),
                    pattern.confidence_score,
                    pattern.usage_count,
                    pattern.success_count
                ))
                conn.commit()

            # Add to cache
            self._pattern_cache[pattern_id] = pattern

            self.logger.info(f"Created new pattern: {pattern.pattern_name}")

        except Exception as e:
            self.logger.error(f"Error creating pattern: {e}")

    def _update_pattern(self, pattern_id: str, pattern_data: Dict[str, Any], success: bool):
        """Update existing pattern"""
        try:
            pattern = self._pattern_cache.get(pattern_id)
            if not pattern:
                return

            # Update counts
            pattern.usage_count += 1
            if success:
                pattern.success_count += 1

            # Update confidence score
            success_rate = pattern.success_count / pattern.usage_count
            pattern.confidence_score = (
                pattern.confidence_score * (1 - self.learning_rate) +
                success_rate * self.learning_rate
            )

            pattern.updated_at = datetime.now()

            # Update in database
            with self.db.get_connection() as conn:
                conn.execute("""
                    UPDATE metalearning_patterns
                    SET usage_count = ?,
                        success_count = ?,
                        confidence_score = ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE pattern_name = ?
                """, (
                    pattern.usage_count,
                    pattern.success_count,
                    pattern.confidence_score,
                    pattern.pattern_name
                ))
                conn.commit()

            self.logger.info(f"Updated pattern: {pattern.pattern_name} (confidence: {pattern.confidence_score:.2f})")

        except Exception as e:
            self.logger.error(f"Error updating pattern: {e}")

    def get_suggestions(self, idea: str) -> Dict[str, Any]:
        """Get suggestions based on recognized patterns"""
        matched_patterns = self.recognize_patterns(idea)

        if not matched_patterns:
            return {'has_suggestions': False}

        # Get the best matching pattern
        best_pattern = matched_patterns[0]

        suggestions = {
            'has_suggestions': True,
            'confidence': best_pattern.confidence_score,
            'pattern_name': best_pattern.pattern_name,
            'suggested_questions': best_pattern.pattern_data.get('question_types', []),
            'expected_execution_time': best_pattern.pattern_data.get('execution_time', 0),
            'success_rate': best_pattern.success_count / best_pattern.usage_count,
            'usage_count': best_pattern.usage_count
        }

        return suggestions

    def get_pattern_statistics(self) -> Dict[str, Any]:
        """Get statistics about learned patterns"""
        try:
            total_patterns = len(self._pattern_cache)
            high_confidence = sum(1 for p in self._pattern_cache.values() if p.confidence_score >= 0.8)
            total_usage = sum(p.usage_count for p in self._pattern_cache.values())

            return {
                'total_patterns': total_patterns,
                'high_confidence_patterns': high_confidence,
                'total_usage': total_usage,
                'avg_confidence': sum(p.confidence_score for p in self._pattern_cache.values()) / max(total_patterns, 1),
                'patterns': [
                    {
                        'name': p.pattern_name,
                        'confidence': p.confidence_score,
                        'usage': p.usage_count,
                        'success_rate': p.success_count / p.usage_count
                    }
                    for p in sorted(self._pattern_cache.values(), key=lambda x: x.usage_count, reverse=True)[:10]
                ]
            }

        except Exception as e:
            self.logger.error(f"Error getting pattern statistics: {e}")
            return {'error': str(e)}

    def cleanup_old_patterns(self, days: int = 30):
        """Remove old unused patterns"""
        try:
            cutoff_date = datetime.now() - timedelta(days=days)

            with self.db.get_connection() as conn:
                # Delete patterns with low confidence and no recent usage
                conn.execute("""
                    DELETE FROM metalearning_patterns
                    WHERE confidence_score < ? AND updated_at < ? AND usage_count < 5
                """, (self.min_confidence, cutoff_date))
                conn.commit()

            # Reload patterns
            self._pattern_cache.clear()
            self._load_patterns()

            self.logger.info("Cleaned up old patterns")

        except Exception as e:
            self.logger.error(f"Error cleaning up patterns: {e}")