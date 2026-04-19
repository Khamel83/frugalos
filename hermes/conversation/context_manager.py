"""
Advanced conversation context management system.

This module provides intelligent context management for multi-turn conversations including:
- Sliding window context management
- Token-aware context optimization
- Semantic compression
- Context prioritization
- Automatic summarization
- Memory retrieval augmentation
"""

import asyncio
import json
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
from collections import deque
from enum import Enum
import logging

import tiktoken
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

logger = logging.getLogger(__name__)


class MessageRole(Enum):
    """Message roles in conversation."""
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    FUNCTION = "function"
    TOOL = "tool"


class ContextStrategy(Enum):
    """Strategies for managing conversation context."""
    SLIDING_WINDOW = "sliding_window"
    SEMANTIC_COMPRESSION = "semantic_compression"
    HIERARCHICAL_SUMMARY = "hierarchical_summary"
    PRIORITY_BASED = "priority_based"
    HYBRID = "hybrid"


@dataclass
class Message:
    """A single conversation message."""
    role: MessageRole
    content: str
    timestamp: datetime = field(default_factory=datetime.utcnow)
    tokens: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)
    importance_score: float = 1.0
    embedding: Optional[List[float]] = None
    message_id: Optional[str] = None


@dataclass
class ConversationContext:
    """Complete conversation context with metadata."""
    conversation_id: str
    messages: List[Message]
    system_prompt: Optional[str] = None
    max_tokens: int = 4096
    current_tokens: int = 0
    strategy: ContextStrategy = ContextStrategy.SLIDING_WINDOW
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)
    last_updated: datetime = field(default_factory=datetime.utcnow)


@dataclass
class ContextWindow:
    """A window of conversation context."""
    messages: List[Message]
    total_tokens: int
    summary: Optional[str] = None
    compressed: bool = False
    strategy_used: str = ""


class TokenCounter:
    """Efficient token counting for conversation messages."""

    def __init__(self, model: str = "gpt-3.5-turbo"):
        try:
            self.encoding = tiktoken.encoding_for_model(model)
        except KeyError:
            self.encoding = tiktoken.get_encoding("cl100k_base")

    def count_tokens(self, text: str) -> int:
        """Count tokens in text."""
        return len(self.encoding.encode(text))

    def count_message_tokens(self, message: Message) -> int:
        """Count tokens in a message including overhead."""
        # Base tokens for message formatting
        tokens = 4  # Message formatting overhead

        # Role tokens
        tokens += len(self.encoding.encode(message.role.value))

        # Content tokens
        tokens += len(self.encoding.encode(message.content))

        return tokens

    def count_messages_tokens(self, messages: List[Message]) -> int:
        """Count total tokens in message list."""
        return sum(self.count_message_tokens(msg) for msg in messages)


class ContextPrioritizer:
    """Prioritizes messages based on importance for context management."""

    def __init__(self):
        self.recency_weight = 0.4
        self.relevance_weight = 0.3
        self.length_weight = 0.2
        self.role_weight = 0.1

    def calculate_importance(self, message: Message,
                           current_query: Optional[str] = None,
                           total_messages: int = 0,
                           message_index: int = 0) -> float:
        """Calculate importance score for a message."""
        score = 0.0

        # Recency score (more recent = more important)
        if total_messages > 0:
            recency_score = message_index / total_messages
            score += recency_score * self.recency_weight

        # Relevance score (if query provided)
        if current_query and message.embedding:
            # Would use semantic similarity here
            relevance_score = 0.5  # Placeholder
            score += relevance_score * self.relevance_weight

        # Length score (longer messages often more important)
        # Normalize by typical message length (100 tokens)
        length_score = min(1.0, message.tokens / 100)
        score += length_score * self.length_weight

        # Role score (assistant responses often more important)
        role_scores = {
            MessageRole.SYSTEM: 1.0,
            MessageRole.ASSISTANT: 0.8,
            MessageRole.USER: 0.6,
            MessageRole.FUNCTION: 0.7,
            MessageRole.TOOL: 0.7
        }
        role_score = role_scores.get(message.role, 0.5)
        score += role_score * self.role_weight

        return score

    def prioritize_messages(self, messages: List[Message],
                          current_query: Optional[str] = None) -> List[Tuple[Message, float]]:
        """Return messages with importance scores, sorted by importance."""
        total_messages = len(messages)

        scored_messages = []
        for idx, message in enumerate(messages):
            importance = self.calculate_importance(
                message,
                current_query,
                total_messages,
                idx
            )
            message.importance_score = importance
            scored_messages.append((message, importance))

        # Sort by importance (descending)
        scored_messages.sort(key=lambda x: x[1], reverse=True)

        return scored_messages


class ContextCompressor:
    """Compresses conversation context using various strategies."""

    def __init__(self, token_counter: TokenCounter):
        self.token_counter = token_counter

    async def compress_messages(self, messages: List[Message],
                               target_tokens: int,
                               strategy: ContextStrategy = ContextStrategy.SLIDING_WINDOW) -> ContextWindow:
        """Compress messages to fit within token budget."""
        if strategy == ContextStrategy.SLIDING_WINDOW:
            return await self._sliding_window_compress(messages, target_tokens)
        elif strategy == ContextStrategy.SEMANTIC_COMPRESSION:
            return await self._semantic_compress(messages, target_tokens)
        elif strategy == ContextStrategy.HIERARCHICAL_SUMMARY:
            return await self._hierarchical_summary(messages, target_tokens)
        elif strategy == ContextStrategy.PRIORITY_BASED:
            return await self._priority_based_compress(messages, target_tokens)
        else:  # HYBRID
            return await self._hybrid_compress(messages, target_tokens)

    async def _sliding_window_compress(self, messages: List[Message],
                                      target_tokens: int) -> ContextWindow:
        """Keep most recent messages that fit in token budget."""
        selected_messages = []
        current_tokens = 0

        # Always keep system message if present
        if messages and messages[0].role == MessageRole.SYSTEM:
            selected_messages.append(messages[0])
            current_tokens += messages[0].tokens
            messages = messages[1:]

        # Add messages from most recent backwards
        for message in reversed(messages):
            if current_tokens + message.tokens <= target_tokens:
                selected_messages.insert(1 if selected_messages else 0, message)
                current_tokens += message.tokens
            else:
                break

        return ContextWindow(
            messages=selected_messages,
            total_tokens=current_tokens,
            compressed=len(selected_messages) < len(messages),
            strategy_used="sliding_window"
        )

    async def _semantic_compress(self, messages: List[Message],
                                target_tokens: int) -> ContextWindow:
        """Compress by removing semantically redundant messages."""
        # Simplified version - would use embeddings in production
        return await self._sliding_window_compress(messages, target_tokens)

    async def _hierarchical_summary(self, messages: List[Message],
                                   target_tokens: int) -> ContextWindow:
        """Create hierarchical summaries of older messages."""
        if not messages:
            return ContextWindow(messages=[], total_tokens=0, strategy_used="hierarchical_summary")

        # Keep recent messages, summarize older ones
        recent_token_budget = int(target_tokens * 0.7)
        summary_token_budget = int(target_tokens * 0.3)

        # Get recent messages using sliding window
        recent_window = await self._sliding_window_compress(messages, recent_token_budget)

        # Determine which messages to summarize
        messages_to_summarize = []
        for msg in messages:
            if msg not in recent_window.messages:
                messages_to_summarize.append(msg)

        # Create summary if needed
        summary = None
        if messages_to_summarize:
            summary = await self._create_summary(messages_to_summarize, summary_token_budget)

        return ContextWindow(
            messages=recent_window.messages,
            total_tokens=recent_window.total_tokens + (self.token_counter.count_tokens(summary) if summary else 0),
            summary=summary,
            compressed=True,
            strategy_used="hierarchical_summary"
        )

    async def _priority_based_compress(self, messages: List[Message],
                                      target_tokens: int) -> ContextWindow:
        """Select messages based on importance scores."""
        prioritizer = ContextPrioritizer()
        scored_messages = prioritizer.prioritize_messages(messages)

        selected_messages = []
        current_tokens = 0

        # Add highest priority messages that fit
        for message, score in scored_messages:
            if current_tokens + message.tokens <= target_tokens:
                selected_messages.append(message)
                current_tokens += message.tokens

        # Sort by original order
        selected_messages.sort(key=lambda m: messages.index(m))

        return ContextWindow(
            messages=selected_messages,
            total_tokens=current_tokens,
            compressed=len(selected_messages) < len(messages),
            strategy_used="priority_based"
        )

    async def _hybrid_compress(self, messages: List[Message],
                              target_tokens: int) -> ContextWindow:
        """Use hybrid approach combining multiple strategies."""
        # Try priority-based first
        priority_window = await self._priority_based_compress(messages, target_tokens)

        # If we have room, try to add recent messages not in priority set
        if priority_window.total_tokens < target_tokens * 0.9:
            # Add recent messages
            for msg in reversed(messages):
                if msg not in priority_window.messages:
                    if priority_window.total_tokens + msg.tokens <= target_tokens:
                        priority_window.messages.append(msg)
                        priority_window.total_tokens += msg.tokens

            # Resort by original order
            priority_window.messages.sort(key=lambda m: messages.index(m))

        priority_window.strategy_used = "hybrid"
        return priority_window

    async def _create_summary(self, messages: List[Message], max_tokens: int) -> str:
        """Create a summary of messages."""
        # Simplified summary - would use LLM in production
        message_contents = [f"{msg.role.value}: {msg.content[:100]}..." for msg in messages[:5]]
        summary = f"[Summary of {len(messages)} earlier messages: {'; '.join(message_contents)}]"

        # Truncate if too long
        summary_tokens = self.token_counter.count_tokens(summary)
        if summary_tokens > max_tokens:
            # Trim summary
            while summary_tokens > max_tokens and len(summary) > 50:
                summary = summary[:-10] + "...]"
                summary_tokens = self.token_counter.count_tokens(summary)

        return summary


class ConversationContextManager:
    """Main context manager for conversations."""

    def __init__(self, default_max_tokens: int = 4096,
                 default_strategy: ContextStrategy = ContextStrategy.HYBRID):
        self.default_max_tokens = default_max_tokens
        self.default_strategy = default_strategy
        self.token_counter = TokenCounter()
        self.compressor = ContextCompressor(self.token_counter)
        self.prioritizer = ContextPrioritizer()

        # Active conversations
        self.conversations: Dict[str, ConversationContext] = {}

    def create_conversation(self, conversation_id: str,
                          system_prompt: Optional[str] = None,
                          max_tokens: Optional[int] = None,
                          strategy: Optional[ContextStrategy] = None) -> ConversationContext:
        """Create a new conversation context."""
        context = ConversationContext(
            conversation_id=conversation_id,
            messages=[],
            system_prompt=system_prompt,
            max_tokens=max_tokens or self.default_max_tokens,
            strategy=strategy or self.default_strategy
        )

        # Add system message if provided
        if system_prompt:
            system_msg = Message(
                role=MessageRole.SYSTEM,
                content=system_prompt,
                tokens=self.token_counter.count_tokens(system_prompt),
                message_id=f"{conversation_id}_sys_0"
            )
            context.messages.append(system_msg)
            context.current_tokens = system_msg.tokens

        self.conversations[conversation_id] = context
        logger.info(f"Created conversation {conversation_id} with strategy {strategy}")

        return context

    def get_conversation(self, conversation_id: str) -> Optional[ConversationContext]:
        """Get conversation context by ID."""
        return self.conversations.get(conversation_id)

    async def add_message(self, conversation_id: str, role: MessageRole,
                         content: str, metadata: Optional[Dict[str, Any]] = None) -> Message:
        """Add a message to conversation."""
        context = self.conversations.get(conversation_id)
        if not context:
            raise ValueError(f"Conversation {conversation_id} not found")

        # Create message
        message = Message(
            role=role,
            content=content,
            tokens=self.token_counter.count_tokens(content),
            metadata=metadata or {},
            message_id=f"{conversation_id}_msg_{len(context.messages)}"
        )

        # Add to context
        context.messages.append(message)
        context.current_tokens += message.tokens
        context.last_updated = datetime.utcnow()

        # Check if compression needed
        if context.current_tokens > context.max_tokens:
            await self._compress_context(context)

        logger.debug(f"Added {role.value} message to {conversation_id}: {len(content)} chars, {message.tokens} tokens")

        return message

    async def _compress_context(self, context: ConversationContext):
        """Compress context to fit within token budget."""
        logger.info(f"Compressing context for {context.conversation_id}: {context.current_tokens} → {context.max_tokens} tokens")

        # Compress messages
        window = await self.compressor.compress_messages(
            context.messages,
            context.max_tokens,
            context.strategy
        )

        # Update context
        context.messages = window.messages
        context.current_tokens = window.total_tokens

        # Store summary if created
        if window.summary:
            context.metadata['last_summary'] = window.summary
            context.metadata['summary_created_at'] = datetime.utcnow().isoformat()

        logger.info(f"Compressed to {len(window.messages)} messages, {window.total_tokens} tokens")

    async def get_context_window(self, conversation_id: str,
                                 max_tokens: Optional[int] = None) -> ContextWindow:
        """Get optimized context window for next request."""
        context = self.conversations.get(conversation_id)
        if not context:
            raise ValueError(f"Conversation {conversation_id} not found")

        target_tokens = max_tokens or context.max_tokens

        # Get compressed window
        window = await self.compressor.compress_messages(
            context.messages,
            target_tokens,
            context.strategy
        )

        return window

    def get_conversation_stats(self, conversation_id: str) -> Dict[str, Any]:
        """Get statistics for a conversation."""
        context = self.conversations.get(conversation_id)
        if not context:
            return {}

        message_counts = {}
        for msg in context.messages:
            role = msg.role.value
            message_counts[role] = message_counts.get(role, 0) + 1

        return {
            'conversation_id': conversation_id,
            'total_messages': len(context.messages),
            'message_counts': message_counts,
            'current_tokens': context.current_tokens,
            'max_tokens': context.max_tokens,
            'utilization': (context.current_tokens / context.max_tokens) * 100,
            'strategy': context.strategy.value,
            'created_at': context.created_at.isoformat(),
            'last_updated': context.last_updated.isoformat(),
            'duration_minutes': (datetime.utcnow() - context.created_at).total_seconds() / 60
        }

    def delete_conversation(self, conversation_id: str) -> bool:
        """Delete a conversation."""
        if conversation_id in self.conversations:
            del self.conversations[conversation_id]
            logger.info(f"Deleted conversation {conversation_id}")
            return True
        return False

    def get_all_conversations(self) -> List[str]:
        """Get list of all active conversation IDs."""
        return list(self.conversations.keys())

    async def optimize_for_model(self, conversation_id: str,
                                model_context_window: int) -> ContextWindow:
        """Optimize context for specific model's context window."""
        context = self.conversations.get(conversation_id)
        if not context:
            raise ValueError(f"Conversation {conversation_id} not found")

        # Reserve tokens for response (typically 1/4 of window)
        max_input_tokens = int(model_context_window * 0.75)

        return await self.get_context_window(conversation_id, max_input_tokens)


class ConversationBranchManager:
    """Manages conversation branches and alternate paths."""

    def __init__(self, context_manager: ConversationContextManager):
        self.context_manager = context_manager
        self.branches: Dict[str, List[str]] = {}  # conversation_id -> [branch_ids]
        self.branch_points: Dict[str, int] = {}  # branch_id -> message_index

    def create_branch(self, conversation_id: str, branch_from_index: int) -> str:
        """Create a new branch from a conversation at specific message."""
        context = self.context_manager.get_conversation(conversation_id)
        if not context:
            raise ValueError(f"Conversation {conversation_id} not found")

        if branch_from_index >= len(context.messages):
            raise ValueError(f"Invalid branch index {branch_from_index}")

        # Create branch ID
        branch_id = f"{conversation_id}_branch_{len(self.branches.get(conversation_id, []))}"

        # Create new conversation with messages up to branch point
        branch_context = self.context_manager.create_conversation(
            branch_id,
            system_prompt=context.system_prompt,
            max_tokens=context.max_tokens,
            strategy=context.strategy
        )

        # Copy messages up to branch point
        for i in range(1, branch_from_index + 1):  # Skip system message
            if i < len(context.messages):
                msg = context.messages[i]
                asyncio.run(self.context_manager.add_message(
                    branch_id,
                    msg.role,
                    msg.content,
                    msg.metadata
                ))

        # Track branch
        if conversation_id not in self.branches:
            self.branches[conversation_id] = []
        self.branches[conversation_id].append(branch_id)
        self.branch_points[branch_id] = branch_from_index

        logger.info(f"Created branch {branch_id} from {conversation_id} at message {branch_from_index}")

        return branch_id

    def get_branches(self, conversation_id: str) -> List[str]:
        """Get all branches for a conversation."""
        return self.branches.get(conversation_id, [])

    def merge_branch(self, branch_id: str, into_conversation_id: str) -> bool:
        """Merge a branch back into main conversation."""
        branch_context = self.context_manager.get_conversation(branch_id)
        main_context = self.context_manager.get_conversation(into_conversation_id)

        if not branch_context or not main_context:
            return False

        branch_point = self.branch_points.get(branch_id, 0)

        # Add branch messages to main conversation
        for msg in branch_context.messages[branch_point + 1:]:
            asyncio.run(self.context_manager.add_message(
                into_conversation_id,
                msg.role,
                msg.content,
                msg.metadata
            ))

        logger.info(f"Merged branch {branch_id} into {into_conversation_id}")

        return True


# Global context manager
context_manager: Optional[ConversationContextManager] = None
branch_manager: Optional[ConversationBranchManager] = None