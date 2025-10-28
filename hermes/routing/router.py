"""
Main Router - Local-First AI Routing Logic
This is the core of the MVP - try local first, show upgrade costs when needed
"""
from typing import Dict, Optional
from datetime import datetime

from .local_runner import LocalModelRunner, LocalResult
from .cloud_runner import CloudModelRunner, CloudResult
from .session import Session, SessionManager
from .database import RoutingDatabase
from .config import QUALITY_THRESHOLDS


class LocalFirstRouter:
    """
    Core routing logic:
    1. Try local models first
    2. Check if quality meets 9/10 target
    3. If not, show upgrade options with costs
    4. Track sessions to avoid context loss
    """

    def __init__(self):
        self.local_runner = LocalModelRunner()
        self.cloud_runner = CloudModelRunner()
        self.session_manager = SessionManager()
        self.database = RoutingDatabase()

    def process_prompt(self, prompt: str, session_id: Optional[str] = None, auto_upgrade: bool = False) -> Dict:
        """
        Process a prompt using local-first approach

        Args:
            prompt: User's prompt
            session_id: Optional session ID to continue conversation
            auto_upgrade: If True, automatically upgrade to cloud if local fails

        Returns:
            Dict with result, cost analysis, and upgrade options
        """

        # Get or create session
        session = self._get_or_create_session(session_id)

        # Step 1: ALWAYS try local first
        local_result = self.local_runner.get_best_local_result(prompt)

        # Step 2: Check if local is good enough
        if local_result.quality_score >= QUALITY_THRESHOLDS["target"]:
            # Local success!
            return self._handle_local_success(session, prompt, local_result)

        # Step 3: Local not good enough - show upgrade options
        upgrade_options = self.cloud_runner.get_upgrade_options(prompt, local_result.quality_score)

        # Get session cost analysis
        if upgrade_options:
            best_option = upgrade_options[0]
            session_analysis = session.get_session_analysis(best_option["estimated_cost"])
        else:
            session_analysis = {}

        # If auto_upgrade enabled and we have options, upgrade automatically
        if auto_upgrade and upgrade_options:
            return self._handle_cloud_upgrade(session, prompt, local_result, upgrade_options[0])

        # Return local result with upgrade options for user decision
        return self._format_upgrade_decision(session, prompt, local_result, upgrade_options, session_analysis)

    def upgrade_to_cloud(self, session_id: str, prompt: str, model: Optional[str] = None) -> Dict:
        """
        User approved cloud upgrade - process with cloud model

        Args:
            session_id: Session ID
            prompt: The prompt to process
            model: Optional specific model to use

        Returns:
            Cloud result with costs
        """

        session = self.session_manager.get_session(session_id)
        if not session:
            return {"error": "Session not found"}

        # Get local result for comparison
        local_result = self.local_runner.get_best_local_result(prompt)

        # Use specified model or default to best option
        if not model:
            upgrade_options = self.cloud_runner.get_upgrade_options(prompt, local_result.quality_score)
            model = upgrade_options[0]["model"] if upgrade_options else "anthropic/claude-3.5-sonnet"

        # Run cloud model
        cloud_result = self.cloud_runner.run_prompt(prompt, model)

        if not cloud_result.success:
            return {"error": f"Cloud model failed: {cloud_result.error}"}

        # Upgrade session to cloud if not already
        if session.tier == "local":
            session.upgrade_to_cloud()

        # Add task to session
        session.add_task(
            prompt=prompt,
            response=cloud_result.response,
            model=cloud_result.model,
            cost=cloud_result.cost,
            quality_score=cloud_result.quality_score
        )

        # Save to database
        self._save_task_to_db(session, prompt, local_result, cloud_result, "cloud")

        return {
            "status": "cloud_success",
            "response": cloud_result.response,
            "model": cloud_result.model,
            "quality": cloud_result.quality_score,
            "cost": cloud_result.cost,
            "session": {
                "session_id": session.session_id,
                "tier": session.tier,
                "total_cost": session.total_cost,
                "task_count": session.task_count
            }
        }

    def _get_or_create_session(self, session_id: Optional[str]) -> Session:
        """Get existing session or create new one"""

        if session_id:
            session = self.session_manager.get_session(session_id)
            if session:
                return session

        return self.session_manager.create_session()

    def _handle_local_success(self, session: Session, prompt: str, local_result: LocalResult) -> Dict:
        """Handle successful local result"""

        # Add task to session FIRST (this updates task_count)
        session.add_task(
            prompt=prompt,
            response=local_result.response,
            model=local_result.model,
            cost=0.0,
            quality_score=local_result.quality_score
        )

        # Save to database
        self._save_task_to_db(session, prompt, local_result, None, "local")

        # NOW return the updated session state
        return {
            "status": "local_success",
            "response": local_result.response,
            "model": local_result.model,
            "quality": local_result.quality_score,
            "cost": 0.0,
            "response_time": local_result.response_time,
            "session": {
                "session_id": session.session_id,
                "tier": session.tier,
                "total_cost": session.total_cost,
                "task_count": session.task_count  # This should now be correct
            },
            "message": f"✅ Local model {local_result.model} achieved {local_result.quality_score:.1f}/10 quality"
        }

    def _handle_cloud_upgrade(self, session: Session, prompt: str, local_result: LocalResult, upgrade_option: Dict) -> Dict:
        """Handle automatic cloud upgrade"""

        model = upgrade_option["model"]
        cloud_result = self.cloud_runner.run_prompt(prompt, model)

        if not cloud_result.success:
            # Cloud failed, return local result
            return self._handle_local_success(session, prompt, local_result)

        # Upgrade session
        if session.tier == "local":
            session.upgrade_to_cloud()

        # Add task to session
        session.add_task(
            prompt=prompt,
            response=cloud_result.response,
            model=cloud_result.model,
            cost=cloud_result.cost,
            quality_score=cloud_result.quality_score
        )

        # Save to database
        self._save_task_to_db(session, prompt, local_result, cloud_result, "cloud")

        return {
            "status": "cloud_success",
            "response": cloud_result.response,
            "model": cloud_result.model,
            "quality": cloud_result.quality_score,
            "cost": cloud_result.cost,
            "session": {
                "session_id": session.session_id,
                "tier": session.tier,
                "total_cost": session.total_cost,
                "task_count": session.task_count
            }
        }

    def _format_upgrade_decision(self, session: Session, prompt: str, local_result: LocalResult,
                                 upgrade_options: list, session_analysis: Dict) -> Dict:
        """Format the upgrade decision for user"""

        # Add local result to session even though user hasn't decided yet
        # This tracks the attempt
        session.add_task(
            prompt=prompt,
            response=local_result.response,
            model=local_result.model,
            cost=0.0,
            quality_score=local_result.quality_score
        )

        # Save to database as a local attempt
        self._save_task_to_db(session, prompt, local_result, None, "local")

        return {
            "status": "local_limited",
            "local_result": {
                "model": local_result.model,
                "response": local_result.response,
                "quality": local_result.quality_score,
                "cost": 0.0,
                "response_time": local_result.response_time
            },
            "upgrade_options": upgrade_options,
            "session_analysis": session_analysis,
            "session": {
                "session_id": session.session_id,
                "tier": session.tier,
                "total_cost": session.total_cost,
                "task_count": session.task_count  # Now updated
            },
            "message": f"🏠 Local best: {local_result.quality_score:.1f}/10. Upgrade options available."
        }

    def _save_task_to_db(self, session: Session, prompt: str, local_result: LocalResult,
                        cloud_result: Optional[CloudResult], decision: str):
        """Save task to database"""

        task_data = {
            "session_id": session.session_id,
            "prompt": prompt,
            "response": cloud_result.response if cloud_result else local_result.response,
            "local_model_used": local_result.model,
            "local_quality_score": local_result.quality_score,
            "cloud_model_used": cloud_result.model if cloud_result else None,
            "cloud_quality_score": cloud_result.quality_score if cloud_result else None,
            "final_model": cloud_result.model if cloud_result else local_result.model,
            "upgrade_decision": decision,
            "actual_cost": cloud_result.cost if cloud_result else 0.0,
            "predicted_cost": None,  # Can add later
            "input_tokens": cloud_result.input_tokens if cloud_result else None,
            "output_tokens": cloud_result.output_tokens if cloud_result else None,
            "response_time": cloud_result.response_time if cloud_result else local_result.response_time
        }

        self.database.save_task(task_data)

        # Update session in database
        self.database.save_session(
            session_id=session.session_id,
            tier=session.tier,
            total_cost=session.total_cost,
            task_count=session.task_count,
            started_at=session.started_at,
            ended_at=session.ended_at
        )

    def get_session_status(self, session_id: str) -> Optional[Dict]:
        """Get session status"""

        session = self.session_manager.get_session(session_id)
        if not session:
            return None

        stats = session.get_stats()
        return {
            "session_id": stats.session_id,
            "tier": stats.tier,
            "task_count": stats.task_count,
            "total_cost": stats.total_cost,
            "started_at": stats.started_at.isoformat(),
            "ended_at": stats.ended_at.isoformat() if stats.ended_at else None
        }

    def end_session(self, session_id: str):
        """End a session"""
        self.session_manager.end_session(session_id)
