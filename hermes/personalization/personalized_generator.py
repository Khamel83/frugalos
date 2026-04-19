#!/usr/bin/env python3
"""
Personalized Response Generator for Hermes AI Assistant
Adapts response generation based on learned user preferences
"""

import asyncio
import logging
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass
from enum import Enum
import re
import json
from datetime import datetime

from .user_profiler import get_user_profiler, CommunicationStyle, ResponseLength, TonePreference, TechnicalLevel

logger = logging.getLogger(__name__)

class ResponseAdaptationStrategy(Enum):
    """Strategies for adapting responses"""
    STYLE_MATCHING = "style_matching"
    CONTENT_ADAPTATION = "content_adaptation"
    STRUCTURE_MODIFICATION = "structure_modification"
    VOCABULARY_ADJUSTMENT = "vocabulary_adjustment"
    TONE_ALIGNMENT = "tone_alignment"

@dataclass
class PersonalizationDirectives:
    """Directives for personalizing a response"""
    communication_style: CommunicationStyle
    response_length: ResponseLength
    tone_preference: TonePreference
    technical_level: TechnicalLevel
    topic_affinities: Dict[str, float]
    language_complexity: float
    formality_level: float
    confidence_score: float

@dataclass
class AdaptationResult:
    """Result of response personalization"""
    original_response: str
    personalized_response: str
    adaptations_applied: List[str]
    confidence_score: float
    processing_time: float
    personalization_directives: PersonalizationDirectives

class PersonalizedResponseGenerator:
    """Generates personalized responses based on user preferences"""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.min_confidence_threshold = config.get("min_confidence_threshold", 0.6)
        self.max_adaptation_time = config.get("max_adaptation_time", 2.0)

        # Style templates and patterns
        self.style_templates = self._initialize_style_templates()
        self.tone_modifiers = self._initialize_tone_modifiers()
        self.technical_adjustments = self._initialize_technical_adjustments()

        # Response length targets
        self.length_targets = {
            ResponseLength.BRIEF: (10, 30),      # words
            ResponseLength.MODERATE: (30, 80),   # words
            ResponseLength.DETAILED: (80, 150),  # words
            ResponseLength.COMPREHENSIVE: (150, 300)  # words
        }

    async def personalize_response(
        self,
        user_id: str,
        original_response: str,
        context: Optional[Dict[str, Any]] = None
    ) -> AdaptationResult:
        """
        Personalize a response based on user's learned preferences

        Args:
            user_id: User identifier
            original_response: Original AI response
            context: Additional context for personalization

        Returns:
            Personalized response with adaptation details
        """

        start_time = asyncio.get_event_loop().time()

        try:
            # Get user profile and preferences
            user_profiler = get_user_profiler()
            user_profile = await user_profiler.get_user_profile(user_id)

            if not user_profile:
                # No profile available, return original response
                return AdaptationResult(
                    original_response=original_response,
                    personalized_response=original_response,
                    adaptations_applied=[],
                    confidence_score=0.0,
                    processing_time=asyncio.get_event_loop().time() - start_time,
                    personalization_directives=self._create_default_directives()
                )

            # Extract personalization directives
            directives = self._extract_personalization_directives(user_profile)

            # Skip personalization if confidence is too low
            if directives.confidence_score < self.min_confidence_threshold:
                logger.info(f"Skipping personalization for user {user_id} due to low confidence")
                return AdaptationResult(
                    original_response=original_response,
                    personalized_response=original_response,
                    adaptations_applied=["skipped_low_confidence"],
                    confidence_score=directives.confidence_score,
                    processing_time=asyncio.get_event_loop().time() - start_time,
                    personalization_directives=directives
                )

            # Apply personalization strategies
            adapted_response = original_response
            adaptations_applied = []

            # 1. Style matching
            if directives.communication_style:
                adapted_response, style_adaptations = await self._apply_style_matching(
                    adapted_response, directives
                )
                adaptations_applied.extend(style_adaptations)

            # 2. Length adjustment
            if directives.response_length:
                adapted_response, length_adaptations = await self._apply_length_adjustment(
                    adapted_response, directives
                )
                adaptations_applied.extend(length_adaptations)

            # 3. Tone alignment
            if directives.tone_preference:
                adapted_response, tone_adaptations = await self._apply_tone_alignment(
                    adapted_response, directives
                )
                adaptations_applied.extend(tone_adaptations)

            # 4. Technical level adjustment
            if directives.technical_level:
                adapted_response, tech_adaptations = await self._apply_technical_adjustment(
                    adapted_response, directives
                )
                adaptations_applied.extend(tech_adaptations)

            # 5. Topic relevance enhancement
            if directives.topic_affinities:
                adapted_response, topic_adaptations = await self._enhance_topic_relevance(
                    adapted_response, directives, context
                )
                adaptations_applied.extend(topic_adaptations)

            # 6. Vocabulary and complexity adjustment
            adapted_response, vocab_adaptations = await self._adjust_vocabulary_complexity(
                adapted_response, directives
            )
            adaptations_applied.extend(vocab_adaptations)

            processing_time = asyncio.get_event_loop().time() - start_time

            logger.info(f"Personalized response for user {user_id} in {processing_time:.3f}s")

            return AdaptationResult(
                original_response=original_response,
                personalized_response=adapted_response,
                adaptations_applied=adaptations_applied,
                confidence_score=directives.confidence_score,
                processing_time=processing_time,
                personalization_directives=directives
            )

        except Exception as e:
            logger.error(f"Error personalizing response for user {user_id}: {e}")
            return AdaptationResult(
                original_response=original_response,
                personalized_response=original_response,
                adaptations_applied=["error_fallback"],
                confidence_score=0.0,
                processing_time=asyncio.get_event_loop().time() - start_time,
                personalization_directives=self._create_default_directives()
            )

    def _extract_personalization_directives(self, user_profile: Dict[str, Any]) -> PersonalizationDirectives:
        """Extract personalization directives from user profile"""

        preferences = user_profile.get("preferences", {})

        # Communication style
        comm_style_pref = preferences.get("communication_style", {})
        communication_style = CommunicationStyle(comm_style_pref.get("value", "conversational"))
        comm_confidence = comm_style_pref.get("confidence", 0.5)

        # Response length
        length_pref = preferences.get("response_length", {})
        response_length = ResponseLength(length_pref.get("value", "moderate"))
        length_confidence = length_pref.get("confidence", 0.5)

        # Tone preference
        tone_pref = preferences.get("tone_preference", {})
        tone_preference = TonePreference(tone_pref.get("value", "friendly"))
        tone_confidence = tone_pref.get("confidence", 0.5)

        # Technical level
        tech_pref = preferences.get("technical_level", {})
        technical_level = TechnicalLevel(tech_pref.get("value", "intermediate"))
        tech_confidence = tech_pref.get("confidence", 0.5)

        # Topic affinities
        topic_affinities = user_profile.get("topic_affinities", {})

        # Language complexity
        language_pref = preferences.get("language_style", {})
        language_complexity = language_pref.get("vocabulary_complexity", 0.5)

        # Formality level
        formality_level = language_pref.get("formality_level", 0.5)

        # Calculate overall confidence
        overall_confidence = (
            comm_confidence * 0.25 +
            length_confidence * 0.2 +
            tone_confidence * 0.2 +
            tech_confidence * 0.2 +
            0.15  # Base confidence for other preferences
        )

        return PersonalizationDirectives(
            communication_style=communication_style,
            response_length=response_length,
            tone_preference=tone_preference,
            technical_level=technical_level,
            topic_affinities=topic_affinities,
            language_complexity=language_complexity,
            formality_level=formality_level,
            confidence_score=overall_confidence
        )

    async def _apply_style_matching(
        self,
        response: str,
        directives: PersonalizationDirectives
    ) -> Tuple[str, List[str]]:
        """Apply communication style matching to response"""

        adapted_response = response
        adaptations = []

        style = directives.communication_style
        templates = self.style_templates.get(style, {})

        # Apply sentence structure patterns
        if "sentence_patterns" in templates:
            adapted_response = self._apply_sentence_patterns(
                adapted_response, templates["sentence_patterns"]
            )
            adaptations.append(f"style_{style.value}_structure")

        # Apply style-specific vocabulary
        if "vocabulary" in templates:
            adapted_response = self._apply_vocabulary_substitutions(
                adapted_response, templates["vocabulary"]
            )
            adaptations.append(f"style_{style.value}_vocabulary")

        # Apply formatting patterns
        if "formatting" in templates:
            adapted_response = self._apply_formatting_patterns(
                adapted_response, templates["formatting"]
            )
            adaptations.append(f"style_{style.value}_formatting")

        return adapted_response, adaptations

    async def _apply_length_adjustment(
        self,
        response: str,
        directives: PersonalizationDirectives
    ) -> Tuple[str, List[str]]:
        """Adjust response length based on user preference"""

        current_word_count = len(response.split())
        target_length = directives.response_length
        target_min, target_max = self.length_targets[target_length]

        adapted_response = response
        adaptations = []

        if current_word_count < target_min:
            # Response is too short, expand it
            adapted_response = await self._expand_response(
                response, target_min, directives
            )
            adaptations.append(f"expanded_to_{target_length.value}")
        elif current_word_count > target_max:
            # Response is too long, condense it
            adapted_response = await self._condense_response(
                response, target_max, directives
            )
            adaptations.append(f"condensed_to_{target_length.value}")

        return adapted_response, adaptations

    async def _apply_tone_alignment(
        self,
        response: str,
        directives: PersonalizationDirectives
    ) -> Tuple[str, List[str]]:
        """Align response tone with user preference"""

        adapted_response = response
        adaptations = []

        tone = directives.tone_preference
        modifiers = self.tone_modifiers.get(tone, {})

        # Apply tone-specific modifications
        if "prefixes" in modifiers:
            adapted_response = self._apply_prefixes(adapted_response, modifiers["prefixes"])
            adaptations.append(f"tone_{tone.value}_prefixes")

        if "word_choices" in modifiers:
            adapted_response = self._apply_word_choices(adapted_response, modifiers["word_choices"])
            adaptations.append(f"tone_{tone.value}_word_choices")

        if "sentence_endings" in modifiers:
            adapted_response = self._apply_sentence_endings(
                adapted_response, modifiers["sentence_endings"]
            )
            adaptations.append(f"tone_{tone.value}_endings")

        if "punctuation" in modifiers:
            adapted_response = self._apply_punctuation_patterns(
                adapted_response, modifiers["punctuation"]
            )
            adaptations.append(f"tone_{tone.value}_punctuation")

        return adapted_response, adaptations

    async def _apply_technical_adjustment(
        self,
        response: str,
        directives: PersonalizationDirectives
    ) -> Tuple[str, List[str]]:
        """Adjust technical complexity based on user's level"""

        adapted_response = response
        adaptations = []

        tech_level = directives.technical_level
        adjustments = self.technical_adjustments.get(tech_level, {})

        # Apply technical level modifications
        if "explanations" in adjustments and tech_level in [TechnicalLevel.BEGINNER, TechnicalLevel.INTERMEDIATE]:
            adapted_response = self._add_explanations(adapted_response, adjustments["explanations"])
            adaptations.append(f"tech_{tech_level.value}_explanations")

        if "simplifications" in adjustments and tech_level == TechnicalLevel.BEGINNER:
            adapted_response = self._simplify_technical_content(
                adapted_response, adjustments["simplifications"]
            )
            adaptations.append(f"tech_{tech_level.value}_simplified")

        if "advanced_content" in adjustments and tech_level in [TechnicalLevel.ADVANCED, TechnicalLevel.EXPERT]:
            adapted_response = self._add_advanced_content(
                adapted_response, adjustments["advanced_content"]
            )
            adaptations.append(f"tech_{tech_level.value}_advanced")

        return adapted_response, adaptations

    async def _enhance_topic_relevance(
        self,
        response: str,
        directives: PersonalizationDirectives,
        context: Optional[Dict[str, Any]] = None
    ) -> Tuple[str, List[str]]:
        """Enhance response relevance based on user's topic interests"""

        adapted_response = response
        adaptations = []

        # Get top topic interests
        top_topics = sorted(
            directives.topic_affinities.items(),
            key=lambda x: x[1],
            reverse=True
        )[:3]

        if top_topics:
            # Enhance response with topic-relevant content
            for topic, affinity in top_topics:
                if affinity > 0.7:  # High affinity topics
                    adapted_response = self._enhance_for_topic(adapted_response, topic)
                    adaptations.append(f"topic_enhanced_{topic}")

        return adapted_response, adaptations

    async def _adjust_vocabulary_complexity(
        self,
        response: str,
        directives: PersonalizationDirectives
    ) -> Tuple[str, List[str]]:
        """Adjust vocabulary complexity based on user preference"""

        adapted_response = response
        adaptations = []

        complexity = directives.language_complexity
        formality = directives.formality_level

        if complexity < 0.3:  # Simple vocabulary
            adapted_response = self._simplify_vocabulary(adapted_response)
            adaptations.append("vocabulary_simplified")
        elif complexity > 0.7:  # Complex vocabulary
            adapted_response = self._enhance_vocabulary(adapted_response)
            adaptations.append("vocabulary_enhanced")

        if formality < 0.3:  # Informal
            adapted_response = self._make_informal(adapted_response)
            adaptations.append("made_informal")
        elif formality > 0.7:  # Formal
            adapted_response = self._make_formal(adapted_response)
            adaptations.append("made_formal")

        return adapted_response, adaptations

    # Helper methods for response adaptation
    def _apply_sentence_patterns(self, response: str, patterns: List[str]) -> str:
        """Apply sentence structure patterns"""
        # This is a simplified implementation
        # In production, use more sophisticated NLP techniques

        for pattern in patterns:
            if pattern == "short_sentences":
                # Break long sentences into shorter ones
                sentences = re.split(r'[.!?]+', response)
                adapted_sentences = []
                for sentence in sentences:
                    sentence = sentence.strip()
                    if len(sentence.split()) > 20:
                        # Try to break at conjunctions
                        parts = re.split(r'\b(and|but|or|so|because)\b', sentence, flags=re.IGNORECASE)
                        if len(parts) > 1:
                            adapted_sentences.extend(parts)
                        else:
                            adapted_sentences.append(sentence)
                    else:
                        adapted_sentences.append(sentence)
                response = '. '.join(filter(None, adapted_sentences))

        return response

    def _apply_vocabulary_substitutions(self, response: str, substitutions: Dict[str, str]) -> str:
        """Apply vocabulary substitutions"""
        adapted_response = response

        for original, replacement in substitutions.items():
            adapted_response = re.sub(
                r'\b' + re.escape(original) + r'\b',
                replacement,
                adapted_response,
                flags=re.IGNORECASE
            )

        return adapted_response

    def _apply_formatting_patterns(self, response: str, formatting: Dict[str, Any]) -> str:
        """Apply formatting patterns"""
        adapted_response = response

        if "add_structure" in formatting and formatting["add_structure"]:
            # Add bullet points for lists
            if any(indicator in adapted_response for indicator in [":", ":", "such as"]):
                lines = adapted_response.split('\n')
                for i, line in enumerate(lines):
                    if any(indicator in line for indicator in [":", "such as"]):
                        # Convert to bullet points
                        items = re.split(r'[,;]', line.split(':', 1)[1])
                        if len(items) > 1:
                            lines[i] = line.split(':')[0] + ':'
                            for item in items:
                                if item.strip():
                                    lines.insert(i+1, f"  • {item.strip()}")
                            break
                adapted_response = '\n'.join(lines)

        return adapted_response

    async def _expand_response(
        self,
        response: str,
        target_min: int,
        directives: PersonalizationDirectives
    ) -> str:
        """Expand response to meet minimum length requirements"""

        current_words = len(response.split())
        if current_words >= target_min:
            return response

        expansion_needed = target_min - current_words

        # Generate appropriate expansions based on context and user preferences
        expansions = []

        # Add contextual details
        if directives.technical_level != TechnicalLevel.EXPERT:
            expansions.append("Here's some additional context that might be helpful: ")

        # Add examples if appropriate
        if "explain" in response.lower() or "how to" in response.lower():
            expansions.append("For example, ")

        # Add forward-looking statements
        if directives.tone_preference == TonePreference.SUPPORTIVE:
            expansions.append("Would you like me to elaborate on any particular aspect? ")

        # Combine expansions
        if expansions:
            expanded_response = response + " " + " ".join(expansions[:2])
            return expanded_response

        return response

    async def _condense_response(
        self,
        response: str,
        target_max: int,
        directives: PersonalizationDirectives
    ) -> str:
        """Condense response to meet maximum length requirements"""

        current_words = len(response.split())
        if current_words <= target_max:
            return response

        sentences = re.split(r'[.!?]+', response)
        condensed_sentences = []

        word_count = 0
        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue

            sentence_words = len(sentence.split())
            if word_count + sentence_words <= target_max:
                condensed_sentences.append(sentence)
                word_count += sentence_words
            else:
                break

        if condensed_sentences:
            return '. '.join(condensed_sentences) + '.'

        # If even one sentence is too long, truncate it
        first_sentence = sentences[0].strip()
        words = first_sentence.split()
        return ' '.join(words[:target_max]) + '...' if len(words) > target_max else first_sentence

    def _apply_prefixes(self, response: str, prefixes: List[str]) -> str:
        """Apply tone-specific prefixes"""
        if prefixes:
            prefix = prefixes[0]  # Use first prefix
            if not response.lower().startswith(tuple(p.lower() for p in prefixes)):
                return f"{prefix} {response}"
        return response

    def _apply_word_choices(self, response: str, word_choices: Dict[str, str]) -> str:
        """Apply tone-specific word choices"""
        adapted_response = response

        for original, replacement in word_choices.items():
            adapted_response = re.sub(
                r'\b' + re.escape(original) + r'\b',
                replacement,
                adapted_response,
                flags=re.IGNORECASE
            )

        return adapted_response

    def _apply_sentence_endings(self, response: str, endings: List[str]) -> str:
        """Apply tone-specific sentence endings"""
        # Add appropriate endings to sentences
        sentences = re.split(r'([.!?]+)', response)
        adapted_sentences = []

        for i in range(0, len(sentences), 2):
            if i < len(sentences):
                sentence = sentences[i].strip()
                if sentence:
                    # Choose appropriate ending
                    if i + 1 < len(sentences):
                        punctuation = sentences[i + 1]
                    else:
                        punctuation = '.'

                    adapted_sentences.append(sentence + punctuation)

        return ' '.join(adapted_sentences)

    def _apply_punctuation_patterns(self, response: str, patterns: Dict[str, Any]) -> str:
        """Apply tone-specific punctuation patterns"""
        adapted_response = response

        if "exclamation_frequency" in patterns:
            freq = patterns["exclamation_frequency"]
            if freq > 0.5 and "!" not in adapted_response:
                adapted_response = adapted_response.rstrip('.') + "!"

        return adapted_response

    def _add_explanations(self, response: str, explanations: List[str]) -> str:
        """Add explanatory content for less technical users"""
        # Simple implementation - in production, use more sophisticated methods
        if explanations:
            explanation = explanations[0]
            return f"{response} {explanation}"
        return response

    def _simplify_technical_content(self, response: str, simplifications: Dict[str, str]) -> str:
        """Simplify technical content"""
        adapted_response = response

        for technical, simple in simplifications.items():
            adapted_response = re.sub(
                r'\b' + re.escape(technical) + r'\b',
                simple,
                adapted_response,
                flags=re.IGNORECASE
            )

        return adapted_response

    def _add_advanced_content(self, response: str, advanced_content: List[str]) -> str:
        """Add advanced content for expert users"""
        if advanced_content:
            advanced = advanced_content[0]
            return f"{response} {advanced}"
        return response

    def _enhance_for_topic(self, response: str, topic: str) -> str:
        """Enhance response for specific topic"""
        # Simple topic enhancement
        topic_enhancements = {
            "technology": "This approach leverages modern technological best practices.",
            "business": "From a business perspective, this strategy offers significant advantages.",
            "science": "Scientific research supports this approach with compelling evidence.",
            "education": "Educational theory suggests this is an effective learning method."
        }

        if topic in topic_enhancements:
            enhancement = topic_enhancements[topic]
            return f"{response} {enhancement}"

        return response

    def _simplify_vocabulary(self, response: str) -> str:
        """Simplify vocabulary in response"""
        simplifications = {
            "utilize": "use",
            "demonstrate": "show",
            "facilitate": "help",
            "consequently": "so",
            "furthermore": "also",
            "implement": "do",
            "methodology": "method",
            "subsequently": "then"
        }

        adapted_response = response
        for complex_word, simple_word in simplifications.items():
            adapted_response = re.sub(
                r'\b' + re.escape(complex_word) + r'\b',
                simple_word,
                adapted_response,
                flags=re.IGNORECASE
            )

        return adapted_response

    def _enhance_vocabulary(self, response: str) -> str:
        """Enhance vocabulary in response"""
        enhancements = {
            "use": "utilize",
            "show": "demonstrate",
            "help": "facilitate",
            "so": "consequently",
            "also": "furthermore",
            "do": "implement",
            "method": "methodology",
            "then": "subsequently"
        }

        adapted_response = response
        for simple_word, complex_word in enhancements.items():
            adapted_response = re.sub(
                r'\b' + re.escape(simple_word) + r'\b',
                complex_word,
                adapted_response,
                flags=re.IGNORECASE
            )

        return adapted_response

    def _make_informal(self, response: str) -> str:
        """Make response more informal"""
        informal_substitutions = {
            "I would recommend": "I'd suggest",
            "It is important to": "It's important to",
            "You should": "You should",
            "Therefore": "So",
            "Additionally": "Also",
            "Furthermore": "Plus"
        }

        adapted_response = response
        for formal, informal in informal_substitutions.items():
            adapted_response = re.sub(
                r'\b' + re.escape(formal) + r'\b',
                informal,
                adapted_response,
                flags=re.IGNORECASE
            )

        return adapted_response

    def _make_formal(self, response: str) -> str:
        """Make response more formal"""
        formal_substitutions = {
            "I'd suggest": "I would recommend",
            "It's important to": "It is important to",
            "Plus": "Additionally",
            "Also": "Furthermore",
            "So": "Therefore",
            "Kids": "Children",
            "Guys": "Individuals"
        }

        adapted_response = response
        for informal, formal in formal_substitutions.items():
            adapted_response = re.sub(
                r'\b' + re.escape(informal) + r'\b',
                formal,
                adapted_response,
                flags=re.IGNORECASE
            )

        return adapted_response

    def _create_default_directives(self) -> PersonalizationDirectives:
        """Create default personalization directives"""
        return PersonalizationDirectives(
            communication_style=CommunicationStyle.CONVERSATIONAL,
            response_length=ResponseLength.MODERATE,
            tone_preference=TonePreference.FRIENDLY,
            technical_level=TechnicalLevel.INTERMEDIATE,
            topic_affinities={},
            language_complexity=0.5,
            formality_level=0.5,
            confidence_score=0.0
        )

    def _initialize_style_templates(self) -> Dict[CommunicationStyle, Dict[str, Any]]:
        """Initialize communication style templates"""
        return {
            CommunicationStyle.FORMAL: {
                "sentence_patterns": ["complete_sentences", "proper_structure"],
                "vocabulary": {
                    "good": "excellent",
                    "bad": "suboptimal",
                    "big": "substantial",
                    "small": "minimal"
                },
                "formatting": {"add_structure": True}
            },
            CommunicationStyle.CASUAL: {
                "sentence_patterns": ["short_sentences", "conversational_flow"],
                "vocabulary": {
                    "excellent": "great",
                    "suboptimal": "not so good",
                    "substantial": "big",
                    "minimal": "small"
                },
                "formatting": {"add_structure": False}
            },
            CommunicationStyle.TECHNICAL: {
                "sentence_patterns": ["precise_language"],
                "vocabulary": {
                    "use": "utilize",
                    "show": "demonstrate",
                    "help": "facilitate"
                },
                "formatting": {"add_structure": True}
            },
            CommunicationStyle.CONVERSATIONAL: {
                "sentence_patterns": ["natural_flow", "questions_encouraged"],
                "vocabulary": {
                    "therefore": "so",
                    "furthermore": "also",
                    "consequently": "as a result"
                },
                "formatting": {"add_structure": False}
            },
            CommunicationStyle.CONCISE: {
                "sentence_patterns": ["brief_statements"],
                "vocabulary": {},
                "formatting": {"add_structure": False}
            },
            CommunicationStyle.DETAILED: {
                "sentence_patterns": ["comprehensive_explanations"],
                "vocabulary": {
                    "explain": "elaborate on",
                    "tell": "describe in detail"
                },
                "formatting": {"add_structure": True}
            }
        }

    def _initialize_tone_modifiers(self) -> Dict[TonePreference, Dict[str, Any]]:
        """Initialize tone modifiers"""
        return {
            TonePreference.PROFESSIONAL: {
                "prefixes": ["Based on my analysis,"],
                "word_choices": {
                    "great": "excellent",
                    "help": "assist",
                    "show": "demonstrate"
                },
                "sentence_endings": ["."],
                "punctuation": {"exclamation_frequency": 0.1}
            },
            TonePreference.FRIENDLY: {
                "prefixes": ["I'd be happy to help!"],
                "word_choices": {
                    "excellent": "great",
                    "assist": "help",
                    "demonstrate": "show"
                },
                "sentence_endings": ["!"],
                "punctuation": {"exclamation_frequency": 0.3}
            },
            TonePreference.ENTHUSIASTIC: {
                "prefixes": ["Absolutely! "],
                "word_choices": {
                    "good": "fantastic",
                    "interesting": "fascinating",
                    "helpful": "incredibly helpful"
                },
                "sentence_endings": ["!"],
                "punctuation": {"exclamation_frequency": 0.6}
            },
            TonePreference.SUPPORTIVE: {
                "prefixes": ["I'm here to help. "],
                "word_choices": {
                    "problem": "challenge",
                    "difficult": "challenging",
                    "wrong": "incorrect"
                },
                "sentence_endings": ["."],
                "punctuation": {"exclamation_frequency": 0.2}
            },
            TonePreference.DIRECT: {
                "prefixes": [],
                "word_choices": {
                    "perhaps": "maybe",
                    "possibly": "maybe",
                    "it seems": "it is"
                },
                "sentence_endings": ["."],
                "punctuation": {"exclamation_frequency": 0.1}
            }
        }

    def _initialize_technical_adjustments(self) -> Dict[TechnicalLevel, Dict[str, Any]]:
        """Initialize technical level adjustments"""
        return {
            TechnicalLevel.BEGINNER: {
                "explanations": [
                    "Let me break this down step by step.",
                    "Think of it this way:",
                    "Here's what that means in simple terms:"
                ],
                "simplifications": {
                    "algorithm": "step-by-step process",
                    "API": "tool that lets programs talk to each other",
                    "database": "organized collection of information",
                    "framework": "set of tools for building things"
                }
            },
            TechnicalLevel.INTERMEDIATE: {
                "explanations": [
                    "To clarify this concept:",
                    "Here's the key insight:"
                ]
            },
            TechnicalLevel.ADVANCED: {
                "advanced_content": [
                    "From a technical perspective:",
                    "The underlying architecture supports:",
                    "This implementation considers:"
                ]
            },
            TechnicalLevel.EXPERT: {
                "advanced_content": [
                    "The implementation details include:",
                    "Architecturally, this approach provides:",
                    "From an optimization standpoint:"
                ]
            }
        }

# Global personalized response generator instance
personalized_generator: Optional[PersonalizedResponseGenerator] = None

def initialize_personalized_generator(config: Dict[str, Any]):
    """Initialize the global personalized response generator"""

    global personalized_generator
    personalized_generator = PersonalizedResponseGenerator(config)
    logger.info("Personalized response generator initialized")

def get_personalized_generator() -> PersonalizedResponseGenerator:
    """Get the global personalized response generator"""

    if personalized_generator is None:
        raise RuntimeError("Personalized response generator not initialized")

    return personalized_generator