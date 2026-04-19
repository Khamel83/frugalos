#!/usr/bin/env python3
"""
Audio Service for Hermes AI Assistant
Provides speech-to-text, text-to-speech, and audio processing capabilities
"""

import asyncio
import logging
from typing import Dict, Any, Optional, List, Union, BinaryIO
from dataclasses import dataclass
from enum import Enum
import io
import uuid
from datetime import datetime
import base64
import tempfile
import os

import aiohttp
import aiofiles
import numpy as np
from pydub import AudioSegment
import speech_recognition as sr
from pyttsx3 import init as tts_init

logger = logging.getLogger(__name__)

class AudioFormat(Enum):
    """Supported audio formats"""
    WAV = "audio/wav"
    MP3 = "audio/mpeg"
    OGG = "audio/ogg"
    FLAC = "audio/flac"
    M4A = "audio/mp4"
    WEBM = "audio/webm"

class SpeechEngine(Enum):
    """Speech recognition engines"""
    GOOGLE = "google"
    WHISPER = "whisper"
    AZURE = "azure"
    AWS = "aws"

class VoiceEngine(Enum):
    """Text-to-speech engines"""
    NATIVE = "native"
    OPENAI = "openai"
    AZURE = "azure"
    AWS = "aws"
    GOOGLE = "google"

@dataclass
class AudioInfo:
    """Audio metadata and information"""
    filename: str
    format: AudioFormat
    duration: float  # seconds
    sample_rate: int
    channels: int
    file_size: int  # bytes
    bitrate: Optional[int] = None
    created_at: datetime = None

@dataclass
class SpeechToTextResult:
    """Result of speech-to-text conversion"""
    text: str
    confidence: float
    language: Optional[str]
    words: List[Dict[str, Any]]
    processing_time: float
    engine_used: str

@dataclass
class TextToSpeechResult:
    """Result of text-to-speech conversion"""
    audio_data: bytes
    format: AudioFormat
    duration: float
    processing_time: float
    engine_used: str
    voice_used: Optional[str] = None

class AudioService:
    """Audio processing service with speech capabilities"""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.openai_api_key = config.get("openai_api_key")
        self.azure_speech_key = config.get("azure_speech_key")
        self.aws_polly_key = config.get("aws_polly_key")
        self.google_speech_key = config.get("google_speech_key")

        # Configuration
        self.max_audio_size = config.get("max_audio_size", 50 * 1024 * 1024)  # 50MB
        self.default_sample_rate = config.get("default_sample_rate", 16000)
        self.supported_formats = {
            "audio/wav": AudioFormat.WAV,
            "audio/mpeg": AudioFormat.MP3,
            "audio/ogg": AudioFormat.OGG,
            "audio/flac": AudioFormat.FLAC,
            "audio/mp4": AudioFormat.M4A,
            "audio/webm": AudioFormat.WEBM
        }

        # Initialize speech recognizer
        self.recognizer = sr.Recognizer()
        self.tts_engine = tts_init()

        # Configure recognizer
        self.recognizer.energy_threshold = 300
        self.recognizer.dynamic_energy_threshold = True
        self.recognizer.pause_threshold = 0.8

    async def speech_to_text(
        self,
        audio_data: bytes,
        audio_format: AudioFormat,
        engine: SpeechEngine = SpeechEngine.GOOGLE,
        language: str = "en-US",
        context: Optional[Dict[str, Any]] = None
    ) -> SpeechToTextResult:
        """
        Convert speech to text using specified engine

        Args:
            audio_data: Raw audio data
            audio_format: Audio format
            engine: Speech recognition engine to use
            language: Language code (e.g., "en-US")
            context: Additional context for recognition

        Returns:
            SpeechToTextResult with transcription and metadata
        """

        start_time = asyncio.get_event_loop().time()

        try:
            # Validate and process audio
            audio_info = await self._validate_and_process_audio(audio_data, audio_format)

            # Convert to WAV format for processing
            wav_data = await self._convert_to_wav(audio_data, audio_format)

            # Use specified recognition engine
            if engine == SpeechEngine.GOOGLE:
                result = await self._recognize_with_google(wav_data, language, audio_info)
            elif engine == SpeechEngine.WHISPER and self.openai_api_key:
                result = await self._recognize_with_whisper(audio_data, language, audio_info)
            elif engine == SpeechEngine.AZURE and self.azure_speech_key:
                result = await self._recognize_with_azure(wav_data, language, audio_info)
            else:
                # Fallback to Google
                result = await self._recognize_with_google(wav_data, language, audio_info)

            processing_time = asyncio.get_event_loop().time() - start_time

            return SpeechToTextResult(
                text=result["text"],
                confidence=result["confidence"],
                language=result.get("language"),
                words=result.get("words", []),
                processing_time=processing_time,
                engine_used=engine.value
            )

        except Exception as e:
            logger.error(f"Speech-to-text conversion failed: {e}")
            raise

    async def text_to_speech(
        self,
        text: str,
        engine: VoiceEngine = VoiceEngine.NATIVE,
        voice: Optional[str] = None,
        format: AudioFormat = AudioFormat.MP3,
        language: str = "en",
        speed: float = 1.0,
        context: Optional[Dict[str, Any]] = None
    ) -> TextToSpeechResult:
        """
        Convert text to speech using specified engine

        Args:
            text: Text to convert to speech
            engine: Text-to-speech engine to use
            voice: Voice ID or name
            format: Output audio format
            language: Language code
            speed: Speech speed multiplier
            context: Additional context for synthesis

        Returns:
            TextToSpeechResult with audio data and metadata
        """

        start_time = asyncio.get_event_loop().time()

        try:
            # Validate input
            if not text or not text.strip():
                raise ValueError("Text cannot be empty")

            # Use specified TTS engine
            if engine == VoiceEngine.OPENAI and self.openai_api_key:
                result = await self._synthesize_with_openai(text, voice, format, language, speed)
            elif engine == VoiceEngine.AZURE and self.azure_speech_key:
                result = await self._synthesize_with_azure(text, voice, format, language, speed)
            elif engine == VoiceEngine.AWS and self.aws_polly_key:
                result = await self._synthesize_with_aws(text, voice, format, language, speed)
            elif engine == VoiceEngine.GOOGLE and self.google_speech_key:
                result = await self._synthesize_with_google(text, voice, format, language, speed)
            else:
                # Fallback to native TTS
                result = await self._synthesize_with_native(text, voice, format, language, speed)

            processing_time = asyncio.get_event_loop().time() - start_time

            return TextToSpeechResult(
                audio_data=result["audio_data"],
                format=result["format"],
                duration=result["duration"],
                processing_time=processing_time,
                engine_used=engine.value,
                voice_used=result.get("voice_used")
            )

        except Exception as e:
            logger.error(f"Text-to-speech conversion failed: {e}")
            raise

    async def _validate_and_process_audio(
        self,
        audio_data: bytes,
        audio_format: AudioFormat
    ) -> AudioInfo:
        """Validate audio and extract metadata"""

        # Check file size
        if len(audio_data) > self.max_audio_size:
            raise ValueError(f"Audio size {len(audio_data)} exceeds maximum {self.max_audio_size}")

        try:
            # Load audio with pydub
            audio = AudioSegment.from_file(io.BytesIO(audio_data))

            return AudioInfo(
                filename="audio",
                format=audio_format,
                duration=len(audio) / 1000.0,  # milliseconds to seconds
                sample_rate=audio.frame_rate,
                channels=audio.channels,
                file_size=len(audio_data),
                bitrate=audio.frame_rate * audio.channels * 2,  # Approximate
                created_at=datetime.utcnow()
            )

        except Exception as e:
            raise ValueError(f"Invalid audio data: {e}")

    async def _convert_to_wav(self, audio_data: bytes, input_format: AudioFormat) -> bytes:
        """Convert audio to WAV format for processing"""

        try:
            # Load audio
            audio = AudioSegment.from_file(io.BytesIO(audio_data))

            # Convert to mono and 16kHz sample rate for speech recognition
            audio = audio.set_channels(1)
            audio = audio.set_frame_rate(16000)

            # Export as WAV
            wav_buffer = io.BytesIO()
            audio.export(wav_buffer, format="wav")
            return wav_buffer.getvalue()

        except Exception as e:
            logger.error(f"Audio conversion to WAV failed: {e}")
            raise

    async def _recognize_with_google(
        self,
        wav_data: bytes,
        language: str,
        audio_info: AudioInfo
    ) -> Dict[str, Any]:
        """Recognize speech using Google Speech Recognition"""

        try:
            # Use temporary file for speech recognition
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
                temp_file.write(wav_data)
                temp_file_path = temp_file.name

            try:
                # Run recognition in thread pool
                loop = asyncio.get_event_loop()

                with sr.AudioFile(temp_file_path) as source:
                    audio = self.recognizer.record(source)

                # Recognize using Google Speech Recognition
                text = await loop.run_in_executor(
                    None,
                    lambda: self.recognizer.recognize_google(
                        audio,
                        language=language,
                        show_all=True
                    )
                )

                if isinstance(text, dict) and "alternative" in text:
                    # Get best result
                    best_alternative = text["alternative"][0]
                    recognized_text = best_alternative["transcript"]
                    confidence = best_alternative.get("confidence", 0.0)

                    # Extract word-level information if available
                    words = []
                    if "result" in text:
                        for result in text["result"]:
                            if "alternative" in result:
                                alt = result["alternative"][0]
                                if "words" in alt:
                                    words.extend(alt["words"])
                else:
                    recognized_text = text
                    confidence = 0.8  # Default confidence
                    words = []

                return {
                    "text": recognized_text,
                    "confidence": confidence,
                    "language": language,
                    "words": words
                }

            finally:
                # Clean up temporary file
                try:
                    os.unlink(temp_file_path)
                except:
                    pass

        except sr.UnknownValueError:
            return {
                "text": "",
                "confidence": 0.0,
                "language": language,
                "words": [],
                "error": "Could not understand audio"
            }
        except sr.RequestError as e:
            logger.error(f"Google Speech Recognition error: {e}")
            raise Exception(f"Speech recognition service error: {e}")

    async def _recognize_with_whisper(
        self,
        audio_data: bytes,
        language: str,
        audio_info: AudioInfo
    ) -> Dict[str, Any]:
        """Recognize speech using OpenAI Whisper API"""

        headers = {
            "Authorization": f"Bearer {self.openai_api_key}",
            "Content-Type": "multipart/form-data"
        }

        # Prepare form data
        form_data = aiohttp.FormData()
        form_data.add_field('file', audio_data, filename='audio.wav', content_type='audio/wav')
        form_data.add_field('model', 'whisper-1')
        form_data.add_field('language', language.split('-')[0])  # Whisper uses language codes like 'en'

        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://api.openai.com/v1/audio/transcriptions",
                headers=headers,
                data=form_data
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise Exception(f"Whisper API error: {response.status} - {error_text}")

                result = await response.json()

                return {
                    "text": result["text"],
                    "confidence": 0.95,  # Whisper typically has high accuracy
                    "language": language,
                    "words": []  # Whisper doesn't provide word-level timing by default
                }

    async def _recognize_with_azure(
        self,
        wav_data: bytes,
        language: str,
        audio_info: AudioInfo
    ) -> Dict[str, Any]:
        """Recognize speech using Azure Speech Services"""

        # Azure Speech Services implementation
        # This would require the Azure SDK for Speech
        # For now, return a placeholder

        return {
            "text": "Azure speech recognition not implemented in this demo",
            "confidence": 0.0,
            "language": language,
            "words": [],
            "error": "Azure Speech Services integration requires additional setup"
        }

    async def _synthesize_with_native(
        self,
        text: str,
        voice: Optional[str],
        format: AudioFormat,
        language: str,
        speed: float
    ) -> Dict[str, Any]:
        """Synthesize speech using native TTS engine"""

        try:
            # Configure TTS engine
            if voice:
                self.tts_engine.setProperty('voice', voice)

            # Set speech rate
            self.tts_engine.setProperty('rate', int(200 * speed))

            # Generate speech to temporary file
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
                temp_file_path = temp_file.name

            self.tts_engine.save_to_file(text, temp_file_path)
            self.tts_engine.runAndWait()

            # Read generated audio
            async with aiofiles.open(temp_file_path, 'rb') as f:
                audio_data = await f.read()

            # Convert to requested format if needed
            if format != AudioFormat.WAV:
                audio = AudioSegment.from_wav(temp_file_path)

                # Convert format
                format_map = {
                    AudioFormat.MP3: "mp3",
                    AudioFormat.OGG: "ogg",
                    AudioFormat.FLAC: "flac"
                }

                if format in format_map:
                    output_buffer = io.BytesIO()
                    audio.export(output_buffer, format=format_map[format])
                    audio_data = output_buffer.getvalue()

            # Clean up
            try:
                os.unlink(temp_file_path)
            except:
                pass

            # Calculate duration
            audio = AudioSegment.from_file(io.BytesIO(audio_data))
            duration = len(audio) / 1000.0

            return {
                "audio_data": audio_data,
                "format": format,
                "duration": duration,
                "voice_used": voice or "default"
            }

        except Exception as e:
            logger.error(f"Native TTS synthesis failed: {e}")
            raise

    async def _synthesize_with_openai(
        self,
        text: str,
        voice: Optional[str],
        format: AudioFormat,
        language: str,
        speed: float
    ) -> Dict[str, Any]:
        """Synthesize speech using OpenAI TTS API"""

        headers = {
            "Authorization": f"Bearer {self.openai_api_key}",
            "Content-Type": "application/json"
        }

        # Map format to OpenAI format
        format_map = {
            AudioFormat.MP3: "mp3",
            AudioFormat.OPUS: "opus",
            AudioFormat.AAC: "aac",
            AudioFormat.FLAC: "flac"
        }

        openai_format = format_map.get(format, "mp3")

        # Default voices for OpenAI
        voice_map = {
            "alloy": "alloy",
            "echo": "echo",
            "fable": "fable",
            "onyx": "onyx",
            "nova": "nova",
            "shimmer": "shimmer"
        }

        selected_voice = voice_map.get(voice or "alloy", "alloy")

        payload = {
            "model": "tts-1",
            "input": text,
            "voice": selected_voice,
            "response_format": openai_format,
            "speed": speed
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://api.openai.com/v1/audio/speech",
                headers=headers,
                json=payload
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise Exception(f"OpenAI TTS API error: {response.status} - {error_text}")

                audio_data = await response.read()

                # Calculate approximate duration (rough estimate)
                # OpenAI doesn't return duration, so we estimate based on word count
                word_count = len(text.split())
                estimated_duration = word_count * 0.6  # ~0.6 seconds per word average

                return {
                    "audio_data": audio_data,
                    "format": format,
                    "duration": estimated_duration,
                    "voice_used": selected_voice
                }

    async def _synthesize_with_azure(
        self,
        text: str,
        voice: Optional[str],
        format: AudioFormat,
        language: str,
        speed: float
    ) -> Dict[str, Any]:
        """Synthesize speech using Azure Speech Services"""

        # Azure Speech Services implementation
        # This would require the Azure SDK for Speech

        return {
            "audio_data": b"",
            "format": format,
            "duration": 0.0,
            "voice_used": voice or "azure",
            "error": "Azure Speech Services integration requires additional setup"
        }

    async def _synthesize_with_aws(
        self,
        text: str,
        voice: Optional[str],
        format: AudioFormat,
        language: str,
        speed: float
    ) -> Dict[str, Any]:
        """Synthesize speech using AWS Polly"""

        # AWS Polly implementation
        # This would require boto3 and AWS credentials

        return {
            "audio_data": b"",
            "format": format,
            "duration": 0.0,
            "voice_used": voice or "aws",
            "error": "AWS Polly integration requires additional setup"
        }

    async def _synthesize_with_google(
        self,
        text: str,
        voice: Optional[str],
        format: AudioFormat,
        language: str,
        speed: float
    ) -> Dict[str, Any]:
        """Synthesize speech using Google Text-to-Speech"""

        # Google Cloud TTS implementation
        # This would require the Google Cloud TTS library

        return {
            "audio_data": b"",
            "format": format,
            "duration": 0.0,
            "voice_used": voice or "google",
            "error": "Google Cloud TTS integration requires additional setup"
        }

    def get_supported_languages(self) -> Dict[str, List[str]]:
        """Get supported languages for speech recognition and synthesis"""

        return {
            "speech_to_text": [
                "en-US", "en-GB", "en-AU", "en-CA",
                "es-ES", "es-MX", "es-AR",
                "fr-FR", "fr-CA",
                "de-DE", "de-AT",
                "it-IT",
                "pt-BR", "pt-PT",
                "ru-RU",
                "ja-JP",
                "ko-KR",
                "zh-CN", "zh-TW"
            ],
            "text_to_speech": [
                "en", "es", "fr", "de", "it", "pt", "ru", "ja", "ko", "zh"
            ]
        }

    def get_supported_voices(self, engine: VoiceEngine) -> List[Dict[str, Any]]:
        """Get available voices for TTS engine"""

        if engine == VoiceEngine.NATIVE:
            # Get available system voices
            voices = []
            for voice in self.tts_engine.getProperty('voices'):
                voices.append({
                    "id": voice.id,
                    "name": voice.name,
                    "languages": voice.languages,
                    "gender": voice.gender
                })
            return voices

        # Placeholder for cloud-based voices
        return [
            {"id": "alloy", "name": "Alloy", "language": "en", "gender": "neutral"},
            {"id": "echo", "name": "Echo", "language": "en", "gender": "male"},
            {"id": "fable", "name": "Fable", "language": "en", "gender": "neutral"},
            {"id": "onyx", "name": "Onyx", "language": "en", "gender": "male"},
            {"id": "nova", "name": "Nova", "language": "en", "gender": "female"},
            {"id": "shimmer", "name": "Shimmer", "language": "en", "gender": "female"}
        ]

# Global audio service instance
audio_service: Optional[AudioService] = None

def initialize_audio_service(config: Dict[str, Any]):
    """Initialize the global audio service"""

    global audio_service
    audio_service = AudioService(config)
    logger.info("Audio service initialized")

def get_audio_service() -> AudioService:
    """Get the global audio service"""

    if audio_service is None:
        raise RuntimeError("Audio service not initialized")

    return audio_service