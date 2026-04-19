"""
Advanced conversation memory and retrieval system.

This module provides long-term memory capabilities including:
- Vector-based semantic search
- Conversation summarization
- Entity and fact extraction
- Memory consolidation
- Retrieval-augmented context
"""

import asyncio
import json
import hashlib
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple, Set
from dataclasses import dataclass, field
from collections import defaultdict
import logging

import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
import redis.asyncio as redis

from .context_manager import Message, MessageRole, ConversationContext

logger = logging.getLogger(__name__)


@dataclass
class MemoryEntry:
    """A single memory entry with metadata."""
    memory_id: str
    content: str
    memory_type: str  # fact, entity, summary, event
    conversation_id: str
    timestamp: datetime
    embedding: Optional[List[float]] = None
    importance_score: float = 0.5
    access_count: int = 0
    last_accessed: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)


@dataclass
class ConversationSummary:
    """Summary of a conversation or conversation segment."""
    summary_id: str
    conversation_id: str
    summary_text: str
    message_range: Tuple[int, int]  # start_index, end_index
    tokens: int
    created_at: datetime
    key_points: List[str] = field(default_factory=list)
    entities_mentioned: List[str] = field(default_factory=list)
    topics: List[str] = field(default_factory=list)


@dataclass
class RetrievalResult:
    """Result from memory retrieval."""
    memories: List[MemoryEntry]
    relevance_scores: List[float]
    total_tokens: int
    retrieval_strategy: str


class EmbeddingService:
    """Service for generating text embeddings."""

    def __init__(self, model: str = "text-embedding-ada-002"):
        self.model = model
        self.cache: Dict[str, List[float]] = {}

    async def embed(self, text: str) -> List[float]:
        """Generate embedding for text."""
        # Check cache
        cache_key = hashlib.md5(text.encode()).hexdigest()
        if cache_key in self.cache:
            return self.cache[cache_key]

        # In production, this would call OpenAI or local embedding model
        # For now, return mock embedding
        embedding = self._mock_embedding(text)

        # Cache result
        self.cache[cache_key] = embedding
        return embedding

    async def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for multiple texts."""
        embeddings = []
        for text in texts:
            embedding = await self.embed(text)
            embeddings.append(embedding)
        return embeddings

    def _mock_embedding(self, text: str) -> List[float]:
        """Generate mock embedding for testing."""
        # Use simple hash-based embedding for testing
        hash_value = hashlib.md5(text.encode()).digest()
        # Convert to list of floats
        embedding = [float(b) / 255.0 for b in hash_value[:16]]
        # Pad to 1536 dimensions (OpenAI ada-002 size)
        embedding.extend([0.0] * (1536 - len(embedding)))
        return embedding


class MemoryStore:
    """Storage backend for conversation memories."""

    def __init__(self, redis_client: Optional[redis.Redis] = None):
        self.redis = redis_client
        self.local_store: Dict[str, MemoryEntry] = {}
        self.summaries: Dict[str, ConversationSummary] = {}

    async def store_memory(self, memory: MemoryEntry) -> bool:
        """Store a memory entry."""
        try:
            if self.redis:
                # Store in Redis
                memory_data = {
                    'content': memory.content,
                    'memory_type': memory.memory_type,
                    'conversation_id': memory.conversation_id,
                    'timestamp': memory.timestamp.isoformat(),
                    'importance_score': memory.importance_score,
                    'access_count': memory.access_count,
                    'metadata': json.dumps(memory.metadata),
                    'tags': json.dumps(memory.tags)
                }

                # Store embedding separately (binary data)
                if memory.embedding:
                    memory_data['embedding'] = json.dumps(memory.embedding)

                await self.redis.hset(f"memory:{memory.memory_id}", mapping=memory_data)
                await self.redis.sadd(f"conversation_memories:{memory.conversation_id}", memory.memory_id)

            # Also store locally
            self.local_store[memory.memory_id] = memory

            logger.debug(f"Stored memory {memory.memory_id}")
            return True

        except Exception as e:
            logger.error(f"Error storing memory: {e}")
            return False

    async def get_memory(self, memory_id: str) -> Optional[MemoryEntry]:
        """Retrieve a specific memory."""
        # Check local store first
        if memory_id in self.local_store:
            memory = self.local_store[memory_id]
            memory.access_count += 1
            memory.last_accessed = datetime.utcnow()
            return memory

        # Try Redis
        if self.redis:
            try:
                data = await self.redis.hgetall(f"memory:{memory_id}")
                if data:
                    # Reconstruct memory
                    memory = MemoryEntry(
                        memory_id=memory_id,
                        content=data[b'content'].decode(),
                        memory_type=data[b'memory_type'].decode(),
                        conversation_id=data[b'conversation_id'].decode(),
                        timestamp=datetime.fromisoformat(data[b'timestamp'].decode()),
                        importance_score=float(data[b'importance_score']),
                        access_count=int(data[b'access_count']),
                        metadata=json.loads(data[b'metadata']),
                        tags=json.loads(data[b'tags'])
                    )

                    if b'embedding' in data:
                        memory.embedding = json.loads(data[b'embedding'])

                    # Update access tracking
                    memory.access_count += 1
                    memory.last_accessed = datetime.utcnow()
                    await self.redis.hincrby(f"memory:{memory_id}", 'access_count', 1)

                    # Cache locally
                    self.local_store[memory_id] = memory
                    return memory

            except Exception as e:
                logger.error(f"Error retrieving memory from Redis: {e}")

        return None

    async def get_conversation_memories(self, conversation_id: str,
                                       limit: Optional[int] = None) -> List[MemoryEntry]:
        """Get all memories for a conversation."""
        memories = []

        if self.redis:
            try:
                memory_ids = await self.redis.smembers(f"conversation_memories:{conversation_id}")
                for memory_id in memory_ids:
                    memory = await self.get_memory(memory_id.decode())
                    if memory:
                        memories.append(memory)
            except Exception as e:
                logger.error(f"Error getting conversation memories: {e}")

        # Also check local store
        local_memories = [
            m for m in self.local_store.values()
            if m.conversation_id == conversation_id
        ]
        memories.extend(local_memories)

        # Remove duplicates
        unique_memories = {m.memory_id: m for m in memories}.values()
        memories = list(unique_memories)

        # Sort by timestamp
        memories.sort(key=lambda m: m.timestamp, reverse=True)

        if limit:
            memories = memories[:limit]

        return memories

    async def store_summary(self, summary: ConversationSummary) -> bool:
        """Store a conversation summary."""
        try:
            self.summaries[summary.summary_id] = summary

            if self.redis:
                summary_data = {
                    'conversation_id': summary.conversation_id,
                    'summary_text': summary.summary_text,
                    'message_range': json.dumps(summary.message_range),
                    'tokens': summary.tokens,
                    'created_at': summary.created_at.isoformat(),
                    'key_points': json.dumps(summary.key_points),
                    'entities': json.dumps(summary.entities_mentioned),
                    'topics': json.dumps(summary.topics)
                }

                await self.redis.hset(f"summary:{summary.summary_id}", mapping=summary_data)
                await self.redis.sadd(f"conversation_summaries:{summary.conversation_id}", summary.summary_id)

            logger.debug(f"Stored summary {summary.summary_id}")
            return True

        except Exception as e:
            logger.error(f"Error storing summary: {e}")
            return False

    async def get_conversation_summaries(self, conversation_id: str) -> List[ConversationSummary]:
        """Get all summaries for a conversation."""
        summaries = []

        if self.redis:
            try:
                summary_ids = await self.redis.smembers(f"conversation_summaries:{conversation_id}")
                for summary_id in summary_ids:
                    data = await self.redis.hgetall(f"summary:{summary_id.decode()}")
                    if data:
                        summary = ConversationSummary(
                            summary_id=summary_id.decode(),
                            conversation_id=data[b'conversation_id'].decode(),
                            summary_text=data[b'summary_text'].decode(),
                            message_range=tuple(json.loads(data[b'message_range'])),
                            tokens=int(data[b'tokens']),
                            created_at=datetime.fromisoformat(data[b'created_at'].decode()),
                            key_points=json.loads(data[b'key_points']),
                            entities_mentioned=json.loads(data[b'entities']),
                            topics=json.loads(data[b'topics'])
                        )
                        summaries.append(summary)
            except Exception as e:
                logger.error(f"Error getting summaries: {e}")

        # Check local store
        local_summaries = [
            s for s in self.summaries.values()
            if s.conversation_id == conversation_id
        ]
        summaries.extend(local_summaries)

        # Remove duplicates and sort
        unique_summaries = {s.summary_id: s for s in summaries}.values()
        summaries = list(unique_summaries)
        summaries.sort(key=lambda s: s.message_range[0])

        return summaries


class ConversationSummarizer:
    """Generates summaries of conversations."""

    def __init__(self, embedding_service: EmbeddingService):
        self.embedding_service = embedding_service

    async def summarize_messages(self, messages: List[Message],
                                conversation_id: str,
                                message_range: Tuple[int, int]) -> ConversationSummary:
        """Create a summary of messages."""
        # Extract content
        message_contents = [f"{msg.role.value}: {msg.content}" for msg in messages]
        full_text = "\n".join(message_contents)

        # In production, this would use an LLM to generate summary
        # For now, create a simple summary
        summary_text = await self._generate_summary(messages)

        # Extract key points (simplified)
        key_points = await self._extract_key_points(messages)

        # Extract entities (simplified)
        entities = await self._extract_entities(messages)

        # Extract topics (simplified)
        topics = await self._extract_topics(messages)

        # Count tokens (rough estimate)
        tokens = len(summary_text.split()) * 1.3

        summary_id = f"{conversation_id}_summary_{message_range[0]}_{message_range[1]}"

        return ConversationSummary(
            summary_id=summary_id,
            conversation_id=conversation_id,
            summary_text=summary_text,
            message_range=message_range,
            tokens=int(tokens),
            created_at=datetime.utcnow(),
            key_points=key_points,
            entities_mentioned=entities,
            topics=topics
        )

    async def _generate_summary(self, messages: List[Message]) -> str:
        """Generate summary text."""
        # Simplified summary generation
        user_messages = [m for m in messages if m.role == MessageRole.USER]
        assistant_messages = [m for m in messages if m.role == MessageRole.ASSISTANT]

        summary_parts = []

        if user_messages:
            summary_parts.append(f"User discussed: {user_messages[0].content[:100]}...")

        if assistant_messages:
            summary_parts.append(f"Assistant responded with: {assistant_messages[0].content[:100]}...")

        summary_parts.append(f"Total {len(messages)} messages exchanged.")

        return " ".join(summary_parts)

    async def _extract_key_points(self, messages: List[Message]) -> List[str]:
        """Extract key points from messages."""
        # Simplified extraction
        key_points = []
        for msg in messages[:3]:  # Take first 3 messages
            if len(msg.content) > 50:
                key_points.append(msg.content[:80] + "...")

        return key_points

    async def _extract_entities(self, messages: List[Message]) -> List[str]:
        """Extract named entities."""
        # Simplified - would use NER in production
        entities = set()
        for msg in messages:
            # Simple capitalized word detection
            words = msg.content.split()
            for word in words:
                if word and word[0].isupper() and len(word) > 3:
                    entities.add(word.strip('.,!?'))

        return list(entities)[:10]  # Top 10

    async def _extract_topics(self, messages: List[Message]) -> List[str]:
        """Extract main topics."""
        # Simplified - would use topic modeling in production
        word_freq = defaultdict(int)
        for msg in messages:
            words = msg.content.lower().split()
            for word in words:
                if len(word) > 4:  # Skip short words
                    word_freq[word] += 1

        # Get top words as topics
        topics = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)[:5]
        return [topic[0] for topic in topics]


class MemoryRetriever:
    """Retrieves relevant memories for context augmentation."""

    def __init__(self, memory_store: MemoryStore, embedding_service: EmbeddingService):
        self.memory_store = memory_store
        self.embedding_service = embedding_service

    async def retrieve_relevant_memories(self, query: str,
                                        conversation_id: Optional[str] = None,
                                        max_memories: int = 5,
                                        min_relevance: float = 0.7) -> RetrievalResult:
        """Retrieve memories relevant to a query."""
        # Generate query embedding
        query_embedding = await self.embedding_service.embed(query)

        # Get candidate memories
        if conversation_id:
            candidates = await self.memory_store.get_conversation_memories(conversation_id)
        else:
            # Get all memories (limited)
            candidates = list(self.memory_store.local_store.values())[:100]

        # Calculate relevance scores
        relevant_memories = []
        relevance_scores = []

        for memory in candidates:
            if not memory.embedding:
                # Generate embedding if missing
                memory.embedding = await self.embedding_service.embed(memory.content)

            # Calculate cosine similarity
            similarity = self._cosine_similarity(query_embedding, memory.embedding)

            if similarity >= min_relevance:
                relevant_memories.append(memory)
                relevance_scores.append(similarity)

        # Sort by relevance
        sorted_results = sorted(
            zip(relevant_memories, relevance_scores),
            key=lambda x: x[1],
            reverse=True
        )

        # Take top N
        top_memories = [m for m, _ in sorted_results[:max_memories]]
        top_scores = [s for _, s in sorted_results[:max_memories]]

        # Calculate total tokens
        total_tokens = sum(len(m.content.split()) * 1.3 for m in top_memories)

        return RetrievalResult(
            memories=top_memories,
            relevance_scores=top_scores,
            total_tokens=int(total_tokens),
            retrieval_strategy="semantic_search"
        )

    def _cosine_similarity(self, embedding1: List[float], embedding2: List[float]) -> float:
        """Calculate cosine similarity between embeddings."""
        vec1 = np.array(embedding1).reshape(1, -1)
        vec2 = np.array(embedding2).reshape(1, -1)
        return float(cosine_similarity(vec1, vec2)[0][0])

    async def retrieve_temporal_memories(self, conversation_id: str,
                                        time_window_hours: int = 24,
                                        max_memories: int = 10) -> List[MemoryEntry]:
        """Retrieve memories from a time window."""
        cutoff_time = datetime.utcnow() - timedelta(hours=time_window_hours)

        memories = await self.memory_store.get_conversation_memories(conversation_id)

        # Filter by time
        recent_memories = [
            m for m in memories
            if m.timestamp >= cutoff_time
        ]

        # Sort by timestamp (most recent first)
        recent_memories.sort(key=lambda m: m.timestamp, reverse=True)

        return recent_memories[:max_memories]


class LongTermMemorySystem:
    """Main long-term memory system integrating all components."""

    def __init__(self, redis_client: Optional[redis.Redis] = None):
        self.embedding_service = EmbeddingService()
        self.memory_store = MemoryStore(redis_client)
        self.summarizer = ConversationSummarizer(self.embedding_service)
        self.retriever = MemoryRetriever(self.memory_store, self.embedding_service)

        self.auto_summarize_threshold = 50  # Summarize every N messages
        self.memory_consolidation_interval = 3600  # 1 hour

    async def process_conversation(self, context: ConversationContext):
        """Process conversation to extract and store memories."""
        # Extract facts and entities from recent messages
        recent_messages = context.messages[-10:]  # Last 10 messages

        for msg in recent_messages:
            if msg.role == MessageRole.ASSISTANT:
                # Extract memories from assistant responses
                await self._extract_memories(msg, context.conversation_id)

        # Auto-summarize if threshold reached
        if len(context.messages) % self.auto_summarize_threshold == 0:
            await self._auto_summarize(context)

    async def _extract_memories(self, message: Message, conversation_id: str):
        """Extract memorable facts from a message."""
        # Simplified extraction - would use NLP in production
        if len(message.content) > 100:
            memory_id = f"{conversation_id}_mem_{message.message_id}"

            # Generate embedding
            embedding = await self.embedding_service.embed(message.content)

            memory = MemoryEntry(
                memory_id=memory_id,
                content=message.content,
                memory_type="fact",
                conversation_id=conversation_id,
                timestamp=message.timestamp,
                embedding=embedding,
                importance_score=0.7,
                metadata={'source_message': message.message_id}
            )

            await self.memory_store.store_memory(memory)

    async def _auto_summarize(self, context: ConversationContext):
        """Automatically summarize conversation segments."""
        total_messages = len(context.messages)
        last_summary_index = 0

        # Check if we already have summaries
        summaries = await self.memory_store.get_conversation_summaries(context.conversation_id)
        if summaries:
            last_summary_index = max(s.message_range[1] for s in summaries)

        # Summarize messages since last summary
        if total_messages - last_summary_index >= self.auto_summarize_threshold:
            messages_to_summarize = context.messages[last_summary_index:total_messages]

            summary = await self.summarizer.summarize_messages(
                messages_to_summarize,
                context.conversation_id,
                (last_summary_index, total_messages)
            )

            await self.memory_store.store_summary(summary)
            logger.info(f"Created summary for messages {last_summary_index}-{total_messages}")

    async def augment_context_with_memories(self, query: str,
                                           conversation_id: str,
                                           max_token_budget: int = 500) -> List[MemoryEntry]:
        """Retrieve and format relevant memories for context."""
        # Retrieve relevant memories
        result = await self.retriever.retrieve_relevant_memories(
            query,
            conversation_id,
            max_memories=10,
            min_relevance=0.6
        )

        # Filter to fit token budget
        selected_memories = []
        current_tokens = 0

        for memory, score in zip(result.memories, result.relevance_scores):
            memory_tokens = len(memory.content.split()) * 1.3
            if current_tokens + memory_tokens <= max_token_budget:
                selected_memories.append(memory)
                current_tokens += memory_tokens
            else:
                break

        logger.info(f"Augmented context with {len(selected_memories)} memories ({int(current_tokens)} tokens)")

        return selected_memories

    async def get_conversation_insights(self, conversation_id: str) -> Dict[str, Any]:
        """Get insights about a conversation."""
        # Get summaries
        summaries = await self.memory_store.get_conversation_summaries(conversation_id)

        # Get memories
        memories = await self.memory_store.get_conversation_memories(conversation_id, limit=100)

        # Aggregate topics
        all_topics = []
        for summary in summaries:
            all_topics.extend(summary.topics)

        topic_counts = defaultdict(int)
        for topic in all_topics:
            topic_counts[topic] += 1

        top_topics = sorted(topic_counts.items(), key=lambda x: x[1], reverse=True)[:5]

        # Aggregate entities
        all_entities = []
        for summary in summaries:
            all_entities.extend(summary.entities_mentioned)

        entity_counts = defaultdict(int)
        for entity in all_entities:
            entity_counts[entity] += 1

        top_entities = sorted(entity_counts.items(), key=lambda x: x[1], reverse=True)[:10]

        return {
            'conversation_id': conversation_id,
            'total_summaries': len(summaries),
            'total_memories': len(memories),
            'top_topics': [{'topic': t, 'count': c} for t, c in top_topics],
            'top_entities': [{'entity': e, 'count': c} for e, c in top_entities],
            'memory_types': self._count_memory_types(memories)
        }

    def _count_memory_types(self, memories: List[MemoryEntry]) -> Dict[str, int]:
        """Count memories by type."""
        type_counts = defaultdict(int)
        for memory in memories:
            type_counts[memory.memory_type] += 1
        return dict(type_counts)


# Global memory system
long_term_memory: Optional[LongTermMemorySystem] = None