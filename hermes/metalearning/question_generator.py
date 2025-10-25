"""
Meta-Learning Question Generator
Generates intelligent questions to gather context before execution
"""

import logging
import re
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

from ..config import Config
from ..database import Database
from ..logger import get_logger

logger = get_logger('metalearning.questions')

class QuestionType(Enum):
    """Types of questions that can be asked"""
    CLARIFICATION = "clarification"
    CONSTRAINT = "constraint"
    PREFERENCE = "preference"
    CONTEXT = "context"
    VALIDATION = "validation"
    SCOPE = "scope"

@dataclass
class Question:
    """Structured question with metadata"""
    question_id: str
    question_text: str
    question_type: QuestionType
    priority: int
    required: bool
    context: Dict[str, Any]
    suggested_answers: List[str] = None
    pattern_id: Optional[str] = None

class QuestionGenerator:
    """Generates contextual questions based on user ideas"""

    def __init__(self, config: Optional[Config] = None):
        self.config = config or Config()
        self.db = Database()
        self.max_questions = self.config.get('metalearning.max_questions', 3)
        self.logger = get_logger('question_generator')

        # Load question templates
        self._templates = self._load_question_templates()

    def _load_question_templates(self) -> Dict[str, List[Dict[str, Any]]]:
        """Load question templates for different scenarios"""
        return {
            'vague_idea': [
                {
                    'text': "What is the primary goal or outcome you're trying to achieve?",
                    'type': QuestionType.CLARIFICATION,
                    'priority': 1,
                    'required': True
                },
                {
                    'text': "Are there any specific constraints or requirements (time, resources, format)?",
                    'type': QuestionType.CONSTRAINT,
                    'priority': 2,
                    'required': False
                },
                {
                    'text': "Do you have any examples or references of what you're looking for?",
                    'type': QuestionType.CONTEXT,
                    'priority': 3,
                    'required': False
                }
            ],
            'technical_task': [
                {
                    'text': "What programming language or technology stack should be used?",
                    'type': QuestionType.PREFERENCE,
                    'priority': 1,
                    'required': False,
                    'suggested_answers': ['Python', 'JavaScript', 'Any', 'Best for task']
                },
                {
                    'text': "Should this follow any specific coding standards or patterns?",
                    'type': QuestionType.PREFERENCE,
                    'priority': 2,
                    'required': False
                },
                {
                    'text': "What is the expected input and output format?",
                    'type': QuestionType.VALIDATION,
                    'priority': 3,
                    'required': True
                }
            ],
            'data_processing': [
                {
                    'text': "What is the format and structure of your input data?",
                    'type': QuestionType.CONTEXT,
                    'priority': 1,
                    'required': True
                },
                {
                    'text': "What should be done with the results (save, display, process further)?",
                    'type': QuestionType.CLARIFICATION,
                    'priority': 2,
                    'required': True
                },
                {
                    'text': "Are there any data quality or validation requirements?",
                    'type': QuestionType.VALIDATION,
                    'priority': 3,
                    'required': False
                }
            ],
            'creative_task': [
                {
                    'text': "What tone or style are you looking for?",
                    'type': QuestionType.PREFERENCE,
                    'priority': 1,
                    'required': False,
                    'suggested_answers': ['Professional', 'Casual', 'Technical', 'Creative']
                },
                {
                    'text': "Is there a target audience or purpose for this?",
                    'type': QuestionType.CONTEXT,
                    'priority': 2,
                    'required': False
                },
                {
                    'text': "Are there any specific requirements for length or format?",
                    'type': QuestionType.CONSTRAINT,
                    'priority': 3,
                    'required': False
                }
            ],
            'analysis_task': [
                {
                    'text': "What specific insights or metrics are you looking to extract?",
                    'type': QuestionType.CLARIFICATION,
                    'priority': 1,
                    'required': True
                },
                {
                    'text': "How should the results be presented (report, visualization, summary)?",
                    'type': QuestionType.PREFERENCE,
                    'priority': 2,
                    'required': True
                },
                {
                    'text': "Are there any thresholds or criteria that should trigger alerts?",
                    'type': QuestionType.VALIDATION,
                    'priority': 3,
                    'required': False
                }
            ]
        }

    def generate_questions(self, idea: str, conversation_id: int) -> List[Question]:
        """
        Generate contextual questions for an idea

        Args:
            idea: The user's idea/task description
            conversation_id: Database conversation ID

        Returns:
            List of generated questions
        """
        try:
            # Analyze the idea to determine category
            category = self._categorize_idea(idea)
            self.logger.info(f"Categorized idea as: {category}")

            # Get base questions for category
            base_questions = self._templates.get(category, self._templates['vague_idea'])

            # Check for missing critical information
            missing_info = self._identify_missing_information(idea)

            # Generate questions
            questions = []
            question_count = 0

            # Add category-specific questions
            for template in base_questions:
                if question_count >= self.max_questions:
                    break

                # Skip if information is already present
                if self._is_info_present(idea, template['type']):
                    continue

                question = Question(
                    question_id=f"q_{conversation_id}_{question_count}",
                    question_text=template['text'],
                    question_type=template['type'],
                    priority=template['priority'],
                    required=template['required'],
                    context={'category': category, 'template': True},
                    suggested_answers=template.get('suggested_answers')
                )
                questions.append(question)
                question_count += 1

            # Add dynamic questions based on missing information
            for info_type, info_question in missing_info:
                if question_count >= self.max_questions:
                    break

                question = Question(
                    question_id=f"q_{conversation_id}_{question_count}",
                    question_text=info_question,
                    question_type=QuestionType.CLARIFICATION,
                    priority=1,
                    required=True,
                    context={'category': category, 'dynamic': True, 'missing_info': info_type}
                )
                questions.append(question)
                question_count += 1

            # Sort by priority
            questions.sort(key=lambda q: q.priority)

            # Store questions in database
            self._store_questions(questions, conversation_id)

            self.logger.info(f"Generated {len(questions)} questions for conversation {conversation_id}")
            return questions[:self.max_questions]

        except Exception as e:
            self.logger.error(f"Error generating questions: {e}")
            return []

    def _categorize_idea(self, idea: str) -> str:
        """Categorize the idea to select appropriate questions"""
        idea_lower = idea.lower()

        # Technical task indicators
        technical_keywords = ['code', 'script', 'program', 'function', 'api', 'algorithm', 'debug', 'implement']
        if any(kw in idea_lower for kw in technical_keywords):
            return 'technical_task'

        # Data processing indicators
        data_keywords = ['analyze', 'process', 'parse', 'extract', 'transform', 'data', 'file', 'csv', 'json']
        if any(kw in idea_lower for kw in data_keywords):
            return 'data_processing'

        # Creative task indicators
        creative_keywords = ['write', 'create', 'generate', 'design', 'compose', 'draft', 'story', 'article']
        if any(kw in idea_lower for kw in creative_keywords):
            return 'creative_task'

        # Analysis task indicators
        analysis_keywords = ['analyze', 'evaluate', 'assess', 'compare', 'review', 'metrics', 'insights']
        if any(kw in idea_lower for kw in analysis_keywords):
            return 'analysis_task'

        # Check idea length and specificity
        word_count = len(idea.split())
        if word_count < 10:
            return 'vague_idea'

        # Default to vague if unclear
        return 'vague_idea'

    def _identify_missing_information(self, idea: str) -> List[Tuple[str, str]]:
        """Identify critical missing information"""
        missing = []

        # Check for input/output specification
        if not re.search(r'(input|output|format|file|data)', idea, re.IGNORECASE):
            missing.append(('input_output', "What input will you provide and what output do you expect?"))

        # Check for success criteria
        if not re.search(r'(should|must|need|want|expect|result|success)', idea, re.IGNORECASE):
            missing.append(('success_criteria', "How will you know when this task is successfully completed?"))

        # Check for scope/boundaries
        if not re.search(r'(only|just|specifically|limit|scope|exclude)', idea, re.IGNORECASE):
            missing.append(('scope', "Are there any specific boundaries or limitations for this task?"))

        return missing

    def _is_info_present(self, idea: str, question_type: QuestionType) -> bool:
        """Check if information is already present in the idea"""
        idea_lower = idea.lower()

        # Mapping of question types to keywords that indicate presence
        presence_indicators = {
            QuestionType.CONSTRAINT: ['must', 'requirement', 'constraint', 'limit', 'deadline'],
            QuestionType.PREFERENCE: ['prefer', 'like', 'using', 'with', 'style'],
            QuestionType.CONTEXT: ['because', 'for', 'to help', 'in order to', 'context'],
            QuestionType.VALIDATION: ['format', 'output', 'result', 'validate', 'check'],
            QuestionType.SCOPE: ['only', 'just', 'specifically', 'focus on', 'exclude']
        }

        indicators = presence_indicators.get(question_type, [])
        return any(indicator in idea_lower for indicator in indicators)

    def _store_questions(self, questions: List[Question], conversation_id: int):
        """Store questions in database"""
        try:
            for question in questions:
                with self.db.get_connection() as conn:
                    conn.execute("""
                        INSERT INTO metalearning_questions (
                            conversation_id, question_text, question_type, context_data
                        ) VALUES (?, ?, ?, ?)
                    """, (
                        conversation_id,
                        question.question_text,
                        question.question_type.value,
                        str(question.context)
                    ))
                    conn.commit()
        except Exception as e:
            self.logger.error(f"Error storing questions: {e}")

    def process_answer(self, question_id: str, answer: str, conversation_id: int) -> Dict[str, Any]:
        """
        Process an answer to a question

        Args:
            question_id: Question identifier
            answer: User's answer
            conversation_id: Conversation ID

        Returns:
            Processing result with confidence score
        """
        try:
            # Store answer in database
            with self.db.get_connection() as conn:
                # Get question details
                cursor = conn.execute("""
                    SELECT id, question_type FROM metalearning_questions
                    WHERE conversation_id = ?
                    ORDER BY id DESC LIMIT 1
                """, (conversation_id,))
                row = cursor.fetchone()

                if row:
                    question_db_id = row['id']

                    # Store response
                    conn.execute("""
                        INSERT INTO metalearning_responses (
                            question_id, response_text, response_data, confidence_score
                        ) VALUES (?, ?, ?, ?)
                    """, (
                        question_db_id,
                        answer,
                        str({'raw_answer': answer}),
                        self._calculate_answer_confidence(answer)
                    ))

                    # Mark question as answered
                    conn.execute("""
                        UPDATE metalearning_questions
                        SET answered_at = CURRENT_TIMESTAMP
                        WHERE id = ?
                    """, (question_db_id,))

                    conn.commit()

            self.logger.info(f"Processed answer for question {question_id}")

            return {
                'success': True,
                'answer': answer,
                'confidence': self._calculate_answer_confidence(answer),
                'processed': True
            }

        except Exception as e:
            self.logger.error(f"Error processing answer: {e}")
            return {
                'success': False,
                'error': str(e)
            }

    def _calculate_answer_confidence(self, answer: str) -> float:
        """Calculate confidence score for an answer"""
        # Simple heuristic based on answer length and specificity
        word_count = len(answer.split())

        if word_count < 3:
            return 0.3  # Very short answers have low confidence

        if word_count < 10:
            return 0.6  # Short but acceptable

        if word_count < 50:
            return 0.9  # Good detail

        return 0.95  # Very detailed

    def should_ask_questions(self, idea: str) -> bool:
        """Determine if questions should be asked for this idea"""
        # Always ask if meta-learning is enabled
        if not self.config.get('metalearning.enabled', True):
            return False

        # Check idea length - very detailed ideas may not need questions
        word_count = len(idea.split())
        if word_count > 100:  # Very detailed idea
            return False

        # Check if idea is too vague
        if word_count < 5:
            return True

        # Check for ambiguity indicators
        ambiguous_terms = ['something', 'anything', 'whatever', 'some', 'maybe', 'probably']
        if any(term in idea.lower() for term in ambiguous_terms):
            return True

        # Default: ask questions for most ideas
        return True

    def get_all_questions(self, conversation_id: int) -> List[Dict[str, Any]]:
        """Get all questions for a conversation"""
        try:
            with self.db.get_connection() as conn:
                cursor = conn.execute("""
                    SELECT * FROM metalearning_questions
                    WHERE conversation_id = ?
                    ORDER BY asked_at
                """, (conversation_id,))

                return [dict(row) for row in cursor.fetchall()]

        except Exception as e:
            self.logger.error(f"Error getting questions: {e}")
            return []

    def get_unanswered_questions(self, conversation_id: int) -> List[Dict[str, Any]]:
        """Get unanswered questions for a conversation"""
        try:
            with self.db.get_connection() as conn:
                cursor = conn.execute("""
                    SELECT * FROM metalearning_questions
                    WHERE conversation_id = ? AND answered_at IS NULL
                    ORDER BY asked_at
                """, (conversation_id,))

                return [dict(row) for row in cursor.fetchall()]

        except Exception as e:
            self.logger.error(f"Error getting unanswered questions: {e}")
            return []