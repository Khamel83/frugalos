"""
FastAPI Routes for Local-First Router
Add these to the main Hermes FastAPI app
"""
from typing import Optional
from pydantic import BaseModel
from fastapi import APIRouter, HTTPException

from .router import LocalFirstRouter


# Create router
router = APIRouter(prefix="/api/v1/routing", tags=["routing"])

# Initialize the local-first router
local_first_router = LocalFirstRouter()


# Request/Response models
class PromptRequest(BaseModel):
    prompt: str
    session_id: Optional[str] = None
    auto_upgrade: bool = False


class UpgradeRequest(BaseModel):
    session_id: str
    prompt: str
    model: Optional[str] = None


class SessionResponse(BaseModel):
    session_id: str
    tier: str
    task_count: int
    total_cost: float
    started_at: str
    ended_at: Optional[str] = None


# Routes
@router.post("/process")
async def process_prompt(request: PromptRequest):
    """
    Process a prompt using local-first approach

    1. Tries local models first
    2. Returns local result if quality >= 9/10
    3. Otherwise shows upgrade options with session cost analysis
    """

    try:
        result = local_first_router.process_prompt(
            prompt=request.prompt,
            session_id=request.session_id,
            auto_upgrade=request.auto_upgrade
        )
        return result

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/upgrade")
async def upgrade_to_cloud(request: UpgradeRequest):
    """
    Upgrade to cloud model after seeing local result

    User has seen the costs and session analysis, now approving cloud upgrade
    """

    try:
        result = local_first_router.upgrade_to_cloud(
            session_id=request.session_id,
            prompt=request.prompt,
            model=request.model
        )

        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])

        return result

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/session/{session_id}")
async def get_session_status(session_id: str):
    """Get current session status"""

    status = local_first_router.get_session_status(session_id)

    if not status:
        raise HTTPException(status_code=404, detail="Session not found")

    return status


@router.post("/session/{session_id}/end")
async def end_session(session_id: str):
    """End a session"""

    try:
        local_first_router.end_session(session_id)
        return {"message": "Session ended successfully"}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats")
async def get_stats(days: int = 7):
    """Get cost statistics for recent days"""

    try:
        stats = local_first_router.database.get_cost_stats(days)
        return stats

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sessions/recent")
async def get_recent_sessions(limit: int = 10):
    """Get recent sessions"""

    try:
        sessions = local_first_router.database.get_recent_sessions(limit)
        return {"sessions": sessions}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Health check
@router.get("/health")
async def health_check():
    """Check if routing system is working"""

    try:
        # Test local connection
        local_models = local_first_router.local_runner.local_models
        has_api_key = bool(local_first_router.cloud_runner.api_key)

        return {
            "status": "healthy",
            "local_models_configured": len(local_models),
            "cloud_api_configured": has_api_key
        }

    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e)
        }
