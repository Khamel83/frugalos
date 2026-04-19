#!/usr/bin/env python3
"""
Vision Service for Hermes AI Assistant
Provides image analysis, OCR, and vision-based AI capabilities
"""

import asyncio
import logging
from typing import Dict, Any, Optional, List, Union, BinaryIO
from dataclasses import dataclass
from enum import Enum
import base64
import io
import uuid
from datetime import datetime

import aiohttp
from PIL import Image, ImageOps
import pytesseract

logger = logging.getLogger(__name__)

class ImageFormat(Enum):
    """Supported image formats"""
    JPEG = "image/jpeg"
    PNG = "image/png"
    WEBP = "image/webp"
    BMP = "image/bmp"
    TIFF = "image/tiff"

class AnalysisType(Enum):
    """Types of vision analysis"""
    GENERAL = "general"
    OCR = "ocr"
    OBJECT_DETECTION = "object_detection"
    FACE_DETECTION = "face_detection"
    SCENE_ANALYSIS = "scene_analysis"
    DOCUMENT_ANALYSIS = "document_analysis"
    CHART_ANALYSIS = "chart_analysis"

@dataclass
class ImageInfo:
    """Image metadata and information"""
    filename: str
    format: ImageFormat
    size: tuple  # (width, height)
    file_size: int  # bytes
    mime_type: str
    has_transparency: bool
    color_mode: str
    created_at: datetime

@dataclass
class VisionAnalysisResult:
    """Result of vision analysis"""
    analysis_type: AnalysisType
    confidence: float
    data: Dict[str, Any]
    processing_time: float
    model_used: str
    image_info: ImageInfo

@dataclass
class OCRResult:
    """Result of OCR analysis"""
    text: str
    confidence: float
    words: List[Dict[str, Any]]
    lines: List[Dict[str, Any]]
    language: Optional[str]
    processing_time: float

@dataclass
class ObjectDetectionResult:
    """Result of object detection"""
    objects: List[Dict[str, Any]]
    total_objects: int
    confidence_threshold: float
    processing_time: float

class VisionService:
    """Vision processing service with multiple analysis capabilities"""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.openai_api_key = config.get("openai_api_key")
        self.anthropic_api_key = config.get("anthropic_api_key")
        self.google_vision_api_key = config.get("google_vision_api_key")
        self.ocr_enabled = config.get("ocr_enabled", True)
        self.max_image_size = config.get("max_image_size", 20 * 1024 * 1024)  # 20MB
        self.supported_formats = {
            "image/jpeg": ImageFormat.JPEG,
            "image/png": ImageFormat.PNG,
            "image/webp": ImageFormat.WEBP,
            "image/bmp": ImageFormat.BMP,
            "image/tiff": ImageFormat.TIFF
        }

    async def analyze_image(
        self,
        image_data: bytes,
        analysis_types: List[AnalysisType],
        filename: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> List[VisionAnalysisResult]:
        """
        Analyze image with specified analysis types

        Args:
            image_data: Raw image data
            analysis_types: List of analysis types to perform
            filename: Original filename (optional)
            context: Additional context for analysis (optional)

        Returns:
            List of analysis results
        """

        start_time = asyncio.get_event_loop().time()

        try:
            # Validate and process image
            image_info = await self._validate_and_process_image(image_data, filename)

            # Perform requested analyses
            results = []
            analysis_tasks = []

            for analysis_type in analysis_types:
                if analysis_type == AnalysisType.OCR and self.ocr_enabled:
                    analysis_tasks.append(self._perform_ocr(image_data, image_info))
                elif analysis_type == AnalysisType.GENERAL:
                    analysis_tasks.append(self._perform_general_analysis(image_data, image_info, context))
                elif analysis_type == AnalysisType.OBJECT_DETECTION:
                    analysis_tasks.append(self._perform_object_detection(image_data, image_info))
                elif analysis_type == AnalysisType.SCENE_ANALYSIS:
                    analysis_tasks.append(self._perform_scene_analysis(image_data, image_info, context))
                elif analysis_type == AnalysisType.DOCUMENT_ANALYSIS:
                    analysis_tasks.append(self._perform_document_analysis(image_data, image_info))
                elif analysis_type == AnalysisType.CHART_ANALYSIS:
                    analysis_tasks.append(self._perform_chart_analysis(image_data, image_info))

            # Execute analyses concurrently
            if analysis_tasks:
                analysis_results = await asyncio.gather(*analysis_tasks, return_exceptions=True)

                for i, result in enumerate(analysis_results):
                    if isinstance(result, Exception):
                        logger.error(f"Analysis {analysis_types[i].value} failed: {result}")
                        # Create error result
                        error_result = VisionAnalysisResult(
                            analysis_type=analysis_types[i],
                            confidence=0.0,
                            data={"error": str(result)},
                            processing_time=0.0,
                            model_used="error",
                            image_info=image_info
                        )
                        results.append(error_result)
                    else:
                        results.append(result)

            processing_time = asyncio.get_event_loop().time() - start_time
            logger.info(f"Vision analysis completed in {processing_time:.2f}s for {len(results)} analysis types")

            return results

        except Exception as e:
            logger.error(f"Error in image analysis: {e}")
            raise

    async def _validate_and_process_image(
        self,
        image_data: bytes,
        filename: Optional[str] = None
    ) -> ImageInfo:
        """Validate image and extract metadata"""

        # Check file size
        if len(image_data) > self.max_image_size:
            raise ValueError(f"Image size {len(image_data)} exceeds maximum {self.max_image_size}")

        try:
            # Load image with PIL
            image = Image.open(io.BytesIO(image_data))

            # Get image format
            mime_type = Image.MIME.get(image.format, "application/octet-stream")
            if mime_type not in self.supported_formats:
                raise ValueError(f"Unsupported image format: {mime_type}")

            image_format = self.supported_formats[mime_type]

            # Auto-orient image based on EXIF
            image = ImageOps.exif_transpose(image)

            # Convert to RGB if necessary
            if image.mode in ('RGBA', 'LA', 'P'):
                has_transparency = True
                image = image.convert('RGB')
            else:
                has_transparency = False

            return ImageInfo(
                filename=filename or "unknown",
                format=image_format,
                size=image.size,
                file_size=len(image_data),
                mime_type=mime_type,
                has_transparency=has_transparency,
                color_mode=image.mode,
                created_at=datetime.utcnow()
            )

        except Exception as e:
            raise ValueError(f"Invalid image data: {e}")

    async def _perform_ocr(
        self,
        image_data: bytes,
        image_info: ImageInfo
    ) -> VisionAnalysisResult:
        """Perform OCR text extraction"""

        start_time = asyncio.get_event_loop().time()

        try:
            # Run OCR in thread pool (pytesseract is synchronous)
            loop = asyncio.get_event_loop()
            pil_image = Image.open(io.BytesIO(image_data))

            # Extract text with confidence data
            ocr_data = await loop.run_in_executor(
                None,
                lambda: pytesseract.image_to_data(
                    pil_image,
                    output_type=pytesseract.Output.DICT,
                    config='--psm 6 --oem 3'
                )
            )

            # Process OCR results
            words = []
            lines = []
            full_text = ""
            total_confidence = 0
            word_count = 0

            # Group words by line
            current_line = None
            current_line_text = ""
            current_line_confidence = 0
            line_word_count = 0

            for i in range(len(ocr_data['text'])):
                word = ocr_data['text'][i].strip()
                if word:
                    confidence = int(ocr_data['conf'][i])
                    bbox = {
                        'x': ocr_data['left'][i],
                        'y': ocr_data['top'][i],
                        'width': ocr_data['width'][i],
                        'height': ocr_data['height'][i]
                    }

                    word_info = {
                        'text': word,
                        'confidence': confidence,
                        'bbox': bbox
                    }
                    words.append(word_info)

                    full_text += word + " "
                    total_confidence += confidence
                    word_count += 1

                    # Group into lines (simplified)
                    if current_line is None:
                        current_line = ocr_data['top'][i]
                        current_line_text = word
                        current_line_confidence = confidence
                        line_word_count = 1
                    elif abs(ocr_data['top'][i] - current_line) < 20:  # Same line
                        current_line_text += " " + word
                        current_line_confidence = max(current_line_confidence, confidence)
                        line_word_count += 1
                    else:  # New line
                        if current_line_text:
                            lines.append({
                                'text': current_line_text,
                                'confidence': current_line_confidence,
                                'word_count': line_word_count
                            })
                        current_line = ocr_data['top'][i]
                        current_line_text = word
                        current_line_confidence = confidence
                        line_word_count = 1

            # Add last line
            if current_line_text:
                lines.append({
                    'text': current_line_text,
                    'confidence': current_line_confidence,
                    'word_count': line_word_count
                })

            # Calculate average confidence
            avg_confidence = total_confidence / max(1, word_count)

            # Detect language (basic detection)
            language = self._detect_language(full_text)

            processing_time = asyncio.get_event_loop().time() - start_time

            ocr_result = OCRResult(
                text=full_text.strip(),
                confidence=avg_confidence,
                words=words,
                lines=lines,
                language=language,
                processing_time=processing_time
            )

            return VisionAnalysisResult(
                analysis_type=AnalysisType.OCR,
                confidence=avg_confidence,
                data=ocr_result.__dict__,
                processing_time=processing_time,
                model_used="tesseract",
                image_info=image_info
            )

        except Exception as e:
            logger.error(f"OCR analysis failed: {e}")
            raise

    async def _perform_general_analysis(
        self,
        image_data: bytes,
        image_info: ImageInfo,
        context: Optional[Dict[str, Any]] = None
    ) -> VisionAnalysisResult:
        """Perform general image analysis using AI models"""

        start_time = asyncio.get_event_loop().time()

        try:
            # Encode image for API
            base64_image = base64.b64encode(image_data).decode('utf-8')

            # Use OpenAI Vision API
            if self.openai_api_key:
                result = await self._analyze_with_openai(base64_image, image_info, context)
            elif self.anthropic_api_key:
                result = await self._analyze_with_anthropic(base64_image, image_info, context)
            else:
                # Fallback to basic analysis
                result = await self._perform_basic_analysis(image_data, image_info)

            processing_time = asyncio.get_event_loop().time() - start_time

            return VisionAnalysisResult(
                analysis_type=AnalysisType.GENERAL,
                confidence=result.get("confidence", 0.8),
                data=result,
                processing_time=processing_time,
                model_used=result.get("model", "basic"),
                image_info=image_info
            )

        except Exception as e:
            logger.error(f"General analysis failed: {e}")
            raise

    async def _analyze_with_openai(
        self,
        base64_image: str,
        image_info: ImageInfo,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Analyze image using OpenAI Vision API"""

        headers = {
            "Authorization": f"Bearer {self.openai_api_key}",
            "Content-Type": "application/json"
        }

        # Build prompt based on context
        prompt = "Analyze this image in detail. Describe what you see, including objects, scenes, text, and any notable features."
        if context:
            if "focus" in context:
                prompt += f" Pay special attention to: {context['focus']}"
            if "question" in context:
                prompt += f" Answer this question about the image: {context['question']}"

        payload = {
            "model": "gpt-4-vision-preview",
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": prompt
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{image_info.mime_type};base64,{base64_image}"
                            }
                        }
                    ]
                }
            ],
            "max_tokens": 1000
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://api.openai.com/v1/chat/completions",
                headers=headers,
                json=payload
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise Exception(f"OpenAI API error: {response.status} - {error_text}")

                result = await response.json()

                content = result["choices"][0]["message"]["content"]

                return {
                    "description": content,
                    "model": "gpt-4-vision-preview",
                    "confidence": 0.9
                }

    async def _analyze_with_anthropic(
        self,
        base64_image: str,
        image_info: ImageInfo,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Analyze image using Anthropic Vision API"""

        headers = {
            "x-api-key": self.anthropic_api_key,
            "Content-Type": "application/json",
            "anthropic-version": "2023-06-01"
        }

        # Build prompt
        prompt = "Analyze this image in detail. Describe what you see comprehensively."
        if context:
            if "focus" in context:
                prompt += f" Focus on: {context['focus']}"
            if "question" in context:
                prompt += f" Answer: {context['question']}"

        payload = {
            "model": "claude-3-opus-20240229",
            "max_tokens": 1000,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": prompt
                        },
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": image_info.mime_type,
                                "data": base64_image
                            }
                        }
                    ]
                }
            ]
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://api.anthropic.com/v1/messages",
                headers=headers,
                json=payload
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise Exception(f"Anthropic API error: {response.status} - {error_text}")

                result = await response.json()

                content = result["content"][0]["text"]

                return {
                    "description": content,
                    "model": "claude-3-opus",
                    "confidence": 0.95
                }

    async def _perform_basic_analysis(
        self,
        image_data: bytes,
        image_info: ImageInfo
    ) -> Dict[str, Any]:
        """Perform basic image analysis without external APIs"""

        image = Image.open(io.BytesIO(image_data))

        # Basic image properties
        width, height = image.size
        aspect_ratio = width / height

        # Color analysis
        colors = image.getcolors(maxcolors=256*256*256)
        dominant_color = max(colors, key=lambda x: x[0]) if colors else (0, (0, 0, 0))

        # Determine image characteristics
        if width > height * 2:
            orientation = "panoramic"
        elif height > width * 2:
            orientation = "portrait"
        else:
            orientation = "square"

        # Determine if it's likely a photo vs graphic
        if image_info.mime_type in ["image/jpeg", "image/webp"]:
            likely_type = "photograph"
        else:
            likely_type = "graphic"

        return {
            "description": f"This appears to be a {orientation} {likely_type} with dimensions {width}x{height} pixels. "
                          f"The dominant color is RGB{dominant_color[1]}. "
                          f"Basic analysis only - advanced features require external API keys.",
            "dimensions": {"width": width, "height": height, "aspect_ratio": aspect_ratio},
            "orientation": orientation,
            "likely_type": likely_type,
            "dominant_color": dominant_color[1],
            "model": "basic_analysis",
            "confidence": 0.5
        }

    async def _perform_object_detection(
        self,
        image_data: bytes,
        image_info: ImageInfo
    ) -> VisionAnalysisResult:
        """Perform object detection (placeholder implementation)"""

        # This would integrate with a service like Google Vision API or a local model
        # For now, return a placeholder result

        return VisionAnalysisResult(
            analysis_type=AnalysisType.OBJECT_DETECTION,
            confidence=0.0,
            data={
                "objects": [],
                "message": "Object detection requires additional configuration and API access"
            },
            processing_time=0.1,
            model_used="placeholder",
            image_info=image_info
        )

    async def _perform_scene_analysis(
        self,
        image_data: bytes,
        image_info: ImageInfo,
        context: Optional[Dict[str, Any]] = None
    ) -> VisionAnalysisResult:
        """Perform scene analysis (delegates to general analysis)"""

        return await self._perform_general_analysis(image_data, image_info, context)

    async def _perform_document_analysis(
        self,
        image_data: bytes,
        image_info: ImageInfo
    ) -> VisionAnalysisResult:
        """Perform document analysis (focused OCR)"""

        # Perform OCR with document-specific settings
        result = await self._perform_ocr(image_data, image_info)

        # Enhance for document analysis
        ocr_data = result.data
        if ocr_data.get("text"):
            # Basic document structure analysis
            text = ocr_data["text"]
            lines = text.split('\n')

            # Detect potential document type
            if any(keyword in text.lower() for keyword in ["invoice", "bill", "total", "amount"]):
                doc_type = "invoice"
            elif any(keyword in text.lower() for keyword in ["receipt", "purchase", "payment"]):
                doc_type = "receipt"
            elif any(keyword in text.lower() for keyword in ["contract", "agreement", "terms"]):
                doc_type = "contract"
            else:
                doc_type = "document"

            ocr_data["document_type"] = doc_type
            ocr_data["line_count"] = len([line for line in lines if line.strip()])
            ocr_data["word_count"] = len(text.split())

        return result

    async def _perform_chart_analysis(
        self,
        image_data: bytes,
        image_info: ImageInfo
    ) -> VisionAnalysisResult:
        """Perform chart analysis (specialized analysis)"""

        # This would involve detecting charts, graphs, and extracting data
        # For now, delegate to general analysis with chart context

        return await self._perform_general_analysis(
            image_data,
            image_info,
            {"focus": "charts, graphs, data visualizations, axes, labels, and numerical data"}
        )

    def _detect_language(self, text: str) -> Optional[str]:
        """Basic language detection from OCR text"""

        # Simple heuristic based on common words
        text_lower = text.lower()

        if any(word in text_lower for word in ["the", "and", "is", "in", "to", "of"]):
            return "en"
        elif any(word in text_lower for word in ["le", "et", "est", "dans", "de", "un"]):
            return "fr"
        elif any(word in text_lower for word in ["el", "la", "es", "en", "de", "un"]):
            return "es"
        elif any(word in text_lower for word in ["der", "die", "das", "und", "ist", "in"]):
            return "de"

        return None

# Global vision service instance
vision_service: Optional[VisionService] = None

def initialize_vision_service(config: Dict[str, Any]):
    """Initialize the global vision service"""

    global vision_service
    vision_service = VisionService(config)
    logger.info("Vision service initialized")

def get_vision_service() -> VisionService:
    """Get the global vision service"""

    if vision_service is None:
        raise RuntimeError("Vision service not initialized")

    return vision_service