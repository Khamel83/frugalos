#!/usr/bin/env python3
"""
Personalization API Routes for Hermes AI Assistant
Provides endpoints for user preference learning, personalized responses, and adaptive conversations
"""

from fastapi import APIRouter, HTTPException, status, Depends, Query, Body
from pydantic import BaseModel, Field
from typing import Dict, Any, Optional, List
import logging
import asyncio
from datetime import datetime, timedelta

from ..personalization.user_profiler import get_user_profiler
from ..personalization.personalized_generator import get_personalized_generator
from ..personalization.contextual_awareness import get_contextual_awareness_engine
from ..personalization.adaptive_conversations import get_adaptive_conversation_engine, ConversationStrategy, InteractionPattern
from ..security.auth_service import get_current_user, User
from ..monitoring.performance_monitor import performance_monitor

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/personalization", tags=["personalization"])

# Request/Response Models
class InteractionData(BaseModel):
    """Model for interaction data"""
    message: str = Field(..., min_length=1, max_length=10000, description="User's message")
    response: str = Field(..., min_length=1, max_length=10000, description="AI's response")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional interaction metadata")

class PersonalizationRequest(BaseModel):
    """Request model for response personalization"""
    user_id: str = Field(..., description="User identifier")
    original_response: str = Field(..., min_length=1, max_length=10000, description="Original AI response")
    context: Optional[Dict[str, Any]] = Field(None, description="Additional context for personalization")

class ContextAnalysisRequest(BaseModel):
    """Request model for context analysis"""
    user_id: str = Field(..., description="User identifier")
    message: str = Field(..., min_length=1, max_length=10000, description="User's message")
    response: str = Field(..., min_length=1, max_length=10000, description="AI's response")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")

class ConversationPatternRequest(BaseModel):
    """Request model for conversation pattern analysis"""
    user_id: str = Field(..., description="User identifier")
    conversation_history: List[Dict[str, Any]] = Field(..., description="Recent conversation history")
    current_context: Optional[Dict[str, Any]] = Field(None, description="Current conversation context")

class StrategyAdaptationRequest(BaseModel):
    """Request model for strategy adaptation"""
    user_id: str = Field(..., description="User identifier")
    current_strategy: str = Field(..., description="Current conversation strategy")
    performance_feedback: Optional[Dict[str, Any]] = Field(None, description="Performance feedback")
    context: Optional[Dict[str, Any]] = Field(None, description="Current context")

# Response Models
class UserProfileResponse(BaseModel):
    """Response model for user profile"""
    success: bool
    user_id: str
    created_at: str
    last_updated: str
    total_interactions: int
    preferences: Dict[str, Any]
    topic_affinities: Dict[str, float]
    communication_patterns: Dict[str, Any]
    adaptation_count: int

class PersonalizationResponse(BaseModel):
    """Response model for response personalization"""
    success: bool
    original_response: str
    personalized_response: str
    adaptations_applied: List[str]
    confidence_score: float
    processing_time: float
    personalization_directives: Dict[str, Any]

class ContextAnalysisResponse(BaseModel):
    """Response model for context analysis"""
    success: bool
    user_id: str
    signals_extracted: int
    insights_generated: int
    context_snapshot: Dict[str, Any]
    top_insights: List[Dict[str, Any]]
    processing_time: float

class PatternAnalysisResponse(BaseModel):
    """Response model for pattern analysis"""
    success: bool
    user_id: str
    interaction_pattern: str
    conversation_phase: str
    conversation_metrics: Dict[str, Any]
    recommended_adaptations: List[Dict[str, Any]]
    processing_time: float

class StrategyAdaptationResponse(BaseModel):
    """Response model for strategy adaptation"""
    success: bool
    user_id: str
    adaptation_needed: bool
    current_strategy: Optional[str]
    new_strategy: Optional[str]
    adaptation_id: Optional[str]
    reason: Optional[str]
    directives: List[Dict[str, Any]]
    performance_score: Optional[float]

# User Profile Endpoints
@router.post("/profile/interaction")
async def process_interaction(
    interaction: InteractionData,
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Process user interaction to learn preferences
    """

    try:
        user_profiler = get_user_profiler()

        result = await user_profiler.process_interaction(
            user_id=current_user.user_id,
            message=interaction.message,
            response=interaction.response,
            metadata=interaction.metadata
        )

        # Log request
        await performance_monitor.log_api_request(
            endpoint="/api/v1/personalization/profile/interaction",
            method="POST",
            user_id=current_user.user_id,
            request_size=len(str(interaction)),
            status_code=200
        )

        return result

    except Exception as e:
        logger.error(f"Error processing interaction: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process interaction"
        )

@router.get("/profile")
async def get_user_profile(
    current_user: User = Depends(get_current_user)
) -> UserProfileResponse:
    """
    Get user's personalization profile
    """

    try:
        user_profiler = get_user_profiler()
        profile_data = await user_profiler.get_user_profile(current_user.user_id)

        if not profile_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User profile not found"
            )

        return UserProfileResponse(**profile_data)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting user profile: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get user profile"
        )

@router.get("/profile/summary")
async def get_preference_summary(
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Get summary of user's learned preferences
    """

    try:
        user_profiler = get_user_profiler()
        summary = await user_profiler.get_preference_summary(current_user.user_id)

        if not summary:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User profile not found"
            )

        return summary

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting preference summary: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get preference summary"
        )

@router.delete("/profile")
async def reset_user_profile(
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Reset user's personalization profile
    """

    try:
        user_profiler = get_user_profiler()

        # Remove user profile (simplified implementation)
        if hasattr(user_profiler, 'user_profiles') and current_user.user_id in user_profiler.user_profiles:
            del user_profiler.user_profiles[current_user.user_id]
            return {
                "success": True,
                "message": "User profile reset successfully",
                "user_id": current_user.user_id
            }
        else:
            return {
                "success": False,
                "message": "No profile found to reset",
                "user_id": current_user.user_id
            }

    except Exception as e:
        logger.error(f"Error resetting user profile: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to reset user profile"
        )

# Personalized Response Endpoints
@router.post("/personalize")
async def personalize_response(
    request: PersonalizationRequest,
    current_user: User = Depends(get_current_user)
) -> PersonalizationResponse:
    """
    Personalize a response based on user preferences
    """

    try:
        # Validate user_id matches current user
        if request.user_id != current_user.user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot personalize response for different user"
            )

        personalized_generator = get_personalized_generator()

        result = await personalized_generator.personalize_response(
            user_id=request.user_id,
            original_response=request.original_response,
            context=request.context
        )

        return PersonalizationResponse(
            success=True,
            original_response=result.original_response,
            personalized_response=result.personalized_response,
            adaptations_applied=result.adaptations_applied,
            confidence_score=result.confidence_score,
            processing_time=result.processing_time,
            personalization_directives={
                "communication_style": result.personalization_directives.communication_style.value,
                "response_length": result.personalization_directives.response_length.value,
                "tone_preference": result.personalization_directives.tone_preference.value,
                "technical_level": result.personalization_directives.technical_level.value
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error personalizing response: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to personalize response"
        )

@router.get("/personalization/capabilities")
async def get_personalization_capabilities(
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Get available personalization capabilities
    """

    try:
        return {
            "supported_styles": [
                "formal", "casual", "technical", "conversational",
                "concise", "detailed", "creative", "analytical"
            ],
            "supported_lengths": [
                "brief", "moderate", "detailed", "comprehensive"
            ],
            "supported_tones": [
                "professional", "friendly", "enthusiastic", "calm",
                "humorous", "empathetic", "direct", "supportive"
            ],
            "supported_levels": [
                "beginner", "intermediate", "advanced", "expert"
            ],
            "features": [
                "communication_style_matching",
                "response_length_adjustment",
                "tone_alignment",
                "technical_level_adaptation",
                "vocabulary_complexity_adjustment",
                "topic_relevance_enhancement"
            ]
        }

    except Exception as e:
        logger.error(f"Error getting personalization capabilities: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get personalization capabilities"
        )

# Contextual Awareness Endpoints
@router.post("/context/analyze")
async def analyze_context(
    request: ContextAnalysisRequest,
    current_user: User = Depends(get_current_user)
) -> ContextAnalysisResponse:
    """
    Analyze interaction context and extract insights
    """

    try:
        # Validate user_id matches current user
        if request.user_id != current_user.user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot analyze context for different user"
            )

        contextual_engine = get_contextual_awareness_engine()

        result = await contextual_engine.process_interaction_context(
            user_id=request.user_id,
            message=request.message,
            response=request.response,
            metadata=request.metadata
        )

        return ContextAnalysisResponse(
            success=result["success"],
            user_id=result["user_id"],
            signals_extracted=result["signals_extracted"],
            insights_generated=result["insights_generated"],
            context_snapshot=result["context_snapshot"],
            top_insights=result["top_insights"],
            processing_time=result["processing_time"]
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error analyzing context: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to analyze context"
        )

@router.get("/context/understanding")
async def get_contextual_understanding(
    user_id: Optional[str] = Query(None, description="User ID (defaults to current user)"),
    time_range_hours: Optional[int] = Query(24, description="Time range in hours"),
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Get comprehensive contextual understanding for a user
    """

    try:
        # Use current user if no user_id provided
        target_user_id = user_id or current_user.user_id

        # Users can only access their own understanding unless they have admin privileges
        if target_user_id != current_user.user_id and current_user.role != "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot access context understanding for different user"
            )

        contextual_engine = get_contextual_awareness_engine()

        time_range = timedelta(hours=time_range_hours) if time_range_hours else None

        result = await contextual_engine.get_contextual_understanding(
            user_id=target_user_id,
            time_range=time_range
        )

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting contextual understanding: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get contextual understanding"
        )

@router.get("/context/prediction")
async def predict_next_context(
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Predict the context of the next user interaction
    """

    try:
        contextual_engine = get_contextual_awareness_engine()

        result = await contextual_engine.predict_next_interaction_context(
            user_id=current_user.user_id
        )

        return result

    except Exception as e:
        logger.error(f"Error predicting next context: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to predict next context"
        )

# Adaptive Conversation Endpoints
@router.post("/conversation/analyze")
async def analyze_conversation_pattern(
    request: ConversationPatternRequest,
    current_user: User = Depends(get_current_user)
) -> PatternAnalysisResponse:
    """
    Analyze conversation patterns and recommend strategies
    """

    try:
        # Validate user_id matches current user
        if request.user_id != current_user.user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot analyze conversation pattern for different user"
            )

        adaptive_engine = get_adaptive_conversation_engine()

        result = await adaptive_engine.analyze_conversation_pattern(
            user_id=request.user_id,
            conversation_history=request.conversation_history,
            current_context=request.current_context
        )

        return PatternAnalysisResponse(
            success=result["success"],
            user_id=result["user_id"],
            interaction_pattern=result["interaction_pattern"],
            conversation_phase=result["conversation_phase"],
            conversation_metrics=result["conversation_metrics"],
            recommended_adaptations=result["recommended_adaptations"],
            processing_time=result["processing_time"]
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error analyzing conversation pattern: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to analyze conversation pattern"
        )

@router.post("/conversation/adapt")
async def adapt_conversation_strategy(
    request: StrategyAdaptationRequest,
    current_user: User = Depends(get_current_user)
) -> StrategyAdaptationResponse:
    """
    Adapt conversation strategy based on performance
    """

    try:
        # Validate user_id matches current user
        if request.user_id != current_user.user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot adapt conversation strategy for different user"
            )

        adaptive_engine = get_adaptive_conversation_engine()

        # Parse strategy
        try:
            current_strategy = ConversationStrategy(request.current_strategy)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid strategy: {request.current_strategy}"
            )

        result = await adaptive_engine.adapt_conversation_strategy(
            user_id=request.user_id,
            current_strategy=current_strategy,
            performance_feedback=request.performance_feedback,
            context=request.context
        )

        return StrategyAdaptationResponse(
            success=result["success"],
            user_id=result["user_id"],
            adaptation_needed=result["adaptation_needed"],
            current_strategy=result.get("current_strategy"),
            new_strategy=result.get("new_strategy"),
            adaptation_id=result.get("adaptation_id"),
            reason=result.get("reason"),
            directives=result.get("directives", []),
            performance_score=result.get("performance_score")
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error adapting conversation strategy: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to adapt conversation strategy"
        )

@router.get("/conversation/recommendations")
async def get_conversation_recommendations(
    situation_type: str = Query("general", description="Type of situation"),
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Get recommendations for handling current conversation situation
    """

    try:
        adaptive_engine = get_adaptive_conversation_engine()

        current_situation = {
            "situation_type": situation_type,
            "timestamp": datetime.utcnow().isoformat(),
            "user_id": current_user.user_id
        }

        result = await adaptive_engine.get_conversation_recommendations(
            user_id=current_user.user_id,
            current_situation=current_situation
        )

        return result

    except Exception as e:
        logger.error(f"Error getting conversation recommendations: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get conversation recommendations"
        )

@router.post("/conversation/track-effectiveness")
async def track_strategy_effectiveness(
    strategy: str = Query(..., description="Strategy that was used"),
    interaction_outcome: Dict[str, Any] = Body(..., description="Results of the interaction"),
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Track effectiveness of applied conversation strategy
    """

    try:
        adaptive_engine = get_adaptive_conversation_engine()

        # Parse strategy
        try:
            conversation_strategy = ConversationStrategy(strategy)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid strategy: {strategy}"
            )

        result = await adaptive_engine.track_strategy_effectiveness(
            user_id=current_user.user_id,
            strategy=conversation_strategy,
            interaction_outcome=interaction_outcome
        )

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error tracking strategy effectiveness: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to track strategy effectiveness"
        )

# Utility Endpoints
@router.get("/strategies")
async def get_available_strategies(
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Get list of available conversation strategies with descriptions
    """

    try:
        strategies = {
            "guided_discovery": {
                "name": "Guided Discovery",
                "description": "Guides user through self-discovery process with open-ended questions",
                "best_for": ["learning", "exploration", "self-reflection"]
            },
            "collaborative_exploration": {
                "name": "Collaborative Exploration",
                "description": "Works collaboratively to explore topics together",
                "best_for": ["brainstorming", "creative work", "partnership"]
            },
            "socratic_method": {
                "name": "Socratic Method",
                "description": "Uses Socratic questioning to stimulate critical thinking",
                "best_for": ["education", "problem-solving", "analysis"]
            },
            "direct_assistance": {
                "name": "Direct Assistance",
                "description": "Provides direct and clear assistance",
                "best_for": ["urgent problems", "clear answers", "efficiency"]
            },
            "educational_tutoring": {
                "name": "Educational Tutoring",
                "description": "Acts as an educational tutor with structured learning",
                "best_for": ["learning", "skill development", "knowledge building"]
            },
            "brainstorming_partner": {
                "name": "Brainstorming Partner",
                "description": "Participates in creative brainstorming sessions",
                "best_for": ["creativity", "idea generation", "innovation"]
            },
            "problem_solving": {
                "name": "Problem Solving",
                "description": "Follows structured problem-solving methodology",
                "best_for": ["technical problems", "complex challenges", "analysis"]
            },
            "decision_support": {
                "name": "Decision Support",
                "description": "Helps with structured decision-making processes",
                "best_for": ["decisions", "choices", "planning"]
            }
        }

        return {
            "strategies": strategies,
            "total_count": len(strategies),
            "user_can_adapt": True
        }

    except Exception as e:
        logger.error(f"Error getting available strategies: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get available strategies"
        )

@router.get("/patterns")
async def get_interaction_patterns(
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Get list of interaction patterns with descriptions
    """

    try:
        patterns = {
            "question_asker": {
                "name": "Question Asker",
                "description": "User primarily asks questions and seeks information",
                "characteristics": ["High question frequency", "Information seeking", "Curious"]
            },
            "information_seeker": {
                "name": "Information Seeker",
                "description": "User seeks specific information and explanations",
                "characteristics": ["Goal-oriented", "Specific queries", "Knowledge building"]
            },
            "problem_presenter": {
                "name": "Problem Presenter",
                "description": "User presents problems and seeks solutions",
                "characteristics": ["Problem-focused", "Solution seeking", "Challenge-oriented"]
            },
            "idea_generator": {
                "name": "Idea Generator",
                "description": "User generates ideas and creative content",
                "characteristics": ["Creative", "Innovative", "Imaginative"]
            },
            "reflective_thinker": {
                "name": "Reflective Thinker",
                "description": "User engages in reflective and analytical thinking",
                "characteristics": ["Thoughtful", "Analytical", "Self-reflective"]
            },
            "quick_querier": {
                "name": "Quick Querier",
                "description": "User asks quick, specific questions",
                "characteristics": ["Brief", "Specific", "Efficient"]
            },
            "detailed_explorer": {
                "name": "Detailed Explorer",
                "description": "User explores topics in depth with detailed questions",
                "characteristics": ["Thorough", "In-depth", "Comprehensive"]
            }
        }

        return {
            "patterns": patterns,
            "total_count": len(patterns),
            "auto_detection": True
        }

    except Exception as e:
        logger.error(f"Error getting interaction patterns: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get interaction patterns"
        )

@router.get("/health")
async def personalization_health_check(
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Health check for personalization services
    """

    try:
        health_status = {
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "services": {
                "user_profiler": "active",
                "personalized_generator": "active",
                "contextual_awareness": "active",
                "adaptive_conversations": "active"
            },
            "features": {
                "preference_learning": True,
                "response_personalization": True,
                "contextual_understanding": True,
                "adaptive_strategies": True
            }
        }

        # Test each service
        try:
            user_profiler = get_user_profiler()
            health_status["services"]["user_profiler"] = "active"
        except Exception as e:
            health_status["services"]["user_profiler"] = f"error: {str(e)}"
            health_status["status"] = "degraded"

        try:
            personalized_generator = get_personalized_generator()
            health_status["services"]["personalized_generator"] = "active"
        except Exception as e:
            health_status["services"]["personalized_generator"] = f"error: {str(e)}"
            health_status["status"] = "degraded"

        try:
            contextual_engine = get_contextual_awareness_engine()
            health_status["services"]["contextual_awareness"] = "active"
        except Exception as e:
            health_status["services"]["contextual_awareness"] = f"error: {str(e)}"
            health_status["status"] = "degraded"

        try:
            adaptive_engine = get_adaptive_conversation_engine()
            health_status["services"]["adaptive_conversations"] = "active"
        except Exception as e:
            health_status["services"]["adaptive_conversations"] = f"error: {str(e)}"
            health_status["status"] = "degraded"

        return health_status

    except Exception as e:
        logger.error(f"Error in personalization health check: {e}")
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }