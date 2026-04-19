#!/usr/bin/env python3
"""
Contextual Awareness System for Hermes AI Assistant
Advanced context understanding based on user interaction history
"""

import asyncio
import logging
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass, field
from enum import Enum
import json
import time
from datetime import datetime, timedelta
import uuid
import re
from collections import defaultdict, deque

logger = logging.getLogger(__name__)

class ContextType(Enum):
    """Types of context that can be tracked"""
    CONVERSATIONAL = "conversational"
    TEMPORAL = "temporal"
    TOPICAL = "topical"
    BEHAVIORAL = "behavioral"
    EMOTIONAL = "emotional"
    PREFERENCE = "preference"
    ENVIRONMENTAL = "environmental"

class ContextRelevance(Enum):
    """Relevance levels for context"""
    IMMEDIATE = "immediate"      # Current interaction
    RECENT = "recent"           # Last few interactions
    SESSION = "session"         # Current session
    HISTORICAL = "historical"   # Long-term patterns
    SEASONAL = "seasonal"       # Time-based patterns

@dataclass
class ContextSignal:
    """A single context signal from user interaction"""
    signal_id: str
    user_id: str
    timestamp: datetime
    context_type: ContextType
    relevance: ContextRelevance
    data: Dict[str, Any]
    confidence: float
    extracted_from: str  # Source of the signal (message, response, metadata)
    decay_factor: float = 1.0  # How quickly this signal decays

@dataclass
class ContextSnapshot:
    """A snapshot of user's context at a point in time"""
    snapshot_id: str
    user_id: str
    timestamp: datetime
    active_topics: List[str]
    emotional_state: Optional[str]
    conversation_state: Dict[str, Any]
    behavioral_patterns: Dict[str, Any]
    preferences_state: Dict[str, Any]
    environmental_factors: Dict[str, Any]
    confidence_score: float

@dataclass
class ContextualInsight:
    """Insight derived from contextual analysis"""
    insight_id: str
    user_id: str
    insight_type: str
    description: str
    confidence: float
    supporting_signals: List[str]
    timestamp: datetime
    actionable: bool = False
    suggested_actions: List[str] = field(default_factory=list)

class ContextualAwarenessEngine:
    """Advanced contextual awareness engine"""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.max_history_size = config.get("max_history_size", 1000)
        self.context_decay_rate = config.get("context_decay_rate", 0.1)
        self.insight_threshold = config.get("insight_threshold", 0.7)
        self.session_timeout = config.get("session_timeout", 3600)  # 1 hour

        # Context storage
        self.context_signals: Dict[str, deque] = defaultdict(lambda: deque(maxlen=self.max_history_size))
        self.context_snapshots: Dict[str, deque] = defaultdict(lambda: deque(maxlen=100))
        self.user_sessions: Dict[str, Dict[str, Any]] = {}
        self.contextual_insights: Dict[str, List[ContextualInsight]] = defaultdict(list)

        # Context analysis patterns
        self.topic_extractors = self._initialize_topic_extractors()
        self.emotion_indicators = self._initialize_emotion_indicators()
        self.behavioral_patterns = self._initialize_behavioral_patterns()
        self.temporal_patterns = self._initialize_temporal_patterns()

        # State tracking
        self.user_states: Dict[str, Dict[str, Any]] = {}

    async def process_interaction_context(
        self,
        user_id: str,
        message: str,
        response: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Process interaction to extract and update contextual information

        Args:
            user_id: User identifier
            message: User's message
            response: AI's response
            metadata: Additional interaction metadata

        Returns:
            Context analysis results and updates
        """

        start_time = time.time()

        try:
            # Update user session
            session_info = await self._update_user_session(user_id, metadata)

            # Extract context signals
            signals = await self._extract_context_signals(user_id, message, response, metadata)

            # Process and store signals
            processed_signals = []
            for signal in signals:
                processed_signal = await self._process_context_signal(signal)
                self.context_signals[user_id].append(processed_signal)
                processed_signals.append(processed_signal)

            # Generate context snapshot
            snapshot = await self._generate_context_snapshot(user_id, processed_signals)
            self.context_snapshots[user_id].append(snapshot)

            # Derive contextual insights
            insights = await self._derive_contextual_insights(user_id, snapshot, processed_signals)
            for insight in insights:
                self.contextual_insights[user_id].append(insight)

            # Update user state
            await self._update_user_state(user_id, snapshot, insights)

            # Clean up old context
            await self._cleanup_old_context(user_id)

            processing_time = time.time() - start_time

            logger.info(f"Processed context for user {user_id} in {processing_time:.3f}s")

            return {
                "success": True,
                "user_id": user_id,
                "session_id": session_info.get("session_id"),
                "signals_extracted": len(processed_signals),
                "insights_generated": len(insights),
                "context_snapshot": {
                    "active_topics": snapshot.active_topics,
                    "emotional_state": snapshot.emotional_state,
                    "confidence_score": snapshot.confidence_score
                },
                "top_insights": [
                    {
                        "type": insight.insight_type,
                        "description": insight.description,
                        "confidence": insight.confidence
                    }
                    for insight in insights[:3]
                ],
                "processing_time": processing_time
            }

        except Exception as e:
            logger.error(f"Error processing context for user {user_id}: {e}")
            return {
                "success": False,
                "error": str(e),
                "user_id": user_id
            }

    async def get_contextual_understanding(
        self,
        user_id: str,
        query: Optional[str] = None,
        time_range: Optional[timedelta] = None
    ) -> Dict[str, Any]:
        """
        Get comprehensive contextual understanding for a user

        Args:
            user_id: User identifier
            query: Specific context query (optional)
            time_range: Time range for context analysis (optional)

        Returns:
            Comprehensive contextual understanding
        """

        try:
            # Get current context state
            current_state = self.user_states.get(user_id, {})

            # Get recent context signals
            recent_signals = list(self.context_signals[user_id])[-50:]  # Last 50 signals

            # Get latest context snapshot
            latest_snapshot = None
            if self.context_snapshots[user_id]:
                latest_snapshot = self.context_snapshots[user_id][-1]

            # Get relevant insights
            relevant_insights = self.contextual_insights[user_id][-20:]  # Last 20 insights

            # Analyze temporal patterns
            temporal_analysis = await self._analyze_temporal_patterns(user_id, time_range)

            # Analyze behavioral patterns
            behavioral_analysis = await self._analyze_behavioral_patterns(user_id)

            # Analyze topic evolution
            topic_evolution = await self._analyze_topic_evolution(user_id)

            # Generate contextual recommendations
            recommendations = await self._generate_contextual_recommendations(user_id)

            return {
                "user_id": user_id,
                "current_state": current_state,
                "latest_snapshot": {
                    "timestamp": latest_snapshot.timestamp.isoformat() if latest_snapshot else None,
                    "active_topics": latest_snapshot.active_topics if latest_snapshot else [],
                    "emotional_state": latest_snapshot.emotional_state if latest_snapshot else None,
                    "confidence_score": latest_snapshot.confidence_score if latest_snapshot else 0.0
                },
                "temporal_analysis": temporal_analysis,
                "behavioral_analysis": behavioral_analysis,
                "topic_evolution": topic_evolution,
                "recent_insights": [
                    {
                        "type": insight.insight_type,
                        "description": insight.description,
                        "confidence": insight.confidence,
                        "timestamp": insight.timestamp.isoformat(),
                        "actionable": insight.actionable
                    }
                    for insight in relevant_insights
                ],
                "recommendations": recommendations,
                "signal_count": len(recent_signals),
                "insight_count": len(relevant_insights)
            }

        except Exception as e:
            logger.error(f"Error getting contextual understanding for user {user_id}: {e}")
            return {
                "user_id": user_id,
                "error": str(e)
            }

    async def predict_next_interaction_context(
        self,
        user_id: str
    ) -> Dict[str, Any]:
        """
        Predict the context of the next user interaction

        Args:
            user_id: User identifier

        Returns:
            Predicted context for next interaction
        """

        try:
            # Get historical patterns
            behavioral_patterns = await self._analyze_behavioral_patterns(user_id)
            temporal_patterns = await self._analyze_temporal_patterns(user_id)

            # Get recent context
            recent_signals = list(self.context_signals[user_id])[-10:]
            latest_snapshot = self.context_snapshots[user_id][-1] if self.context_snapshots[user_id] else None

            # Predict likely topics
            predicted_topics = await self._predict_next_topics(user_id, recent_signals)

            # Predict likely emotional state
            predicted_emotion = await self._predict_next_emotional_state(user_id, recent_signals)

            # Predict interaction type
            predicted_interaction_type = await self._predict_next_interaction_type(user_id, behavioral_patterns)

            # Predict response preferences
            predicted_preferences = await self._predict_next_preferences(user_id, latest_snapshot)

            # Calculate prediction confidence
            prediction_confidence = await self._calculate_prediction_confidence(
                user_id, recent_signals, behavioral_patterns
            )

            return {
                "user_id": user_id,
                "prediction_timestamp": datetime.utcnow().isoformat(),
                "predicted_topics": predicted_topics,
                "predicted_emotional_state": predicted_emotion,
                "predicted_interaction_type": predicted_interaction_type,
                "predicted_preferences": predicted_preferences,
                "confidence_score": prediction_confidence,
                "based_on_signals": len(recent_signals),
                "recommendations": [
                    "Prepare for questions about " + topic for topic in predicted_topics[:2]
                ]
            }

        except Exception as e:
            logger.error(f"Error predicting next interaction context for user {user_id}: {e}")
            return {
                "user_id": user_id,
                "error": str(e),
                "confidence_score": 0.0
            }

    async def _update_user_session(
        self,
        user_id: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Update user session information"""

        current_time = datetime.utcnow()

        if user_id not in self.user_sessions:
            # Create new session
            session_info = {
                "session_id": str(uuid.uuid4()),
                "start_time": current_time,
                "last_activity": current_time,
                "interaction_count": 0,
                "session_duration": 0,
                "device_type": metadata.get("device_type") if metadata else "unknown",
                "location": metadata.get("location") if metadata else "unknown"
            }
            self.user_sessions[user_id] = session_info
        else:
            session_info = self.user_sessions[user_id]

            # Check if session has timed out
            if (current_time - session_info["last_activity"]).seconds > self.session_timeout:
                # Create new session
                session_info = {
                    "session_id": str(uuid.uuid4()),
                    "start_time": current_time,
                    "last_activity": current_time,
                    "interaction_count": 0,
                    "session_duration": 0,
                    "device_type": metadata.get("device_type") if metadata else session_info["device_type"],
                    "location": metadata.get("location") if metadata else session_info["location"]
                }
                self.user_sessions[user_id] = session_info

        # Update session activity
        session_info["last_activity"] = current_time
        session_info["interaction_count"] += 1
        session_info["session_duration"] = (current_time - session_info["start_time"]).seconds

        return session_info

    async def _extract_context_signals(
        self,
        user_id: str,
        message: str,
        response: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> List[ContextSignal]:
        """Extract context signals from interaction"""

        signals = []
        current_time = datetime.utcnow()

        # Extract topic signals
        topic_signals = await self._extract_topic_signals(user_id, message, response, current_time)
        signals.extend(topic_signals)

        # Extract emotional signals
        emotion_signals = await self._extract_emotional_signals(user_id, message, current_time)
        signals.extend(emotion_signals)

        # Extract behavioral signals
        behavior_signals = await self._extract_behavioral_signals(user_id, message, response, metadata, current_time)
        signals.extend(behavior_signals)

        # Extract temporal signals
        temporal_signals = await self._extract_temporal_signals(user_id, current_time, metadata)
        signals.extend(temporal_signals)

        # Extract preference signals
        preference_signals = await self._extract_preference_signals(user_id, message, response, current_time)
        signals.extend(preference_signals)

        return signals

    async def _extract_topic_signals(
        self,
        user_id: str,
        message: str,
        response: str,
        timestamp: datetime
    ) -> List[ContextSignal]:
        """Extract topic-related context signals"""

        signals = []
        combined_text = f"{message} {response}"

        # Extract topics using patterns
        topics = []
        for category, patterns in self.topic_extractors.items():
            for pattern in patterns:
                matches = re.findall(pattern, combined_text, re.IGNORECASE)
                if matches:
                    topics.append((category, matches[0]))

        # Create topic signals
        for category, topic in topics:
            signal = ContextSignal(
                signal_id=str(uuid.uuid4()),
                user_id=user_id,
                timestamp=timestamp,
                context_type=ContextType.TOPICAL,
                relevance=ContextRelevance.RECENT,
                data={
                    "topic": topic,
                    "category": category,
                    "source_text": combined_text[:200]  # First 200 chars
                },
                confidence=0.8,
                decay_factor=0.2,  # Topics decay relatively slowly
                extracted_from="message_response"
            )
            signals.append(signal)

        return signals

    async def _extract_emotional_signals(
        self,
        user_id: str,
        message: str,
        timestamp: datetime
    ) -> List[ContextSignal]:
        """Extract emotional context signals"""

        signals = []
        message_lower = message.lower()

        # Detect emotions using indicators
        for emotion, indicators in self.emotion_indicators.items():
            score = 0
            matched_indicators = []

            for indicator in indicators["words"]:
                if indicator in message_lower:
                    score += 1
                    matched_indicators.append(indicator)

            for indicator in indicators["phrases"]:
                if indicator in message_lower:
                    score += 2  # Phrases weight more
                    matched_indicators.append(indicator)

            if score > 0:
                signal = ContextSignal(
                    signal_id=str(uuid.uuid4()),
                    user_id=user_id,
                    timestamp=timestamp,
                    context_type=ContextType.EMOTIONAL,
                    relevance=ContextRelevance.IMMEDIATE,
                    data={
                        "emotion": emotion,
                        "intensity": min(score / 3.0, 1.0),
                        "indicators": matched_indicators,
                        "message_length": len(message.split())
                    },
                    confidence=min(score / 3.0, 1.0),
                    decay_factor=0.3,  # Emotions decay moderately
                    extracted_from="message"
                )
                signals.append(signal)

        return signals

    async def _extract_behavioral_signals(
        self,
        user_id: str,
        message: str,
        response: str,
        metadata: Optional[Dict[str, Any]],
        timestamp: datetime
    ) -> List[ContextSignal]:
        """Extract behavioral context signals"""

        signals = []

        # Message length pattern
        message_length = len(message.split())
        signal = ContextSignal(
            signal_id=str(uuid.uuid4()),
            user_id=user_id,
            timestamp=timestamp,
            context_type=ContextType.BEHAVIORAL,
            relevance=ContextRelevance.RECENT,
            data={
                "behavior_type": "message_length",
                "value": message_length,
                "pattern": self._categorize_message_length(message_length)
            },
            confidence=0.9,
            decay_factor=0.1,
            extracted_from="message"
        )
        signals.append(signal)

        # Question asking pattern
        question_count = message.count('?')
        if question_count > 0:
            signal = ContextSignal(
                signal_id=str(uuid.uuid4()),
                user_id=user_id,
                timestamp=timestamp,
                context_type=ContextType.BEHAVIORAL,
                relevance=ContextRelevance.IMMEDIATE,
                data={
                    "behavior_type": "question_asking",
                    "question_count": question_count,
                    "pattern": "inquiring" if question_count > 1 else "single_question"
                },
                confidence=0.95,
                decay_factor=0.2,
                extracted_from="message"
            )
            signals.append(signal)

        # Response engagement (from metadata if available)
        if metadata and metadata.get("duration"):
            response_time = metadata["duration"]
            signal = ContextSignal(
                signal_id=str(uuid.uuid4()),
                user_id=user_id,
                timestamp=timestamp,
                context_type=ContextType.BEHAVIORAL,
                relevance=ContextRelevance.RECENT,
                data={
                    "behavior_type": "response_engagement",
                    "response_time": response_time,
                    "pattern": self._categorize_response_time(response_time)
                },
                confidence=0.8,
                decay_factor=0.15,
                extracted_from="metadata"
            )
            signals.append(signal)

        return signals

    async def _extract_temporal_signals(
        self,
        user_id: str,
        timestamp: datetime,
        metadata: Optional[Dict[str, Any]] = None
    ) -> List[ContextSignal]:
        """Extract temporal context signals"""

        signals = []

        # Time of day pattern
        hour = timestamp.hour
        time_period = self._categorize_time_period(hour)

        signal = ContextSignal(
            signal_id=str(uuid.uuid4()),
            user_id=user_id,
            timestamp=timestamp,
            context_type=ContextType.TEMPORAL,
            relevance=ContextRelevance.SESSION,
            data={
                "temporal_type": "time_of_day",
                "hour": hour,
                "period": time_period,
                "day_of_week": timestamp.weekday()
            },
            confidence=1.0,
            decay_factor=0.05,  # Time patterns decay slowly
            extracted_from="timestamp"
        )
        signals.append(signal)

        # Day of week pattern
        day_of_week = timestamp.weekday()
        day_type = "weekday" if day_of_week < 5 else "weekend"

        signal = ContextSignal(
            signal_id=str(uuid.uuid4()),
            user_id=user_id,
            timestamp=timestamp,
            context_type=ContextType.TEMPORAL,
            relevance=ContextRelevance.SESSION,
            data={
                "temporal_type": "day_type",
                "day_of_week": day_of_week,
                "day_type": day_type
            },
            confidence=1.0,
            decay_factor=0.05,
            extracted_from="timestamp"
        )
        signals.append(signal)

        return signals

    async def _extract_preference_signals(
        self,
        user_id: str,
        message: str,
        response: str,
        timestamp: datetime
    ) -> List[ContextSignal]:
        """Extract preference-related context signals"""

        signals = []

        # Length preference indicators
        if "shorter" in message.lower() or "brief" in message.lower():
            signal = ContextSignal(
                signal_id=str(uuid.uuid4()),
                user_id=user_id,
                timestamp=timestamp,
                context_type=ContextType.PREFERENCE,
                relevance=ContextRelevance.RECENT,
                data={
                    "preference_type": "response_length",
                    "preference": "shorter",
                    "indicators": ["explicit_request"]
                },
                confidence=0.9,
                decay_factor=0.1,
                extracted_from="message"
            )
            signals.append(signal)

        elif "more detail" in message.lower() or "explain further" in message.lower():
            signal = ContextSignal(
                signal_id=str(uuid.uuid4()),
                user_id=user_id,
                timestamp=timestamp,
                context_type=ContextType.PREFERENCE,
                relevance=ContextRelevance.RECENT,
                data={
                    "preference_type": "response_length",
                    "preference": "more_detailed",
                    "indicators": ["explicit_request"]
                },
                confidence=0.9,
                decay_factor=0.1,
                extracted_from="message"
            )
            signals.append(signal)

        return signals

    async def _process_context_signal(self, signal: ContextSignal) -> ContextSignal:
        """Process and enhance a context signal"""

        # Apply time-based decay to confidence
        age = (datetime.utcnow() - signal.timestamp).total_seconds()
        age_hours = age / 3600

        # Reduce confidence based on age and decay factor
        decayed_confidence = signal.confidence * (1 - signal.decay_factor) ** age_hours
        signal.confidence = max(0.1, decayed_confidence)  # Minimum confidence

        return signal

    async def _generate_context_snapshot(
        self,
        user_id: str,
        signals: List[ContextSignal]
    ) -> ContextSnapshot:
        """Generate a context snapshot from signals"""

        current_time = datetime.utcnow()

        # Aggregate active topics
        active_topics = []
        topic_weights = defaultdict(float)
        for signal in signals:
            if signal.context_type == ContextType.TOPICAL:
                topic = signal.data.get("topic")
                if topic:
                    topic_weights[topic] += signal.confidence

        # Get top topics
        active_topics = [topic for topic, weight in sorted(topic_weights.items(), key=lambda x: x[1], reverse=True)[:5]]

        # Determine emotional state
        emotional_state = None
        emotion_weights = defaultdict(float)
        for signal in signals:
            if signal.context_type == ContextType.EMOTIONAL:
                emotion = signal.data.get("emotion")
                if emotion:
                    emotion_weights[emotion] += signal.confidence

        if emotion_weights:
            emotional_state = max(emotion_weights, key=emotion_weights.get)

        # Build conversation state
        conversation_state = {
            "signal_count": len(signals),
            "topic_count": len(active_topics),
            "emotional_signals": len([s for s in signals if s.context_type == ContextType.EMOTIONAL]),
            "behavioral_signals": len([s for s in signals if s.context_type == ContextType.BEHAVIORAL])
        }

        # Build behavioral patterns
        behavioral_patterns = {}
        for signal in signals:
            if signal.context_type == ContextType.BEHAVIORAL:
                behavior_type = signal.data.get("behavior_type")
                if behavior_type:
                    if behavior_type not in behavioral_patterns:
                        behavioral_patterns[behavior_type] = []
                    behavioral_patterns[behavior_type].append(signal.data)

        # Calculate overall confidence score
        if signals:
            confidence_score = sum(s.confidence for s in signals) / len(signals)
        else:
            confidence_score = 0.0

        return ContextSnapshot(
            snapshot_id=str(uuid.uuid4()),
            user_id=user_id,
            timestamp=current_time,
            active_topics=active_topics,
            emotional_state=emotional_state,
            conversation_state=conversation_state,
            behavioral_patterns=behavioral_patterns,
            preferences_state={},
            environmental_factors={},
            confidence_score=confidence_score
        )

    async def _derive_contextual_insights(
        self,
        user_id: str,
        snapshot: ContextSnapshot,
        signals: List[ContextSignal]
    ) -> List[ContextualInsight]:
        """Derive insights from context snapshot and signals"""

        insights = []

        # Topic consistency insight
        if len(snapshot.active_topics) > 0:
            recent_topics = [s.data.get("topic") for s in signals if s.context_type == ContextType.TOPICAL and s.data.get("topic")]
            if len(set(recent_topics)) <= 2 and len(recent_topics) > 3:
                insight = ContextualInsight(
                    insight_id=str(uuid.uuid4()),
                    user_id=user_id,
                    insight_type="topic_consistency",
                    description=f"User is consistently discussing topics: {', '.join(snapshot.active_topics[:3])}",
                    confidence=0.8,
                    supporting_signals=[s.signal_id for s in signals if s.context_type == ContextType.TOPICAL],
                    timestamp=datetime.utcnow(),
                    actionable=True,
                    suggested_actions=[f"Prepare more content about {snapshot.active_topics[0]}"]
                )
                insights.append(insight)

        # Emotional pattern insight
        if snapshot.emotional_state:
            emotion_signals = [s for s in signals if s.context_type == ContextType.EMOTIONAL and s.data.get("emotion") == snapshot.emotional_state]
            if len(emotion_signals) > 2:
                insight = ContextualInsight(
                    insight_id=str(uuid.uuid4()),
                    user_id=user_id,
                    insight_type="emotional_pattern",
                    description=f"User is showing consistent {snapshot.emotional_state} emotional state",
                    confidence=0.7,
                    supporting_signals=[s.signal_id for s in emotion_signals],
                    timestamp=datetime.utcnow(),
                    actionable=True,
                    suggested_actions=[f"Maintain {snapshot.emotional_state}-appropriate tone"]
                )
                insights.append(insight)

        # Behavioral pattern insight
        question_signals = [s for s in signals if s.context_type == ContextType.BEHAVIORAL and s.data.get("behavior_type") == "question_asking"]
        if len(question_signals) > 3:
            insight = ContextualInsight(
                insight_id=str(uuid.uuid4()),
                user_id=user_id,
                insight_type="question_pattern",
                description="User is asking many questions - indicates high engagement or confusion",
                confidence=0.75,
                supporting_signals=[s.signal_id for s in question_signals],
                timestamp=datetime.utcnow(),
                actionable=True,
                suggested_actions=["Provide clear, structured answers", "Check if user needs clarification"]
            )
            insights.append(insight)

        return insights

    async def _update_user_state(
        self,
        user_id: str,
        snapshot: ContextSnapshot,
        insights: List[ContextualInsight]
    ) -> None:
        """Update user's current state based on snapshot and insights"""

        if user_id not in self.user_states:
            self.user_states[user_id] = {}

        state = self.user_states[user_id]

        # Update basic state information
        state["last_snapshot_id"] = snapshot.snapshot_id
        state["last_update"] = snapshot.timestamp.isoformat()
        state["active_topics"] = snapshot.active_topics
        state["emotional_state"] = snapshot.emotional_state
        state["confidence_score"] = snapshot.confidence_score

        # Update insight summary
        state["recent_insight_types"] = [insight.insight_type for insight in insights[-5:]]
        state["actionable_insights_count"] = len([i for i in insights if i.actionable])

        # Update behavioral summary
        if snapshot.behavioral_patterns:
            state["behavioral_summary"] = {
                behavior_type: len(patterns) for behavior_type, patterns in snapshot.behavioral_patterns.items()
            }

    async def _cleanup_old_context(self, user_id: str) -> None:
        """Clean up old context signals and snapshots"""

        current_time = datetime.utcnow()
        cutoff_time = current_time - timedelta(days=7)  # Keep 7 days of context

        # Clean old signals
        if user_id in self.context_signals:
            original_size = len(self.context_signals[user_id])
            self.context_signals[user_id] = deque(
                (s for s in self.context_signals[user_id] if s.timestamp > cutoff_time),
                maxlen=self.max_history_size
            )
            cleaned_count = original_size - len(self.context_signals[user_id])
            if cleaned_count > 0:
                logger.debug(f"Cleaned {cleaned_count} old context signals for user {user_id}")

        # Clean old insights
        if user_id in self.contextual_insights:
            original_size = len(self.contextual_insights[user_id])
            self.contextual_insights[user_id] = [
                insight for insight in self.contextual_insights[user_id]
                if insight.timestamp > cutoff_time
            ]
            cleaned_count = original_size - len(self.contextual_insights[user_id])
            if cleaned_count > 0:
                logger.debug(f"Cleaned {cleaned_count} old insights for user {user_id}")

    # Helper methods
    def _categorize_message_length(self, length: int) -> str:
        """Categorize message length"""
        if length <= 5:
            return "very_short"
        elif length <= 15:
            return "short"
        elif length <= 30:
            return "medium"
        elif length <= 50:
            return "long"
        else:
            return "very_long"

    def _categorize_response_time(self, response_time: float) -> str:
        """Categorize response time"""
        if response_time <= 2:
            return "very_fast"
        elif response_time <= 5:
            return "fast"
        elif response_time <= 10:
            return "normal"
        elif response_time <= 20:
            return "slow"
        else:
            return "very_slow"

    def _categorize_time_period(self, hour: int) -> str:
        """Categorize time of day"""
        if 5 <= hour < 12:
            return "morning"
        elif 12 <= hour < 17:
            return "afternoon"
        elif 17 <= hour < 21:
            return "evening"
        else:
            return "night"

    def _initialize_topic_extractors(self) -> Dict[str, List[str]]:
        """Initialize topic extraction patterns"""
        return {
            "technology": [r'\b(software|code|programming|API|database|algorithm)\b'],
            "business": [r'\b(company|market|revenue|customer|strategy|finance)\b'],
            "science": [r'\b(research|experiment|study|analysis|data|hypothesis)\b'],
            "education": [r'\b(learning|teaching|student|course|knowledge)\b'],
            "health": [r'\b(medical|health|patient|treatment|diagnosis)\b'],
            "personal": [r'\b(my|I|me|personal|feel|think)\b']
        }

    def _initialize_emotion_indicators(self) -> Dict[str, Dict[str, List[str]]]:
        """Initialize emotion detection indicators"""
        return {
            "happy": {
                "words": ["happy", "glad", "excited", "joyful", "great", "awesome", "wonderful"],
                "phrases": ["love it", "can't wait", "so excited", "really happy"]
            },
            "sad": {
                "words": ["sad", "unhappy", "disappointed", "depressed", "upset", "worried"],
                "phrases": ["feel sad", "so disappointed", "really upset", "worried about"]
            },
            "angry": {
                "words": ["angry", "mad", "frustrated", "annoyed", "irritated", "upset"],
                "phrases": ["so angry", "really frustrated", "can't believe", "so irritating"]
            },
            "confused": {
                "words": ["confused", "unclear", "unsure", "puzzled", "lost", "uncertain"],
                "phrases": ["don't understand", "not clear", "confused about", "unsure how"]
            },
            "excited": {
                "words": ["excited", "enthusiastic", "eager", "thrilled", "looking forward"],
                "phrases": ["so excited", "can't wait", "really looking forward", "thrilled about"]
            }
        }

    def _initialize_behavioral_patterns(self) -> Dict[str, Any]:
        """Initialize behavioral pattern detection"""
        return {
            "message_length_thresholds": {
                "very_short": 5,
                "short": 15,
                "medium": 30,
                "long": 50
            },
            "response_time_thresholds": {
                "very_fast": 2,
                "fast": 5,
                "normal": 10,
                "slow": 20
            }
        }

    def _initialize_temporal_patterns(self) -> Dict[str, Any]:
        """Initialize temporal pattern detection"""
        return {
            "time_periods": {
                "morning": (5, 12),
                "afternoon": (12, 17),
                "evening": (17, 21),
                "night": (21, 5)
            },
            "session_timeout": 3600  # 1 hour
        }

    # Analysis methods (simplified implementations)
    async def _analyze_temporal_patterns(self, user_id: str, time_range: Optional[timedelta] = None) -> Dict[str, Any]:
        """Analyze temporal patterns for user"""
        # Simplified implementation
        return {
            "most_active_time": "afternoon",
            "interaction_frequency": "daily",
            "session_duration_average": 15.5
        }

    async def _analyze_behavioral_patterns(self, user_id: str) -> Dict[str, Any]:
        """Analyze behavioral patterns for user"""
        # Simplified implementation
        return {
            "average_message_length": 25,
            "question_frequency": 0.3,
            "preferred_interaction_time": "morning"
        }

    async def _analyze_topic_evolution(self, user_id: str) -> Dict[str, Any]:
        """Analyze topic evolution over time"""
        # Simplified implementation
        return {
            "topic_stability": 0.7,
            "topic_transitions": ["technology", "business", "personal"],
            "emerging_topics": ["AI", "automation"]
        }

    async def _generate_contextual_recommendations(self, user_id: str) -> List[str]:
        """Generate contextual recommendations"""
        # Simplified implementation
        return [
            "Consider asking follow-up questions to deepen engagement",
            "User prefers detailed responses - provide comprehensive answers"
        ]

    async def _predict_next_topics(self, user_id: str, recent_signals: List[ContextSignal]) -> List[str]:
        """Predict next likely topics"""
        # Simplified implementation
        topic_signals = [s for s in recent_signals if s.context_type == ContextType.TOPICAL]
        if topic_signals:
            return [s.data.get("topic") for s in topic_signals[-3:]]
        return ["general"]

    async def _predict_next_emotional_state(self, user_id: str, recent_signals: List[ContextSignal]) -> Optional[str]:
        """Predict next emotional state"""
        # Simplified implementation
        emotion_signals = [s for s in recent_signals if s.context_type == ContextType.EMOTIONAL]
        if emotion_signals:
            return emotion_signals[-1].data.get("emotion")
        return None

    async def _predict_next_interaction_type(self, user_id: str, behavioral_patterns: Dict[str, Any]) -> str:
        """Predict next interaction type"""
        # Simplified implementation
        return "question"

    async def _predict_next_preferences(self, user_id: str, snapshot: Optional[ContextSnapshot]) -> Dict[str, Any]:
        """Predict next interaction preferences"""
        # Simplified implementation
        return {
            "response_length": "moderate",
            "tone": "friendly"
        }

    async def _calculate_prediction_confidence(
        self,
        user_id: str,
        recent_signals: List[ContextSignal],
        behavioral_patterns: Dict[str, Any]
    ) -> float:
        """Calculate confidence in predictions"""
        # Simplified implementation
        if len(recent_signals) > 10:
            return 0.8
        elif len(recent_signals) > 5:
            return 0.6
        else:
            return 0.4

# Global contextual awareness engine instance
contextual_awareness_engine: Optional[ContextualAwarenessEngine] = None

def initialize_contextual_awareness(config: Dict[str, Any]):
    """Initialize the global contextual awareness engine"""

    global contextual_awareness_engine
    contextual_awareness_engine = ContextualAwarenessEngine(config)
    logger.info("Contextual awareness engine initialized")

def get_contextual_awareness_engine() -> ContextualAwarenessEngine:
    """Get the global contextual awareness engine"""

    if contextual_awareness_engine is None:
        raise RuntimeError("Contextual awareness engine not initialized")

    return contextual_awareness_engine