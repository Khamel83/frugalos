#!/usr/bin/env python3
"""
Multi-Modal Reasoner for Hermes AI Assistant
Provides cross-modal reasoning across text, image, and audio inputs
"""

import asyncio
import logging
from typing import Dict, Any, Optional, List, Union, Tuple
from dataclasses import dataclass, field
from enum import Enum
import json
import time
from datetime import datetime

from ..vision.vision_service import VisionService, AnalysisType, VisionAnalysisResult
from ..audio.audio_service import AudioService, SpeechEngine, VoiceEngine, SpeechToTextResult, TextToSpeechResult
from ..streaming.streaming_manager import ActiveStream, streaming_manager

logger = logging.getLogger(__name__)

class ModalityType(Enum):
    """Types of input modalities"""
    TEXT = "text"
    IMAGE = "image"
    AUDIO = "audio"
    VIDEO = "video"

class ReasoningStrategy(Enum):
    """Multi-modal reasoning strategies"""
    SEQUENTIAL = "sequential"  # Process modalities one after another
    PARALLEL = "parallel"      # Process all modalities simultaneously
    DOMINANT = "dominant"      # Use dominant modality with others as context
    INTEGRATED = "integrated"  # Fully integrated reasoning across modalities

@dataclass
class ModalityData:
    """Data for a specific modality"""
    modality: ModalityType
    data: Union[str, bytes]
    metadata: Dict[str, Any] = field(default_factory=dict)
    confidence: float = 1.0
    timestamp: float = field(default_factory=time.time)

@dataclass
class MultiModalInput:
    """Multi-modal input containing multiple modalities"""
    input_id: str
    modalities: List[ModalityData]
    context: Optional[Dict[str, Any]] = None
    reasoning_strategy: ReasoningStrategy = ReasoningStrategy.INTEGRATED
    user_id: Optional[str] = None
    conversation_id: Optional[str] = None

@dataclass
class ModalityAnalysis:
    """Analysis result for a specific modality"""
    modality: ModalityType
    analysis_type: str
    result: Dict[str, Any]
    confidence: float
    processing_time: float
    extracted_features: Dict[str, Any] = field(default_factory=dict)

@dataclass
class CrossModalInsight:
    """Insights from cross-modal reasoning"""
    insight_type: str
    description: str
    confidence: float
    supporting_modalities: List[ModalityType]
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class MultiModalResponse:
    """Response from multi-modal reasoning"""
    input_id: str
    reasoning_strategy: ReasoningStrategy
    modality_analyses: List[ModalityAnalysis]
    cross_modal_insights: List[CrossModalInsight]
    integrated_response: str
    confidence: float
    processing_time: float
    recommendations: List[str] = field(default_factory=list)

class MultiModalReasoner:
    """Advanced multi-modal reasoning system"""

    def __init__(
        self,
        vision_service: VisionService,
        audio_service: AudioService,
        config: Dict[str, Any]
    ):
        self.vision_service = vision_service
        self.audio_service = audio_service
        self.config = config
        self.max_concurrent_reasoning = config.get("max_concurrent_reasoning", 10)
        self.default_confidence_threshold = config.get("confidence_threshold", 0.7)

    async def reason(
        self,
        multi_modal_input: MultiModalInput,
        stream: Optional[ActiveStream] = None
    ) -> MultiModalResponse:
        """
        Perform multi-modal reasoning on input

        Args:
            multi_modal_input: Multi-modal input data
            stream: Optional stream for real-time updates

        Returns:
            Multi-modal reasoning response
        """

        start_time = time.time()

        try:
            # Send initial status
            if stream:
                await stream.send_metadata({
                    "stage": "multi_modal_reasoning",
                    "inputId": multi_modal_input.input_id,
                    "modalities": [m.modality.value for m in multi_modal_input.modalities],
                    "strategy": multi_modal_input.reasoning_strategy.value
                })

            # Analyze each modality
            modality_analyses = await self._analyze_modalities(multi_modal_input, stream)

            # Perform cross-modal reasoning
            cross_modal_insights = await self._perform_cross_modal_reasoning(
                modality_analyses, multi_modal_input.reasoning_strategy, stream
            )

            # Generate integrated response
            integrated_response = await self._generate_integrated_response(
                modality_analyses, cross_modal_insights, multi_modal_input, stream
            )

            # Calculate overall confidence
            overall_confidence = self._calculate_overall_confidence(
                modality_analyses, cross_modal_insights
            )

            # Generate recommendations
            recommendations = await self._generate_recommendations(
                modality_analyses, cross_modal_insights, integrated_response
            )

            processing_time = time.time() - start_time

            response = MultiModalResponse(
                input_id=multi_modal_input.input_id,
                reasoning_strategy=multi_modal_input.reasoning_strategy,
                modality_analyses=modality_analyses,
                cross_modal_insights=cross_modal_insights,
                integrated_response=integrated_response,
                confidence=overall_confidence,
                processing_time=processing_time,
                recommendations=recommendations
            )

            # Send completion status
            if stream:
                await stream.send_metadata({
                    "stage": "multi_modal_completed",
                    "inputId": multi_modal_input.input_id,
                    "confidence": overall_confidence,
                    "processingTime": processing_time
                })

            logger.info(f"Multi-modal reasoning completed for {multi_modal_input.input_id} in {processing_time:.2f}s")

            return response

        except Exception as e:
            logger.error(f"Multi-modal reasoning failed for {multi_modal_input.input_id}: {e}")
            if stream:
                await stream.send_error(str(e), "MULTIMODAL_REASONING_ERROR")
            raise

    async def _analyze_modalities(
        self,
        multi_modal_input: MultiModalInput,
        stream: Optional[ActiveStream] = None
    ) -> List[ModalityAnalysis]:
        """Analyze each modality in the input"""

        analyses = []
        analysis_tasks = []

        for modality_data in multi_modal_input.modalities:
            if modality_data.modality == ModalityType.TEXT:
                analysis_tasks.append(self._analyze_text_modality(modality_data))
            elif modality_data.modality == ModalityType.IMAGE:
                analysis_tasks.append(self._analyze_image_modality(modality_data))
            elif modality_data.modality == ModalityType.AUDIO:
                analysis_tasks.append(self._analyze_audio_modality(modality_data))
            elif modality_data.modality == ModalityType.VIDEO:
                analysis_tasks.append(self._analyze_video_modality(modality_data))

        # Execute analyses based on reasoning strategy
        if multi_modal_input.reasoning_strategy == ReasoningStrategy.PARALLEL:
            # Execute all analyses concurrently
            results = await asyncio.gather(*analysis_tasks, return_exceptions=True)
            for result in results:
                if isinstance(result, Exception):
                    logger.error(f"Modality analysis failed: {result}")
                else:
                    analyses.append(result)
                    if stream:
                        await stream.send_metadata({
                            "stage": "modality_analyzed",
                            "modality": result.modality.value,
                            "confidence": result.confidence
                        })
        else:
            # Execute analyses sequentially
            for task in analysis_tasks:
                try:
                    result = await task
                    analyses.append(result)
                    if stream:
                        await stream.send_metadata({
                            "stage": "modality_analyzed",
                            "modality": result.modality.value,
                            "confidence": result.confidence
                        })
                except Exception as e:
                    logger.error(f"Modality analysis failed: {e}")

        return analyses

    async def _analyze_text_modality(self, modality_data: ModalityData) -> ModalityAnalysis:
        """Analyze text modality"""

        start_time = time.time()
        text = modality_data.data if isinstance(modality_data.data, str) else modality_data.data.decode('utf-8')

        # Extract features from text
        features = await self._extract_text_features(text)

        # Analyze sentiment, intent, entities
        analysis_result = {
            "text": text,
            "length": len(text),
            "word_count": len(text.split()),
            "language": self._detect_language(text),
            "sentiment": features.get("sentiment"),
            "intent": features.get("intent"),
            "entities": features.get("entities", []),
            "keywords": features.get("keywords", []),
            "summary": features.get("summary")
        }

        processing_time = time.time() - start_time

        return ModalityAnalysis(
            modality=ModalityType.TEXT,
            analysis_type="text_analysis",
            result=analysis_result,
            confidence=0.9,  # High confidence for text analysis
            processing_time=processing_time,
            extracted_features=features
        )

    async def _analyze_image_modality(self, modality_data: ModalityData) -> ModalityAnalysis:
        """Analyze image modality"""

        start_time = time.time()
        image_data = modality_data.data if isinstance(modality_data.data, bytes) else modality_data.data.encode('latin-1')

        # Determine analysis types based on context
        analysis_types = [AnalysisType.GENERAL]
        if modality_data.metadata.get("contains_text", False):
            analysis_types.append(AnalysisType.OCR)

        # Perform vision analysis
        vision_results = await self.vision_service.analyze_image(
            image_data,
            analysis_types,
            context=modality_data.metadata
        )

        # Extract features from image analysis
        features = {}
        combined_result = {}

        for result in vision_results:
            if result.analysis_type == AnalysisType.GENERAL:
                combined_result["description"] = result.data.get("description", "")
                features["description"] = result.data.get("description", "")
            elif result.analysis_type == AnalysisType.OCR:
                combined_result["extracted_text"] = result.data.get("text", "")
                features["extracted_text"] = result.data.get("text", "")
                features["ocr_confidence"] = result.confidence

        processing_time = time.time() - start_time

        return ModalityAnalysis(
            modality=ModalityType.IMAGE,
            analysis_type="vision_analysis",
            result=combined_result,
            confidence=max(r.confidence for r in vision_results) if vision_results else 0.0,
            processing_time=processing_time,
            extracted_features=features
        )

    async def _analyze_audio_modality(self, modality_data: ModalityData) -> ModalityAnalysis:
        """Analyze audio modality"""

        start_time = time.time()
        audio_data = modality_data.data if isinstance(modality_data.data, bytes) else modality_data.data.encode('latin-1')

        # Determine if it's speech or sound
        is_speech = modality_data.metadata.get("is_speech", True)

        if is_speech:
            # Convert speech to text
            stt_result = await self.audio_service.speech_to_text(
                audio_data,
                modality_data.metadata.get("format", "audio/wav"),
                engine=SpeechEngine.GOOGLE,
                language=modality_data.metadata.get("language", "en-US")
            )

            analysis_result = {
                "transcript": stt_result.text,
                "confidence": stt_result.confidence,
                "language": stt_result.language,
                "words": stt_result.words,
                "processing_engine": stt_result.engine_used
            }

            features = {
                "transcript": stt_result.text,
                "speech_confidence": stt_result.confidence,
                "detected_language": stt_result.language
            }
        else:
            # Analyze as sound (placeholder implementation)
            analysis_result = {
                "type": "sound",
                "description": "Sound analysis not implemented in this version",
                "features": []
            }

            features = {"sound_type": "unknown"}

        processing_time = time.time() - start_time

        return ModalityAnalysis(
            modality=ModalityType.AUDIO,
            analysis_type="audio_analysis",
            result=analysis_result,
            confidence=analysis_result.get("confidence", 0.5),
            processing_time=processing_time,
            extracted_features=features
        )

    async def _analyze_video_modality(self, modality_data: ModalityData) -> ModalityAnalysis:
        """Analyze video modality (placeholder implementation)"""

        start_time = time.time()

        # Video analysis would involve frame extraction and analysis
        # For now, return a placeholder
        analysis_result = {
            "type": "video",
            "description": "Video analysis not implemented in this version",
            "duration": modality_data.metadata.get("duration", 0),
            "frame_count": 0
        }

        features = {"video_type": "unknown"}

        processing_time = time.time() - start_time

        return ModalityAnalysis(
            modality=ModalityType.VIDEO,
            analysis_type="video_analysis",
            result=analysis_result,
            confidence=0.0,
            processing_time=processing_time,
            extracted_features=features
        )

    async def _perform_cross_modal_reasoning(
        self,
        analyses: List[ModalityAnalysis],
        strategy: ReasoningStrategy,
        stream: Optional[ActiveStream] = None
    ) -> List[CrossModalInsight]:
        """Perform cross-modal reasoning to find connections and insights"""

        insights = []

        if stream:
            await stream.send_metadata({"stage": "cross_modal_reasoning"})

        # Look for connections between modalities
        for i, analysis1 in enumerate(analyses):
            for j, analysis2 in enumerate(analyses[i+1:], i+1):
                connection = await self._find_modal_connection(analysis1, analysis2)
                if connection:
                    insights.append(connection)

        # Look for contradictions or confirmations
        contradictions = await self._find_contradictions(analyses)
        insights.extend(contradictions)

        # Look for complementary information
        complementary = await self._find_complementary_info(analyses)
        insights.extend(complementary)

        # Sort insights by confidence
        insights.sort(key=lambda x: x.confidence, reverse=True)

        if stream:
            await stream.send_metadata({
                "stage": "cross_modal_completed",
                "insightCount": len(insights)
            })

        return insights

    async def _find_modal_connection(
        self,
        analysis1: ModalityAnalysis,
        analysis2: ModalityAnalysis
    ) -> Optional[CrossModalInsight]:
        """Find connections between two modalities"""

        # Text-Image connections
        if analysis1.modality == ModalityType.TEXT and analysis2.modality == ModalityType.IMAGE:
            return await self._find_text_image_connection(analysis1, analysis2)
        elif analysis1.modality == ModalityType.IMAGE and analysis2.modality == ModalityType.TEXT:
            return await self._find_text_image_connection(analysis2, analysis1)

        # Text-Audio connections
        if analysis1.modality == ModalityType.TEXT and analysis2.modality == ModalityType.AUDIO:
            return await self._find_text_audio_connection(analysis1, analysis2)
        elif analysis1.modality == ModalityType.AUDIO and analysis2.modality == ModalityType.TEXT:
            return await self._find_text_audio_connection(analysis2, analysis1)

        # Image-Audio connections
        if (analysis1.modality == ModalityType.IMAGE and analysis2.modality == ModalityType.AUDIO) or \
           (analysis1.modality == ModalityType.AUDIO and analysis2.modality == ModalityType.IMAGE):
            return await self._find_image_audio_connection(analysis1, analysis2)

        return None

    async def _find_text_image_connection(
        self,
        text_analysis: ModalityAnalysis,
        image_analysis: ModalityAnalysis
    ) -> Optional[CrossModalInsight]:
        """Find connections between text and image"""

        text_result = text_analysis.result
        image_result = image_analysis.result

        # Check if text mentions things in image
        text_keywords = set(text_result.get("keywords", []))
        image_description = image_result.get("description", "").lower()
        extracted_text = image_result.get("extracted_text", "").lower()

        connections = []
        for keyword in text_keywords:
            if keyword.lower() in image_description or keyword.lower() in extracted_text:
                connections.append(keyword)

        # Check for OCR text matching
        if extracted_text and any(word in extracted_text for word in text_result.get("text", "").split()):
            connections.append("Text matching in image")

        if connections:
            return CrossModalInsight(
                insight_type="text_image_correlation",
                description=f"Text content correlates with image content: {', '.join(connections)}",
                confidence=0.8,
                supporting_modalities=[ModalityType.TEXT, ModalityType.IMAGE],
                metadata={"connections": connections}
            )

        return None

    async def _find_text_audio_connection(
        self,
        text_analysis: ModalityAnalysis,
        audio_analysis: ModalityAnalysis
    ) -> Optional[CrossModalInsight]:
        """Find connections between text and audio"""

        text_result = text_analysis.result
        audio_result = audio_analysis.result

        # Check if audio transcript matches text
        transcript = audio_result.get("transcript", "")
        original_text = text_result.get("text", "")

        if transcript and original_text:
            # Simple similarity check
            similarity = self._calculate_text_similarity(transcript, original_text)

            if similarity > 0.8:
                return CrossModalInsight(
                    insight_type="text_audio_match",
                    description="Audio transcript closely matches provided text",
                    confidence=similarity,
                    supporting_modalities=[ModalityType.TEXT, ModalityType.AUDIO],
                    metadata={"similarity": similarity}
                )

        return None

    async def _find_image_audio_connection(
        self,
        image_analysis: ModalityAnalysis,
        audio_analysis: ModalityAnalysis
    ) -> Optional[CrossModalInsight]:
        """Find connections between image and audio"""

        image_result = image_analysis.result
        audio_result = audio_analysis.result

        # Check if audio mentions things in image
        transcript = audio_result.get("transcript", "").lower()
        image_description = image_result.get("description", "").lower()
        extracted_text = image_result.get("extracted_text", "").lower()

        connections = []
        image_words = set(image_description.split() + extracted_text.split())
        audio_words = set(transcript.split())

        overlap = image_words & audio_words
        if len(overlap) > 2:  # More than 2 overlapping words
            connections.extend(list(overlap)[:5])  # Top 5 connections

        if connections:
            return CrossModalInsight(
                insight_type="image_audio_correlation",
                description=f"Audio content mentions elements visible in image: {', '.join(connections)}",
                confidence=0.7,
                supporting_modalities=[ModalityType.IMAGE, ModalityType.AUDIO],
                metadata={"connections": connections}
            )

        return None

    async def _find_contradictions(self, analyses: List[ModalityAnalysis]) -> List[CrossModalInsight]:
        """Find contradictions between modalities"""

        contradictions = []

        # Look for contradictions between text descriptions
        text_analyses = [a for a in analyses if a.modality == ModalityType.TEXT]
        image_analyses = [a for a in analyses if a.modality == ModalityType.IMAGE]

        for text_analysis in text_analyses:
            for image_analysis in image_analyses:
                text_sentiment = text_analysis.extracted_features.get("sentiment", "neutral")
                image_description = image_analysis.result.get("description", "").lower()

                # Check for sentiment-image mismatch
                if text_sentiment == "positive" and any(negative in image_description for negative in ["sad", "angry", "broken", "damaged"]):
                    contradictions.append(CrossModalInsight(
                        insight_type="sentiment_mismatch",
                        description="Text sentiment is positive but image shows negative elements",
                        confidence=0.6,
                        supporting_modalities=[ModalityType.TEXT, ModalityType.IMAGE]
                    ))

        return contradictions

    async def _find_complementary_info(self, analyses: List[ModalityAnalysis]) -> List[CrossModalInsight]:
        """Find complementary information between modalities"""

        complementary = []

        # Look for OCR text that complements spoken text
        text_analyses = [a for a in analyses if a.modality == ModalityType.TEXT]
        image_analyses = [a for a in analyses if a.modality == ModalityType.IMAGE]
        audio_analyses = [a for a in analyses if a.modality == ModalityType.AUDIO]

        for image_analysis in image_analyses:
            extracted_text = image_analysis.result.get("extracted_text", "")
            if extracted_text:
                # Check if extracted text adds new information
                for text_analysis in text_analyses:
                    original_text = text_analysis.result.get("text", "")
                    if extracted_text not in original_text and len(extracted_text) > 10:
                        complementary.append(CrossModalInsight(
                            insight_type="additional_text",
                            description="Image contains additional text not present in main text",
                            confidence=0.8,
                            supporting_modalities=[ModalityType.IMAGE, ModalityType.TEXT],
                            metadata={"extracted_text": extracted_text[:100]}  # First 100 chars
                        ))

        return complementary

    async def _generate_integrated_response(
        self,
        analyses: List[ModalityAnalysis],
        insights: List[CrossModalInsight],
        multi_modal_input: MultiModalInput,
        stream: Optional[ActiveStream] = None
    ) -> str:
        """Generate integrated response combining all modalities"""

        if stream:
            await stream.send_metadata({"stage": "generating_response"})

        # Collect all information
        all_text = []
        all_descriptions = []
        all_insights = []

        for analysis in analyses:
            if analysis.modality == ModalityType.TEXT:
                all_text.append(analysis.result.get("text", ""))
            elif analysis.modality == ModalityType.IMAGE:
                desc = analysis.result.get("description", "")
                if desc:
                    all_descriptions.append(desc)
                extracted_text = analysis.result.get("extracted_text", "")
                if extracted_text:
                    all_text.append(f"[Image text: {extracted_text}]")
            elif analysis.modality == ModalityType.AUDIO:
                transcript = analysis.result.get("transcript", "")
                if transcript:
                    all_text.append(f"[Audio: {transcript}]")

        for insight in insights:
            all_insights.append(insight.description)

        # Generate comprehensive response
        response_parts = []

        if all_text:
            response_parts.append("Text Analysis: " + " ".join(all_text))

        if all_descriptions:
            response_parts.append("Visual Analysis: " + " ".join(all_descriptions))

        if all_insights:
            response_parts.append("Key Insights: " + "; ".join(all_insights))

        if len(response_parts) == 1:
            return response_parts[0]
        else:
            return "\n\n".join(response_parts)

    def _calculate_overall_confidence(
        self,
        analyses: List[ModalityAnalysis],
        insights: List[CrossModalInsight]
    ) -> float:
        """Calculate overall confidence based on analyses and insights"""

        if not analyses:
            return 0.0

        # Weight modality confidences
        modality_weights = {
            ModalityType.TEXT: 0.3,
            ModalityType.IMAGE: 0.3,
            ModalityType.AUDIO: 0.2,
            ModalityType.VIDEO: 0.2
        }

        weighted_confidence = 0.0
        total_weight = 0.0

        for analysis in analyses:
            weight = modality_weights.get(analysis.modality, 0.1)
            weighted_confidence += analysis.confidence * weight
            total_weight += weight

        if total_weight > 0:
            base_confidence = weighted_confidence / total_weight
        else:
            base_confidence = 0.0

        # Adjust based on insights
        if insights:
            insight_confidence = sum(insight.confidence for insight in insights) / len(insights)
            final_confidence = (base_confidence + insight_confidence) / 2
        else:
            final_confidence = base_confidence

        return min(1.0, max(0.0, final_confidence))

    async def _generate_recommendations(
        self,
        analyses: List[ModalityAnalysis],
        insights: List[CrossModalInsight],
        response: str
    ) -> List[str]:
        """Generate recommendations based on multi-modal analysis"""

        recommendations = []

        # Analyze response quality
        if len(response) < 50:
            recommendations.append("Consider providing more detailed input for better analysis")

        # Check for missing modalities
        modalities_present = {a.modality for a in analyses}
        if ModalityType.IMAGE not in modalities_present:
            recommendations.append("Consider adding images for visual context")

        if len(insights) == 0:
            recommendations.append("Modalities don't show strong connections - consider more related inputs")

        # Confidence-based recommendations
        avg_confidence = sum(a.confidence for a in analyses) / len(analyses) if analyses else 0.0
        if avg_confidence < 0.7:
            recommendations.append("Low confidence analysis - consider higher quality inputs")

        return recommendations

    async def _extract_text_features(self, text: str) -> Dict[str, Any]:
        """Extract features from text"""

        # Simple feature extraction (in production, use NLP libraries)
        features = {
            "sentiment": "neutral",  # Placeholder
            "intent": "unknown",     # Placeholder
            "entities": [],          # Placeholder
            "keywords": text.split()[:10],  # First 10 words as keywords
            "summary": text[:200] + "..." if len(text) > 200 else text
        }

        # Basic sentiment analysis
        positive_words = ["good", "great", "excellent", "amazing", "wonderful", "fantastic"]
        negative_words = ["bad", "terrible", "awful", "horrible", "disappointing", "poor"]

        positive_count = sum(1 for word in positive_words if word in text.lower())
        negative_count = sum(1 for word in negative_words if word in text.lower())

        if positive_count > negative_count:
            features["sentiment"] = "positive"
        elif negative_count > positive_count:
            features["sentiment"] = "negative"

        return features

    def _detect_language(self, text: str) -> str:
        """Detect language of text (simple heuristic)"""

        # Basic language detection based on common words
        text_lower = text.lower()

        if any(word in text_lower for word in ["the", "and", "is", "in", "to", "of"]):
            return "en"
        elif any(word in text_lower for word in ["le", "et", "est", "dans", "de", "un"]):
            return "fr"
        elif any(word in text_lower for word in ["el", "la", "es", "en", "de", "un"]):
            return "es"

        return "unknown"

    def _calculate_text_similarity(self, text1: str, text2: str) -> float:
        """Calculate similarity between two texts"""

        # Simple word-based similarity
        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())

        intersection = words1 & words2
        union = words1 | words2

        if len(union) == 0:
            return 0.0

        return len(intersection) / len(union)

# Global multi-modal reasoner instance
multimodal_reasoner: Optional[MultiModalReasoner] = None

def initialize_multimodal_reasoner(
    vision_service: VisionService,
    audio_service: AudioService,
    config: Dict[str, Any]
):
    """Initialize the global multi-modal reasoner"""

    global multimodal_reasoner
    multimodal_reasoner = MultiModalReasoner(vision_service, audio_service, config)
    logger.info("Multi-modal reasoner initialized")

def get_multimodal_reasoner() -> MultiModalReasoner:
    """Get the global multi-modal reasoner"""

    if multimodal_reasoner is None:
        raise RuntimeError("Multi-modal reasoner not initialized")

    return multimodal_reasoner