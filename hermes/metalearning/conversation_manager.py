"""
Meta-Learning Conversation Manager
Manages conversations with context and question flow
"""

import logging
import json
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from ..config import Config
from ..database import Database
from ..logger import get_logger
from .question_generator import QuestionGenerator, Question
from .pattern_engine import PatternEngine

logger = get_logger('metalearning.conversation')

class ConversationState(Enum):
    """Conversation states"""
    INITIAL = "initial"
    GATHERING_CONTEXT = "gathering_context"
    READY_TO_EXECUTE = "ready_to_execute"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"

@dataclass
class ConversationMessage:
    """Single message in a conversation"""
    message_type: str  # 'user', 'assistant', 'system'
    sender: str
    content: str
    metadata: Dict[str, Any]
    timestamp: datetime

class ConversationManager:
    """Manages interactive conversations with meta-learning"""

    def __init__(self, config: Optional[Config] = None):
        self.config = config or Config()
        self.db = Database()
        self.question_generator = QuestionGenerator(self.config)
        self.pattern_engine = PatternEngine(self.config)
        self.logger = get_logger('conversation_manager')

    def create_conversation(self, job_id: int, initial_idea: str) -> int:
        """
        Create a new conversation for a job

        Args:
            job_id: Associated job ID
            initial_idea: User's initial idea

        Returns:
            Conversation ID
        """
        try:
            with self.db.get_connection() as conn:
                cursor = conn.execute("""
                    INSERT INTO conversations (job_id, status)
                    VALUES (?, ?)
                """, (job_id, ConversationState.INITIAL.value))
                conversation_id = cursor.lastrowid
                conn.commit()

            # Add initial message
            self.add_message(
                conversation_id,
                'user',
                'user',
                initial_idea,
                {'type': 'initial_idea'}
            )

            self.logger.info(f"Created conversation {conversation_id} for job {job_id}")
            return conversation_id

        except Exception as e:
            self.logger.error(f"Error creating conversation: {e}")
            raise

    def add_message(
        self,
        conversation_id: int,
        message_type: str,
        sender: str,
        content: str,
        metadata: Dict[str, Any] = None
    ):
        """Add a message to the conversation"""
        try:
            with self.db.get_connection() as conn:
                conn.execute("""
                    INSERT INTO conversation_messages (
                        conversation_id, message_type, sender, content, metadata
                    ) VALUES (?, ?, ?, ?, ?)
                """, (
                    conversation_id,
                    message_type,
                    sender,
                    content,
                    json.dumps(metadata or {})
                ))

                # Update conversation updated_at
                conn.execute("""
                    UPDATE conversations
                    SET updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                """, (conversation_id,))

                conn.commit()

            self.logger.debug(f"Added {message_type} message to conversation {conversation_id}")

        except Exception as e:
            self.logger.error(f"Error adding message: {e}")

    def get_conversation_messages(self, conversation_id: int) -> List[ConversationMessage]:
        """Get all messages in a conversation"""
        try:
            with self.db.get_connection() as conn:
                cursor = conn.execute("""
                    SELECT * FROM conversation_messages
                    WHERE conversation_id = ?
                    ORDER BY created_at
                """, (conversation_id,))

                messages = []
                for row in cursor.fetchall():
                    message = ConversationMessage(
                        message_type=row['message_type'],
                        sender=row['sender'],
                        content=row['content'],
                        metadata=json.loads(row['metadata']) if row['metadata'] else {},
                        timestamp=row['created_at']
                    )
                    messages.append(message)

                return messages

        except Exception as e:
            self.logger.error(f"Error getting messages: {e}")
            return []

    def start_context_gathering(self, conversation_id: int, idea: str) -> List[Question]:
        """
        Start gathering context by generating questions

        Args:
            conversation_id: Conversation ID
            idea: User's idea

        Returns:
            List of questions to ask
        """
        try:
            # Update conversation state
            self._update_state(conversation_id, ConversationState.GATHERING_CONTEXT)

            # Check patterns for suggestions
            suggestions = self.pattern_engine.get_suggestions(idea)

            # Generate questions
            questions = self.question_generator.generate_questions(idea, conversation_id)

            # Add system message about questions
            if questions:
                self.add_message(
                    conversation_id,
                    'system',
                    'hermes',
                    f"I have {len(questions)} questions to better understand your request.",
                    {
                        'type': 'questions_generated',
                        'question_count': len(questions),
                        'has_pattern_suggestions': suggestions.get('has_suggestions', False)
                    }
                )

            self.logger.info(f"Generated {len(questions)} questions for conversation {conversation_id}")
            return questions

        except Exception as e:
            self.logger.error(f"Error starting context gathering: {e}")
            return []

    def process_answer(
        self,
        conversation_id: int,
        question_id: str,
        answer: str
    ) -> Dict[str, Any]:
        """
        Process an answer to a question

        Args:
            conversation_id: Conversation ID
            question_id: Question ID
            answer: User's answer

        Returns:
            Processing result
        """
        try:
            # Add answer as message
            self.add_message(
                conversation_id,
                'user',
                'user',
                answer,
                {
                    'type': 'question_answer',
                    'question_id': question_id
                }
            )

            # Process the answer
            result = self.question_generator.process_answer(question_id, answer, conversation_id)

            # Check if all questions are answered
            unanswered = self.question_generator.get_unanswered_questions(conversation_id)

            if not unanswered:
                # All questions answered, ready to execute
                self._update_state(conversation_id, ConversationState.READY_TO_EXECUTE)

                result['all_answered'] = True
                result['ready_to_execute'] = True

                self.add_message(
                    conversation_id,
                    'system',
                    'hermes',
                    "All questions answered. Ready to execute your request.",
                    {'type': 'context_complete'}
                )
            else:
                result['all_answered'] = False
                result['remaining_questions'] = len(unanswered)

            return result

        except Exception as e:
            self.logger.error(f"Error processing answer: {e}")
            return {'success': False, 'error': str(e)}

    def get_enhanced_context(self, conversation_id: int) -> Dict[str, Any]:
        """
        Get enhanced context from conversation including answers

        Args:
            conversation_id: Conversation ID

        Returns:
            Enhanced context dictionary
        """
        try:
            # Get all messages
            messages = self.get_conversation_messages(conversation_id)

            # Get questions and answers
            questions = self.question_generator.get_all_questions(conversation_id)

            # Extract answers from messages
            answers = [
                msg for msg in messages
                if msg.metadata.get('type') == 'question_answer'
            ]

            # Build context
            context = {
                'conversation_id': conversation_id,
                'message_count': len(messages),
                'questions_asked': len(questions),
                'answers_provided': len(answers),
                'answers': {},
                'conversation_history': []
            }

            # Map answers to questions
            for i, question in enumerate(questions):
                if i < len(answers):
                    context['answers'][question['question_text']] = answers[i].content

            # Add conversation history
            for msg in messages:
                if msg.message_type in ['user', 'assistant']:
                    context['conversation_history'].append({
                        'role': msg.sender,
                        'content': msg.content,
                        'timestamp': str(msg.timestamp)
                    })

            return context

        except Exception as e:
            self.logger.error(f"Error getting enhanced context: {e}")
            return {}

    def finalize_conversation(
        self,
        conversation_id: int,
        execution_result: Dict[str, Any]
    ):
        """
        Finalize conversation after execution

        Args:
            conversation_id: Conversation ID
            execution_result: Result of job execution
        """
        try:
            # Update state based on result
            if execution_result.get('success', False):
                self._update_state(conversation_id, ConversationState.COMPLETED)
            else:
                self._update_state(conversation_id, ConversationState.FAILED)

            # Get conversation data for learning
            messages = self.get_conversation_messages(conversation_id)
            questions = self.question_generator.get_all_questions(conversation_id)

            # Extract initial idea
            initial_idea = next(
                (msg.content for msg in messages if msg.metadata.get('type') == 'initial_idea'),
                None
            )

            if initial_idea:
                # Get answers
                with self.db.get_connection() as conn:
                    cursor = conn.execute("""
                        SELECT q.id, q.question_text, r.response_text, r.confidence_score
                        FROM metalearning_questions q
                        LEFT JOIN metalearning_responses r ON q.id = r.question_id
                        WHERE q.conversation_id = ?
                    """, (conversation_id,))

                    answers = [dict(row) for row in cursor.fetchall()]

                # Learn from interaction
                self.pattern_engine.learn_from_interaction(
                    initial_idea,
                    questions,
                    answers,
                    execution_result
                )

            self.logger.info(f"Finalized conversation {conversation_id}")

        except Exception as e:
            self.logger.error(f"Error finalizing conversation: {e}")

    def _update_state(self, conversation_id: int, state: ConversationState):
        """Update conversation state"""
        try:
            with self.db.get_connection() as conn:
                conn.execute("""
                    UPDATE conversations
                    SET status = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                """, (state.value, conversation_id))
                conn.commit()

            self.logger.debug(f"Updated conversation {conversation_id} state to {state.value}")

        except Exception as e:
            self.logger.error(f"Error updating conversation state: {e}")

    def get_conversation_state(self, conversation_id: int) -> Optional[ConversationState]:
        """Get current conversation state"""
        try:
            with self.db.get_connection() as conn:
                cursor = conn.execute("""
                    SELECT status FROM conversations WHERE id = ?
                """, (conversation_id,))
                row = cursor.fetchone()

                if row:
                    return ConversationState(row['status'])

                return None

        except Exception as e:
            self.logger.error(f"Error getting conversation state: {e}")
            return None

    def get_conversation_summary(self, conversation_id: int) -> Dict[str, Any]:
        """Get summary of conversation"""
        try:
            messages = self.get_conversation_messages(conversation_id)
            questions = self.question_generator.get_all_questions(conversation_id)
            state = self.get_conversation_state(conversation_id)

            return {
                'conversation_id': conversation_id,
                'state': state.value if state else 'unknown',
                'message_count': len(messages),
                'question_count': len(questions),
                'answered_count': len([q for q in questions if q.get('answered_at')]),
                'created_at': messages[0].timestamp if messages else None,
                'last_updated': messages[-1].timestamp if messages else None
            }

        except Exception as e:
            self.logger.error(f"Error getting conversation summary: {e}")
            return {}

    def should_gather_context(self, idea: str) -> bool:
        """Determine if context gathering is needed"""
        return self.question_generator.should_ask_questions(idea)