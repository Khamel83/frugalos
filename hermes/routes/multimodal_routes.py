#!/usr/bin/env python3
"""
Multi-Modal API Routes for Hermes AI Assistant
Provides endpoints for vision, audio, and multi-modal reasoning
"""

from fastapi import APIRouter, HTTPException, status, Depends, UploadFile, File, Form, Query
from pydantic import BaseModel, Field
from typing import Dict, Any, Optional, List
import logging
import base64
import io

from ..vision.vision_service import get_vision_service, AnalysisType
from ..audio.audio_service import get_audio_service, AudioFormat, SpeechEngine, VoiceEngine
from ..multimodal.multimodal_reasoner import get_multimodal_reasoner, MultiModalInput, ModalityData, ModalityType, ReasoningStrategy
from ..security.auth_service import get_current_user, User
from ..monitoring.performance_monitor import performance_monitor

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/multimodal", tags=["multimodal"])

# Vision endpoints
class VisionAnalysisRequest(BaseModel):
    """Request model for vision analysis"""
    analysis_types: List[str] = Field(..., description="Types of analysis to perform")
    context: Optional[Dict[str, Any]] = Field(None, description="Additional context")

class VisionAnalysisResponse(BaseModel):
    """Response model for vision analysis"""
    success: bool
    analyses: List[Dict[str, Any]]
    processing_time: float
    image_info: Dict[str, Any]

@router.post("/vision/analyze")
async def analyze_image(
    file: UploadFile = File(..., description="Image file to analyze"),
    analysis_types: str = Form(..., description="Comma-separated list of analysis types"),
    context: Optional[str] = Form(None, description="JSON context string"),
    current_user: User = Depends(get_current_user)
) -> VisionAnalysisResponse:
    """
    Analyze uploaded image with specified analysis types

    Supported analysis types: general, ocr, object_detection, scene_analysis, document_analysis, chart_analysis
    """

    try:
        # Validate file type
        if not file.content_type or not file.content_type.startswith('image/'):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File must be an image"
            )

        # Parse analysis types
        analysis_type_list = [t.strip() for t in analysis_types.split(',')]
        valid_types = {t.value for t in AnalysisType}
        invalid_types = set(analysis_type_list) - valid_types

        if invalid_types:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid analysis types: {', '.join(invalid_types)}"
            )

        # Convert to AnalysisType enums
        analysis_types_enum = [AnalysisType(t) for t in analysis_type_list]

        # Parse context
        context_dict = {}
        if context:
            import json
            try:
                context_dict = json.loads(context)
            except json.JSONDecodeError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid JSON context"
                )

        # Read image data
        image_data = await file.read()

        # Get vision service and analyze
        vision_service = get_vision_service()
        results = await vision_service.analyze_image(
            image_data,
            analysis_types_enum,
            filename=file.filename,
            context=context_dict
        )

        # Format response
        analyses = []
        for result in results:
            analyses.append({
                "type": result.analysis_type.value,
                "confidence": result.confidence,
                "data": result.data,
                "processing_time": result.processing_time,
                "model_used": result.model_used
            })

        total_processing_time = sum(result.processing_time for result in results)

        response = VisionAnalysisResponse(
            success=True,
            analyses=analyses,
            processing_time=total_processing_time,
            image_info={
                "filename": file.filename,
                "format": results[0].image_info.format.value if results else "unknown",
                "size": results[0].image_info.size if results else (0, 0),
                "file_size": results[0].image_info.file_size if results else len(image_data)
            }
        )

        # Log request
        await performance_monitor.log_api_request(
            endpoint="/api/v1/multimodal/vision/analyze",
            method="POST",
            user_id=current_user.user_id,
            request_size=len(image_data),
            status_code=200
        )

        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in image analysis: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to analyze image"
        )

# Audio endpoints
class SpeechToTextRequest(BaseModel):
    """Request model for speech-to-text"""
    engine: str = Field("google", description="Speech recognition engine")
    language: str = Field("en-US", description="Language code")
    context: Optional[Dict[str, Any]] = Field(None, description="Additional context")

class SpeechToTextResponse(BaseModel):
    """Response model for speech-to-text"""
    success: bool
    text: str
    confidence: float
    language: Optional[str]
    words: List[Dict[str, Any]]
    processing_time: float
    engine_used: str

class TextToSpeechRequest(BaseModel):
    """Request model for text-to-speech"""
    text: str = Field(..., min_length=1, max_length=1000, description="Text to convert")
    engine: str = Field("native", description="TTS engine")
    voice: Optional[str] = Field(None, description="Voice ID or name")
    format: str = Field("mp3", description="Output audio format")
    language: str = Field("en", description="Language code")
    speed: float = Field(1.0, ge=0.25, le=4.0, description="Speech speed")

@router.post("/audio/speech-to-text")
async def speech_to_text(
    file: UploadFile = File(..., description="Audio file"),
    engine: str = Form("google", description="Speech recognition engine"),
    language: str = Form("en-US", description="Language code"),
    current_user: User = Depends(get_current_user)
) -> SpeechToTextResponse:
    """
    Convert speech in audio file to text

    Supported engines: google, whisper (requires OpenAI API key)
    """

    try:
        # Validate file type
        if not file.content_type or not file.content_type.startswith('audio/'):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File must be an audio file"
            )

        # Parse audio format
        format_map = {
            "audio/wav": AudioFormat.WAV,
            "audio/mpeg": AudioFormat.MP3,
            "audio/ogg": AudioFormat.OGG,
            "audio/flac": AudioFormat.FLAC,
            "audio/mp4": AudioFormat.M4A,
            "audio/webm": AudioFormat.WEBM
        }

        if file.content_type not in format_map:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported audio format: {file.content_type}"
            )

        audio_format = format_map[file.content_type]

        # Parse engine
        try:
            speech_engine = SpeechEngine(engine.lower())
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported speech engine: {engine}"
            )

        # Read audio data
        audio_data = await file.read()

        # Get audio service and convert
        audio_service = get_audio_service()
        result = await audio_service.speech_to_text(
            audio_data,
            audio_format,
            engine=speech_engine,
            language=language
        )

        response = SpeechToTextResponse(
            success=bool(result.text),
            text=result.text,
            confidence=result.confidence,
            language=result.language,
            words=result.words,
            processing_time=result.processing_time,
            engine_used=result.engine_used
        )

        # Log request
        await performance_monitor.log_api_request(
            endpoint="/api/v1/multimodal/audio/speech-to-text",
            method="POST",
            user_id=current_user.user_id,
            request_size=len(audio_data),
            status_code=200
        )

        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in speech-to-text: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to convert speech to text"
        )

@router.post("/audio/text-to-speech")
async def text_to_speech(
    request: TextToSpeechRequest,
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Convert text to speech

    Returns base64-encoded audio data
    """

    try:
        # Parse engine
        try:
            voice_engine = VoiceEngine(request.engine.lower())
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported TTS engine: {request.engine}"
            )

        # Parse format
        format_map = {
            "wav": AudioFormat.WAV,
            "mp3": AudioFormat.MP3,
            "ogg": AudioFormat.OGG,
            "flac": AudioFormat.FLAC
        }

        if request.format not in format_map:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported audio format: {request.format}"
            )

        audio_format = format_map[request.format]

        # Get audio service and synthesize
        audio_service = get_audio_service()
        result = await audio_service.text_to_speech(
            text=request.text,
            engine=voice_engine,
            voice=request.voice,
            format=audio_format,
            language=request.language,
            speed=request.speed
        )

        # Encode audio data as base64
        audio_base64 = base64.b64encode(result.audio_data).decode('utf-8')

        response_data = {
            "success": True,
            "audio_data": audio_base64,
            "format": result.format.value,
            "duration": result.duration,
            "processing_time": result.processing_time,
            "engine_used": result.engine_used,
            "voice_used": result.voice_used
        }

        # Log request
        await performance_monitor.log_api_request(
            endpoint="/api/v1/multimodal/audio/text-to-speech",
            method="POST",
            user_id=current_user.user_id,
            request_size=len(request.text),
            status_code=200
        )

        return response_data

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in text-to-speech: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to convert text to speech"
        )

# Multi-modal endpoints
class MultiModalReasoningRequest(BaseModel):
    """Request model for multi-modal reasoning"""
    input_id: str = Field(..., description="Unique identifier for this input")
    reasoning_strategy: str = Field("integrated", description="Reasoning strategy")
    context: Optional[Dict[str, Any]] = Field(None, description="Additional context")
    modalities: List[Dict[str, Any]] = Field(..., description="List of modality data")

class MultiModalReasoningResponse(BaseModel):
    """Response model for multi-modal reasoning"""
    success: bool
    input_id: str
    reasoning_strategy: str
    modality_analyses: List[Dict[str, Any]]
    cross_modal_insights: List[Dict[str, Any]]
    integrated_response: str
    confidence: float
    processing_time: float
    recommendations: List[str]

@router.post("/reasoning")
async def multi_modal_reasoning(
    request: MultiModalReasoningRequest,
    current_user: User = Depends(get_current_user)
) -> MultiModalReasoningResponse:
    """
    Perform multi-modal reasoning across text, image, and audio inputs

    Modalities format:
    - Text: {"type": "text", "data": "text content"}
    - Image: {"type": "image", "data": "base64_image_data", "metadata": {...}}
    - Audio: {"type": "audio", "data": "base64_audio_data", "metadata": {...}}
    """

    try:
        # Parse reasoning strategy
        try:
            strategy = ReasoningStrategy(request.reasoning_strategy.lower())
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported reasoning strategy: {request.reasoning_strategy}"
            )

        # Parse modalities
        modality_data_list = []
        for modality in request.modalities:
            modality_type_str = modality.get("type", "").lower()
            data = modality.get("data", "")
            metadata = modality.get("metadata", {})

            try:
                modality_type = ModalityType(modality_type_str)
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Unsupported modality type: {modality_type_str}"
                )

            # Convert base64 data for binary modalities
            if modality_type in [ModalityType.IMAGE, ModalityType.AUDIO, ModalityType.VIDEO]:
                if isinstance(data, str):
                    binary_data = base64.b64decode(data)
                else:
                    binary_data = data
                modality_data = ModalityData(
                    modality=modality_type,
                    data=binary_data,
                    metadata=metadata
                )
            else:
                modality_data = ModalityData(
                    modality=modality_type,
                    data=data,
                    metadata=metadata
                )

            modality_data_list.append(modality_data)

        if not modality_data_list:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="At least one modality must be provided"
            )

        # Create multi-modal input
        multi_modal_input = MultiModalInput(
            input_id=request.input_id,
            modalities=modality_data_list,
            context=request.context,
            reasoning_strategy=strategy,
            user_id=current_user.user_id
        )

        # Get multi-modal reasoner and process
        reasoner = get_multimodal_reasoner()
        result = await reasoner.reason(multi_modal_input)

        # Format response
        modality_analyses = []
        for analysis in result.modality_analyses:
            modality_analyses.append({
                "modality": analysis.modality.value,
                "analysis_type": analysis.analysis_type,
                "result": analysis.result,
                "confidence": analysis.confidence,
                "processing_time": analysis.processing_time,
                "extracted_features": analysis.extracted_features
            })

        cross_modal_insights = []
        for insight in result.cross_modal_insights:
            cross_modal_insights.append({
                "insight_type": insight.insight_type,
                "description": insight.description,
                "confidence": insight.confidence,
                "supporting_modalities": [m.value for m in insight.supporting_modalities],
                "metadata": insight.metadata
            })

        response = MultiModalReasoningResponse(
            success=True,
            input_id=result.input_id,
            reasoning_strategy=result.reasoning_strategy.value,
            modality_analyses=modality_analyses,
            cross_modal_insights=cross_modal_insights,
            integrated_response=result.integrated_response,
            confidence=result.confidence,
            processing_time=result.processing_time,
            recommendations=result.recommendations
        )

        # Log request
        await performance_monitor.log_api_request(
            endpoint="/api/v1/multimodal/reasoning",
            method="POST",
            user_id=current_user.user_id,
            request_size=len(str(request)),
            status_code=200
        )

        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in multi-modal reasoning: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to perform multi-modal reasoning"
        )

# Utility endpoints
@router.get("/capabilities")
async def get_capabilities(
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """Get available multi-modal capabilities"""

    try:
        vision_service = get_vision_service()
        audio_service = get_audio_service()

        return {
            "vision": {
                "supported_formats": ["image/jpeg", "image/png", "image/webp", "image/bmp", "image/tiff"],
                "analysis_types": [t.value for t in AnalysisType],
                "max_image_size": vision_service.max_image_size
            },
            "audio": {
                "supported_formats": ["audio/wav", "audio/mpeg", "audio/ogg", "audio/flac", "audio/mp4", "audio/webm"],
                "speech_engines": [e.value for e in SpeechEngine],
                "voice_engines": [e.value for e in VoiceEngine],
                "max_audio_size": audio_service.max_audio_size,
                "supported_languages": audio_service.get_supported_languages()
            },
            "multimodal": {
                "supported_modalities": [m.value for m in ModalityType],
                "reasoning_strategies": [s.value for s in ReasoningStrategy],
                "max_concurrent_reasoning": 10
            }
        }

    except Exception as e:
        logger.error(f"Error getting capabilities: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get capabilities"
        )