#!/usr/bin/env python3
"""
User Profiler for Hermes AI Assistant
Advanced user preference learning and adaptation system
"""

import asyncio
import logging
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass, field, asdict
from enum import Enum
import json
import time
from datetime import datetime, timedelta
import uuid

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.cluster import KMeans

logger = logging.getLogger(__name__)

class UserPreferenceType(Enum):
    """Types of user preferences that can be learned"""
    COMMUNICATION_STYLE = "communication_style"
    RESPONSE_LENGTH = "response_length"
    TECHNICAL_LEVEL = "technical_level"
    TONE_PREFERENCE = "tone_preference"
    TOPIC_INTERESTS = "topic_interests"
    INTERACTION_PATTERNS = "interaction_patterns"
    LANGUAGE_STYLE = "language_style"
    CONTEXT_PREFERENCES = "context_preferences"

class CommunicationStyle(Enum):
    """User communication style categories"""
    FORMAL = "formal"
    CASUAL = "casual"
    TECHNICAL = "technical"
    CONVERSATIONAL = "conversational"
    CONCISE = "concise"
    DETAILED = "detailed"
    CREATIVE = "creative"
    ANALYTICAL = "analytical"

class ResponseLength(Enum):
    """Preferred response length categories"""
    BRIEF = "brief"          # 1-2 sentences
    MODERATE = "moderate"    # 3-5 sentences
    DETAILED = "detailed"    # 6-10 sentences
    COMPREHENSIVE = "comprehensive"  # 10+ sentences

class TechnicalLevel(Enum):
    """User technical expertise levels"""
    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"
    EXPERT = "expert"

class TonePreference(Enum):
    """Preferred response tones"""
    PROFESSIONAL = "professional"
    FRIENDLY = "friendly"
    ENTHUSIASTIC = "enthusiastic"
    CALM = "calm"
    HUMOROUS = "humorous"
    EMPATHETIC = "empathetic"
    DIRECT = "direct"
    SUPPORTIVE = "supportive"

@dataclass
class UserInteractionData:
    """Data from a single user interaction"""
    interaction_id: str
    user_id: str
    timestamp: datetime
    message_type: str  # question, statement, command, etc.
    message_content: str
    response_content: str
    response_length: int
    interaction_duration: float  # time to response
    user_feedback: Optional[int] = None  # 1-5 rating
    follow_up_questions: int = 0
    topic_category: Optional[str] = None
    technical_terms_count: int = 0
    emotional_indicators: List[str] = field(default_factory=list)
    context_keywords: List[str] = field(default_factory=list)

@dataclass
class UserPreference:
    """A learned user preference"""
    preference_type: UserPreferenceType
    value: Any
    confidence: float
    learned_at: datetime
    last_updated: datetime
    supporting_interactions: int
    examples: List[str] = field(default_factory=list)

@dataclass
class UserProfile:
    """Complete user profile with all learned preferences"""
    user_id: str
    created_at: datetime
    last_updated: datetime
    total_interactions: int
    preferences: Dict[UserPreferenceType, UserPreference] = field(default_factory=dict)
    interaction_history: List[UserInteractionData] = field(default_factory=list)
    topic_affinities: Dict[str, float] = field(default_factory=dict)
    communication_patterns: Dict[str, Any] = field(default_factory=dict)
    adaptation_history: List[Dict[str, Any]] = field(default_factory=dict)

class UserProfiler:
    """Advanced user profiling and preference learning system"""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.max_history_size = config.get("max_history_size", 1000)
        self.learning_threshold = config.get("learning_threshold", 0.7)
        self.adaptation_rate = config.get("adaptation_rate", 0.1)

        # Initialize ML components
        self.tfidf_vectorizer = TfidfVectorizer(
            max_features=1000,
            stop_words='english',
            ngram_range=(1, 2)
        )
        self.topic_clusterer = KMeans(n_clusters=10, random_state=42)

        # User profiles storage
        self.user_profiles: Dict[str, UserProfile] = {}
        self.interaction_buffer: List[UserInteractionData] = []

        # Pre-trained patterns
        self.formal_indicators = {
            "words": ["therefore", "furthermore", "consequently", "moreover"],
            "phrases": ["in conclusion", "it is important to note", "as previously mentioned"],
            "punctuation": [";", ":"]
        }

        self.casual_indicators = {
            "words": ["hey", "cool", "awesome", "totally", "definitely"],
            "phrases": ["by the way", "long story short", "no worries"],
            "punctuation": ["!", "??"]
        }

        self.technical_indicators = {
            "domains": ["algorithm", "database", "API", "framework", "architecture"],
            "terms": ["implement", "optimize", "scalability", "performance"],
            "patterns": ["r'^\w+\(\)$", "r'^\w+\.\w+$"]
        }

    async def process_interaction(
        self,
        user_id: str,
        message: str,
        response: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Process a user interaction and update user profile

        Args:
            user_id: Unique user identifier
            message: User's message
            response: AI's response
            metadata: Additional interaction metadata

        Returns:
            Processing results and preference updates
        """

        start_time = time.time()

        try:
            # Create interaction data
            interaction = await self._create_interaction_data(
                user_id, message, response, metadata
            )

            # Get or create user profile
            profile = await self._get_or_create_profile(user_id)

            # Analyze interaction for preference signals
            preference_signals = await self._analyze_interaction(interaction)

            # Update user preferences based on signals
            preference_updates = await self._update_preferences(
                profile, preference_signals, interaction
            )

            # Update topic affinities
            topic_updates = await self._update_topic_affinities(profile, interaction)

            # Update communication patterns
            pattern_updates = await self._update_communication_patterns(profile, interaction)

            # Store interaction in history
            profile.interaction_history.append(interaction)
            if len(profile.interaction_history) > self.max_history_size:
                profile.interaction_history = profile.interaction_history[-self.max_history_size:]

            # Update profile metadata
            profile.last_updated = datetime.utcnow()
            profile.total_interactions += 1

            # Record adaptation
            adaptation_record = {
                "timestamp": datetime.utcnow().isoformat(),
                "interaction_id": interaction.interaction_id,
                "preference_updates": len(preference_updates),
                "confidence_improvement": self._calculate_confidence_improvement(
                    preference_updates
                )
            }
            profile.adaptation_history.append(adaptation_record)

            processing_time = time.time() - start_time

            logger.info(f"Processed interaction for user {user_id} in {processing_time:.3f}s")

            return {
                "success": True,
                "user_id": user_id,
                "interaction_id": interaction.interaction_id,
                "preference_updates": preference_updates,
                "topic_updates": topic_updates,
                "pattern_updates": pattern_updates,
                "processing_time": processing_time,
                "current_preferences": self._get_current_preferences(profile)
            }

        except Exception as e:
            logger.error(f"Error processing interaction for user {user_id}: {e}")
            return {
                "success": False,
                "error": str(e),
                "user_id": user_id
            }

    async def _create_interaction_data(
        self,
        user_id: str,
        message: str,
        response: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> UserInteractionData:
        """Create structured interaction data from raw inputs"""

        return UserInteractionData(
            interaction_id=str(uuid.uuid4()),
            user_id=user_id,
            timestamp=datetime.utcnow(),
            message_type=self._detect_message_type(message),
            message_content=message,
            response_content=response,
            response_length=len(response.split()),
            interaction_duration=metadata.get("duration", 0.0) if metadata else 0.0,
            user_feedback=metadata.get("feedback") if metadata else None,
            follow_up_questions=metadata.get("follow_up_count", 0) if metadata else 0,
            topic_category=metadata.get("topic") if metadata else None,
            technical_terms_count=self._count_technical_terms(message + " " + response),
            emotional_indicators=self._detect_emotional_indicators(message),
            context_keywords=self._extract_context_keywords(message)
        )

    async def _analyze_interaction(
        self,
        interaction: UserInteractionData
    ) -> Dict[UserPreferenceType, Dict[str, Any]]:
        """Analyze interaction for preference signals"""

        signals = {}

        # Analyze communication style
        signals[UserPreferenceType.COMMUNICATION_STYLE] = await self._analyze_communication_style(
            interaction
        )

        # Analyze response length preference
        signals[UserPreferenceType.RESPONSE_LENGTH] = await self._analyze_response_length_preference(
            interaction
        )

        # Analyze technical level
        signals[UserPreferenceType.TECHNICAL_LEVEL] = await self._analyze_technical_level(
            interaction
        )

        # Analyze tone preference
        signals[UserPreferenceType.TONE_PREFERENCE] = await self._analyze_tone_preference(
            interaction
        )

        # Analyze topic interests
        signals[UserPreferenceType.TOPIC_INTERESTS] = await self._analyze_topic_interests(
            interaction
        )

        # Analyze language style
        signals[UserPreferenceType.LANGUAGE_STYLE] = await self._analyze_language_style(
            interaction
        )

        return signals

    async def _analyze_communication_style(
        self,
        interaction: UserInteractionData
    ) -> Dict[str, Any]:
        """Analyze user's communication style"""

        message = interaction.message_content.lower()

        style_scores = {
            CommunicationStyle.FORMAL: 0.0,
            CommunicationStyle.CASUAL: 0.0,
            CommunicationStyle.TECHNICAL: 0.0,
            CommunicationStyle.CONVERSATIONAL: 0.0,
            CommunicationStyle.CONCISE: 0.0,
            CommunicationStyle.DETAILED: 0.0,
            CommunicationStyle.CREATIVE: 0.0,
            CommunicationStyle.ANALYTICAL: 0.0
        }

        # Formal indicators
        formal_score = 0
        for indicator in self.formal_indicators["words"]:
            if indicator in message:
                formal_score += 1
        for phrase in self.formal_indicators["phrases"]:
            if phrase in message:
                formal_score += 2
        for punct in self.formal_indicators["punctuation"]:
            formal_score += message.count(punct)
        style_scores[CommunicationStyle.FORMAL] = formal_score

        # Casual indicators
        casual_score = 0
        for indicator in self.casual_indicators["words"]:
            if indicator in message:
                casual_score += 1
        for phrase in self.casual_indicators["phrases"]:
            if phrase in message:
                casual_score += 2
        for punct in self.casual_indicators["punctuation"]:
            casual_score += message.count(punct)
        style_scores[CommunicationStyle.CASUAL] = casual_score

        # Technical indicators
        technical_score = interaction.technical_terms_count
        for domain in self.technical_indicators["domains"]:
            if domain.lower() in message:
                technical_score += 2
        style_scores[CommunicationStyle.TECHNICAL] = technical_score

        # Conversational indicators
        conversational_score = 0
        if any(word in message for word in ["what", "how", "why", "when", "where"]):
            conversational_score += 1
        if message.endswith("?"):
            conversational_score += 1
        style_scores[CommunicationStyle.CONVERSATIONAL] = conversational_score

        # Concise vs Detailed
        if len(message.split()) < 10:
            style_scores[CommunicationStyle.CONCISE] = 1
        elif len(message.split()) > 30:
            style_scores[CommunicationStyle.DETAILED] = 1

        # Determine dominant style
        max_score = max(style_scores.values())
        if max_score > 0:
            dominant_style = max(style_scores, key=style_scores.get)
            confidence = min(max_score / 5.0, 1.0)
        else:
            dominant_style = CommunicationStyle.CONVERSATIONAL
            confidence = 0.5

        return {
            "style": dominant_style,
            "confidence": confidence,
            "all_scores": {style.value: score for style, score in style_scores.items()}
        }

    async def _analyze_response_length_preference(
        self,
        interaction: UserInteractionData
    ) -> Dict[str, Any]:
        """Analyze preferred response length based on user behavior"""

        # Use feedback and follow-up behavior as indicators
        if interaction.user_feedback is not None:
            # High feedback score suggests current length was good
            if interaction.user_feedback >= 4:
                if interaction.response_length <= 20:
                    preferred = ResponseLength.BRIEF
                elif interaction.response_length <= 50:
                    preferred = ResponseLength.MODERATE
                elif interaction.response_length <= 100:
                    preferred = ResponseLength.DETAILED
                else:
                    preferred = ResponseLength.COMPREHENSIVE
                confidence = 0.8
            else:
                # Low feedback suggests length was not ideal
                if interaction.response_length <= 20:
                    preferred = ResponseLength.MODERATE  # Too brief
                elif interaction.response_length <= 50:
                    preferred = ResponseLength.DETAILED  # Too short
                else:
                    preferred = ResponseLength.MODERATE  # Too long
                confidence = 0.6
        else:
            # Use follow-up questions as indicator
            if interaction.follow_up_questions == 0:
                # No follow-ups suggests response was sufficient
                preferred = ResponseLength.MODERATE
                confidence = 0.5
            elif interaction.follow_up_questions > 2:
                # Many follow-ups suggest response was insufficient
                preferred = ResponseLength.DETAILED
                confidence = 0.6
            else:
                preferred = ResponseLength.MODERATE
                confidence = 0.4

        return {
            "preferred_length": preferred,
            "confidence": confidence,
            "based_on": "feedback" if interaction.user_feedback else "follow_up_behavior"
        }

    async def _analyze_technical_level(
        self,
        interaction: UserInteractionData
    ) -> Dict[str, Any]:
        """Analyze user's technical expertise level"""

        message = interaction.message_content.lower()
        tech_score = interaction.technical_terms_count

        # Look for complexity indicators
        complexity_indicators = {
            "beginner": ["help", "explain", "what is", "how do", "basic", "simple"],
            "intermediate": ["implement", "optimize", "improve", "best practice"],
            "advanced": ["architecture", "scalability", "performance", "optimization"],
            "expert": ["low-level", "algorithm", "complexity", "paradigm"]
        }

        level_scores = {}
        for level, indicators in complexity_indicators.items():
            score = sum(1 for indicator in indicators if indicator in message)
            level_scores[level] = score

        # Add technical term score
        level_scores["advanced"] += tech_score
        level_scores["expert"] += tech_score * 2

        # Determine level
        if tech_score == 0 and level_scores["beginner"] > 0:
            level = TechnicalLevel.BEGINNER
            confidence = 0.7
        elif tech_score <= 2 or level_scores["intermediate"] > 0:
            level = TechnicalLevel.INTERMEDIATE
            confidence = 0.6
        elif tech_score <= 5 or level_scores["advanced"] > 0:
            level = TechnicalLevel.ADVANCED
            confidence = 0.7
        else:
            level = TechnicalLevel.EXPERT
            confidence = 0.8

        return {
            "technical_level": level,
            "confidence": confidence,
            "technical_terms": tech_score,
            "complexity_scores": level_scores
        }

    async def _analyze_tone_preference(
        self,
        interaction: UserInteractionData
    ) -> Dict[str, Any]:
        """Analyze user's preferred response tone"""

        message = interaction.message_content.lower()
        emotional_indicators = interaction.emotional_indicators

        tone_scores = {
            TonePreference.PROFESSIONAL: 0.0,
            TonePreference.FRIENDLY: 0.0,
            TonePreference.ENTHUSIASTIC: 0.0,
            TonePreference.CALM: 0.0,
            TonePreference.HUMOROUS: 0.0,
            TonePreference.EMPATHETIC: 0.0,
            TonePreference.DIRECT: 0.0,
            TonePreference.SUPPORTIVE: 0.0
        }

        # Professional tone indicators
        if any(word in message for word in ["please", "thank", "appreciate", "regards"]):
            tone_scores[TonePreference.PROFESSIONAL] += 1

        # Friendly tone indicators
        if any(word in message for word in ["hi", "hello", "thanks", "awesome", "cool"]):
            tone_scores[TonePreference.FRIENDLY] += 1

        # Enthusiastic tone indicators
        if "excited" in message or any(punct in message for punct in ["!", "!!"]):
            tone_scores[TonePreference.ENTHUSIASTIC] += 1

        # Calm tone indicators
        if any(word in message for word in ["relax", "calm", "peaceful", "understand"]):
            tone_scores[TonePreference.CALM] += 1

        # Humorous tone indicators
        if any(word in message for word in ["funny", "haha", "lol", "joke"]):
            tone_scores[TonePreference.HUMOROUS] += 1

        # Empathetic tone indicators
        if any(word in message for word in ["feel", "understand", "relate", "empathize"]):
            tone_scores[TonePreference.EMPATHETIC] += 1

        # Direct tone indicators
        if any(word in message for word in ["just", "directly", "straight", "simply"]):
            tone_scores[TonePreference.DIRECT] += 1

        # Supportive tone indicators
        if any(word in message for word in ["help", "support", "assist", "guide"]):
            tone_scores[TonePreference.SUPPORTIVE] += 1

        # Emotional indicators
        for emotion in emotional_indicators:
            if emotion == "positive":
                tone_scores[TonePreference.ENTHUSIASTIC] += 1
                tone_scores[TonePreference.FRIENDLY] += 1
            elif emotion == "negative":
                tone_scores[TonePreference.EMPATHETIC] += 1
                tone_scores[TonePreference.SUPPORTIVE] += 1

        # Determine preferred tone
        max_score = max(tone_scores.values())
        if max_score > 0:
            preferred_tone = max(tone_scores, key=tone_scores.get)
            confidence = min(max_score / 3.0, 1.0)
        else:
            preferred_tone = TonePreference.FRIENDLY
            confidence = 0.5

        return {
            "preferred_tone": preferred_tone,
            "confidence": confidence,
            "tone_scores": {tone.value: score for tone, score in tone_scores.items()}
        }

    async def _analyze_topic_interests(
        self,
        interaction: UserInteractionData
    ) -> Dict[str, Any]:
        """Analyze user's topic interests"""

        # Extract topics from interaction
        topics = self._extract_topics(interaction.message_content + " " + interaction.response_content)

        # Score topics based on engagement
        topic_scores = {}
        for topic in topics:
            # Higher score for topics with follow-up questions
            engagement_multiplier = 1 + (interaction.follow_up_questions * 0.2)

            # Higher score for positive feedback
            if interaction.user_feedback and interaction.user_feedback >= 4:
                engagement_multiplier *= 1.5

            topic_scores[topic] = 1.0 * engagement_multiplier

        return {
            "interests": topic_scores,
            "primary_topics": sorted(topic_scores.items(), key=lambda x: x[1], reverse=True)[:5]
        }

    async def _analyze_language_style(
        self,
        interaction: UserInteractionData
    ) -> Dict[str, Any]:
        """Analyze user's language style patterns"""

        message = interaction.message_content

        # Language style metrics
        avg_sentence_length = len(message.split()) / max(1, message.count('.') + message.count('!') + message.count('?'))
        vocabulary_complexity = self._calculate_vocabulary_complexity(message)
        question_frequency = message.count('?') / max(1, len(message.split()))
        exclamation_frequency = message.count('!') / max(1, len(message.split()))

        return {
            "avg_sentence_length": avg_sentence_length,
            "vocabulary_complexity": vocabulary_complexity,
            "question_frequency": question_frequency,
            "exclamation_frequency": exclamation_frequency,
            "formality_level": self._calculate_formality_level(message)
        }

    async def _get_or_create_profile(self, user_id: str) -> UserProfile:
        """Get existing user profile or create new one"""

        if user_id not in self.user_profiles:
            self.user_profiles[user_id] = UserProfile(
                user_id=user_id,
                created_at=datetime.utcnow(),
                last_updated=datetime.utcnow(),
                total_interactions=0
            )
            logger.info(f"Created new user profile for {user_id}")

        return self.user_profiles[user_id]

    async def _update_preferences(
        self,
        profile: UserProfile,
        signals: Dict[UserPreferenceType, Dict[str, Any]],
        interaction: UserInteractionData
    ) -> List[Dict[str, Any]]:
        """Update user preferences based on analyzed signals"""

        updates = []

        for preference_type, signal_data in signals.items():
            # Extract preference value and confidence
            if preference_type == UserPreferenceType.COMMUNICATION_STYLE:
                value = signal_data["style"]
                confidence = signal_data["confidence"]
            elif preference_type == UserPreferenceType.RESPONSE_LENGTH:
                value = signal_data["preferred_length"]
                confidence = signal_data["confidence"]
            elif preference_type == UserPreferenceType.TECHNICAL_LEVEL:
                value = signal_data["technical_level"]
                confidence = signal_data["confidence"]
            elif preference_type == UserPreferenceType.TONE_PREFERENCE:
                value = signal_data["preferred_tone"]
                confidence = signal_data["confidence"]
            elif preference_type == UserPreferenceType.TOPIC_INTERESTS:
                value = signal_data["interests"]
                confidence = 0.7  # Default confidence for topic interests
            elif preference_type == UserPreferenceType.LANGUAGE_STYLE:
                value = signal_data
                confidence = 0.6
            else:
                continue

            # Update or create preference
            if preference_type in profile.preferences:
                existing_pref = profile.preferences[preference_type]

                # Apply weighted update based on confidence
                new_confidence = self._update_confidence(
                    existing_pref.confidence, confidence, self.adaptation_rate
                )

                # Update preference value if confidence is higher
                if confidence > existing_pref.confidence * 0.8:
                    existing_pref.value = value
                    existing_pref.confidence = new_confidence
                    existing_pref.last_updated = datetime.utcnow()
                    existing_pref.supporting_interactions += 1
                    existing_pref.examples.append(interaction.message_content[:100])

                    updates.append({
                        "type": preference_type.value,
                        "old_value": existing_pref.value,
                        "new_value": value,
                        "confidence": new_confidence
                    })
            else:
                # Create new preference
                new_preference = UserPreference(
                    preference_type=preference_type,
                    value=value,
                    confidence=confidence,
                    learned_at=datetime.utcnow(),
                    last_updated=datetime.utcnow(),
                    supporting_interactions=1,
                    examples=[interaction.message_content[:100]]
                )

                profile.preferences[preference_type] = new_preference

                updates.append({
                    "type": preference_type.value,
                    "new_value": value,
                    "confidence": confidence
                })

        return updates

    async def _update_topic_affinities(
        self,
        profile: UserProfile,
        interaction: UserInteractionData
    ) -> Dict[str, float]:
        """Update user's topic affinities based on interaction"""

        # Extract topics from interaction
        topics = self._extract_topics(interaction.message_content + " " + interaction.response_content)

        updates = {}

        for topic in topics:
            # Calculate affinity score based on engagement
            base_score = 1.0

            # Increase score based on feedback
            if interaction.user_feedback:
                base_score *= (interaction.user_feedback / 5.0)

            # Increase score based on follow-up questions
            base_score *= (1 + interaction.follow_up_questions * 0.1)

            # Update affinity with exponential moving average
            if topic in profile.topic_affinities:
                profile.topic_affinities[topic] = (
                    profile.topic_affinities[topic] * 0.8 + base_score * 0.2
                )
            else:
                profile.topic_affinities[topic] = base_score

            updates[topic] = profile.topic_affinities[topic]

        return updates

    async def _update_communication_patterns(
        self,
        profile: UserProfile,
        interaction: UserInteractionData
    ) -> Dict[str, Any]:
        """Update user's communication patterns"""

        # Analyze interaction timing
        current_hour = interaction.timestamp.hour

        if "interaction_times" not in profile.communication_patterns:
            profile.communication_patterns["interaction_times"] = {}

        # Update interaction time preferences
        time_slot = f"{current_hour:02d}:00"
        if time_slot not in profile.communication_patterns["interaction_times"]:
            profile.communication_patterns["interaction_times"][time_slot] = 0
        profile.communication_patterns["interaction_times"][time_slot] += 1

        # Analyze message patterns
        if "message_patterns" not in profile.communication_patterns:
            profile.communication_patterns["message_patterns"] = {}

        pattern_key = f"{interaction.message_type}_{len(interaction.message_content.split())//10*10}_words"
        if pattern_key not in profile.communication_patterns["message_patterns"]:
            profile.communication_patterns["message_patterns"][pattern_key] = 0
        profile.communication_patterns["message_patterns"][pattern_key] += 1

        return {
            "updated_time_slot": time_slot,
            "message_pattern": pattern_key,
            "total_interactions": profile.total_interactions
        }

    # Helper methods
    def _detect_message_type(self, message: str) -> str:
        """Detect the type of user message"""
        message_lower = message.lower().strip()

        if message_lower.endswith('?'):
            return "question"
        elif any(word in message_lower for word in ["help", "explain", "show me", "how to"]):
            return "request"
        elif any(word in message_lower for word in ["thanks", "thank you", "appreciate"]):
            return "gratitude"
        elif any(word in message_lower for word in ["hello", "hi", "hey", "good morning"]):
            return "greeting"
        else:
            return "statement"

    def _count_technical_terms(self, text: str) -> int:
        """Count technical terms in text"""
        text_lower = text.lower()
        count = 0

        for domain in self.technical_indicators["domains"]:
            if domain.lower() in text_lower:
                count += 1

        for term in self.technical_indicators["terms"]:
            if term.lower() in text_lower:
                count += 1

        return count

    def _detect_emotional_indicators(self, message: str) -> List[str]:
        """Detect emotional indicators in message"""
        indicators = []
        message_lower = message.lower()

        positive_words = ["great", "awesome", "excellent", "good", "love", "happy", "excited"]
        negative_words = ["bad", "terrible", "awful", "hate", "sad", "angry", "frustrated"]

        if any(word in message_lower for word in positive_words):
            indicators.append("positive")

        if any(word in message_lower for word in negative_words):
            indicators.append("negative")

        return indicators

    def _extract_context_keywords(self, message: str) -> List[str]:
        """Extract relevant context keywords from message"""
        # Simple keyword extraction (in production, use more sophisticated NLP)
        import re

        # Extract potential keywords (nouns and proper nouns)
        words = re.findall(r'\b[A-Z][a-z]+\b|\b[a-z]{4,}\b', message)

        # Filter out common words
        stop_words = {"this", "that", "with", "have", "will", "from", "they", "been", "said"}
        keywords = [word for word in words if word.lower() not in stop_words]

        return keywords[:10]  # Return top 10 keywords

    def _extract_topics(self, text: str) -> List[str]:
        """Extract topics from text"""
        # Simple topic extraction based on keywords
        topic_keywords = {
            "technology": ["software", "code", "programming", "algorithm", "database"],
            "business": ["company", "market", "revenue", "customer", "strategy"],
            "science": ["research", "experiment", "study", "analysis", "data"],
            "education": ["learning", "teaching", "student", "course", "knowledge"],
            "health": ["medical", "health", "patient", "treatment", "diagnosis"],
            "finance": ["money", "investment", "budget", "financial", "economy"]
        }

        text_lower = text.lower()
        topics = []

        for topic, keywords in topic_keywords.items():
            if any(keyword in text_lower for keyword in keywords):
                topics.append(topic)

        return topics

    def _calculate_vocabulary_complexity(self, text: str) -> float:
        """Calculate vocabulary complexity score"""
        words = text.split()
        if not words:
            return 0.0

        # Count longer words as indicator of complexity
        long_words = sum(1 for word in words if len(word) > 6)
        complexity = long_words / len(words)

        return min(complexity, 1.0)

    def _calculate_formality_level(self, text: str) -> float:
        """Calculate formality level of text"""
        text_lower = text.lower()

        formal_indicators = len([word for word in self.formal_indicators["words"] if word in text_lower])
        casual_indicators = len([word for word in self.casual_indicators["words"] if word in text_lower])

        if formal_indicators + casual_indicators == 0:
            return 0.5  # Neutral

        return formal_indicators / (formal_indicators + casual_indicators)

    def _update_confidence(self, existing_confidence: float, new_confidence: float, adaptation_rate: float) -> float:
        """Update confidence using exponential moving average"""
        return existing_confidence * (1 - adaptation_rate) + new_confidence * adaptation_rate

    def _calculate_confidence_improvement(self, preference_updates: List[Dict[str, Any]]) -> float:
        """Calculate overall confidence improvement from updates"""
        if not preference_updates:
            return 0.0

        total_confidence = sum(update.get("confidence", 0) for update in preference_updates)
        return total_confidence / len(preference_updates)

    def _get_current_preferences(self, profile: UserProfile) -> Dict[str, Any]:
        """Get current user preferences as dictionary"""
        preferences = {}

        for pref_type, preference in profile.preferences.items():
            if hasattr(preference.value, 'value'):  # Handle enum types
                preferences[pref_type.value] = {
                    "value": preference.value.value,
                    "confidence": preference.confidence,
                    "last_updated": preference.last_updated.isoformat()
                }
            else:
                preferences[pref_type.value] = {
                    "value": preference.value,
                    "confidence": preference.confidence,
                    "last_updated": preference.last_updated.isoformat()
                }

        return preferences

    async def get_user_profile(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get complete user profile"""
        if user_id not in self.user_profiles:
            return None

        profile = self.user_profiles[user_id]

        return {
            "user_id": profile.user_id,
            "created_at": profile.created_at.isoformat(),
            "last_updated": profile.last_updated.isoformat(),
            "total_interactions": profile.total_interactions,
            "preferences": self._get_current_preferences(profile),
            "topic_affinities": profile.topic_affinities,
            "communication_patterns": profile.communication_patterns,
            "adaptation_count": len(profile.adaptation_history)
        }

    async def get_preference_summary(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get summary of user's learned preferences"""
        profile_data = await self.get_user_profile(user_id)
        if not profile_data:
            return None

        # Create human-readable summary
        summary = {
            "user_id": user_id,
            "interaction_count": profile_data["total_interactions"],
            "learned_preferences": {}
        }

        preferences = profile_data["preferences"]

        if "communication_style" in preferences:
            style = preferences["communication_style"]["value"]
            summary["learned_preferences"]["communication_style"] = f"Prefers {style} communication"

        if "response_length" in preferences:
            length = preferences["response_length"]["value"]
            summary["learned_preferences"]["response_length"] = f"Prefers {length} responses"

        if "technical_level" in preferences:
            level = preferences["technical_level"]["value"]
            summary["learned_preferences"]["technical_level"] = f"Technical level: {level}"

        if "tone_preference" in preferences:
            tone = preferences["tone_preference"]["value"]
            summary["learned_preferences"]["tone"] = f"Prefers {tone} tone"

        if profile_data["topic_affinities"]:
            top_topics = sorted(profile_data["topic_affinities"].items(), key=lambda x: x[1], reverse=True)[:3]
            summary["learned_preferences"]["top_topics"] = [topic for topic, _ in top_topics]

        return summary

# Global user profiler instance
user_profiler: Optional[UserProfiler] = None

def initialize_user_profiler(config: Dict[str, Any]):
    """Initialize the global user profiler"""

    global user_profiler
    user_profiler = UserProfiler(config)
    logger.info("User profiler initialized")

def get_user_profiler() -> UserProfiler:
    """Get the global user profiler"""

    if user_profiler is None:
        raise RuntimeError("User profiler not initialized")

    return user_profiler