"""
Session Manager - Track conversation sessions and costs
Handles session state and context transfer costs
"""
import uuid
from datetime import datetime
from typing import Dict, List, Optional
from dataclasses import dataclass, field

from .config import SESSION_CONFIG


@dataclass
class Message:
    prompt: str
    response: str
    model: str
    cost: float
    quality_score: float
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class SessionStats:
    session_id: str
    tier: str  # 'local' or 'cloud'
    task_count: int
    total_cost: float
    started_at: datetime
    ended_at: Optional[datetime]
    messages: List[Message]


class Session:
    """Manages a single conversation session"""

    def __init__(self, session_id: Optional[str] = None):
        self.session_id = session_id or str(uuid.uuid4())
        self.tier = "local"  # Always start local
        self.messages: List[Message] = []
        self.total_cost = 0.0
        self.task_count = 0
        self.started_at = datetime.now()
        self.ended_at = None
        self.context_transferred = False

    def add_task(self, prompt: str, response: str, model: str, cost: float, quality_score: float):
        """Add a task to the session"""

        message = Message(
            prompt=prompt,
            response=response,
            model=model,
            cost=cost,
            quality_score=quality_score
        )

        self.messages.append(message)
        self.total_cost += cost
        self.task_count += 1

    def upgrade_to_cloud(self):
        """Switch session to cloud tier"""

        if self.tier == "cloud":
            return  # Already in cloud

        self.tier = "cloud"
        self.context_transferred = True

        # Add context transfer cost
        context_cost = SESSION_CONFIG["context_transfer_cost"]
        self.total_cost += context_cost

    def should_warn_about_session(self) -> bool:
        """Check if we should warn user about session costs"""
        return self.tier == "local" and not self.context_transferred

    def get_session_analysis(self, upgrade_cost: float) -> Dict:
        """
        Analyze the real cost impact of upgrading to cloud
        This is THE KEY FEATURE - showing session continuation costs
        """

        if self.tier == "cloud":
            # Already in cloud - show current session costs
            return {
                "status": "in_cloud_session",
                "current_task_cost": upgrade_cost,
                "session_cost_so_far": self.total_cost,
                "task_number": self.task_count + 1,
                "projected_total": self.total_cost + (upgrade_cost * (SESSION_CONFIG["average_session_tasks"] - self.task_count))
            }

        # Calculate what upgrading would cost for full session
        single_task_cost = upgrade_cost
        context_transfer_cost = SESSION_CONFIG["context_transfer_cost"]
        average_tasks = SESSION_CONFIG["average_session_tasks"]
        session_continuation_cost = SESSION_CONFIG["session_continuation_cost"]

        # Cost per task in session (includes continuation overhead)
        cost_per_task = single_task_cost + (session_continuation_cost / average_tasks)

        # Total projected session cost
        total_session_cost = context_transfer_cost + (average_tasks * cost_per_task)

        # Session premium (how much more expensive than single task)
        session_premium = total_session_cost / single_task_cost if single_task_cost > 0 else 0

        return {
            "status": "considering_upgrade",
            "single_task_cost": single_task_cost,
            "context_transfer_cost": context_transfer_cost,
            "projected_session_tasks": average_tasks,
            "cost_per_task_in_session": cost_per_task,
            "total_session_cost": total_session_cost,
            "session_premium": session_premium,
            "context_loss_risk": SESSION_CONFIG["context_loss_risk"]
        }

    def end_session(self):
        """Mark session as ended"""
        self.ended_at = datetime.now()

    def get_stats(self) -> SessionStats:
        """Get session statistics"""
        return SessionStats(
            session_id=self.session_id,
            tier=self.tier,
            task_count=self.task_count,
            total_cost=self.total_cost,
            started_at=self.started_at,
            ended_at=self.ended_at,
            messages=self.messages
        )

    def get_context(self, max_messages: int = 10) -> List[Dict]:
        """Get recent conversation context"""

        recent_messages = self.messages[-max_messages:]

        context = []
        for msg in recent_messages:
            context.append({"role": "user", "content": msg.prompt})
            context.append({"role": "assistant", "content": msg.response})

        return context


class SessionManager:
    """Manages multiple sessions"""

    def __init__(self):
        self.active_sessions: Dict[str, Session] = {}

    def create_session(self) -> Session:
        """Create a new session"""
        session = Session()
        self.active_sessions[session.session_id] = session
        return session

    def get_session(self, session_id: str) -> Optional[Session]:
        """Get an existing session"""
        return self.active_sessions.get(session_id)

    def end_session(self, session_id: str):
        """End a session"""
        session = self.active_sessions.get(session_id)
        if session:
            session.end_session()

    def cleanup_old_sessions(self, max_age_hours: int = 24):
        """Remove sessions older than max_age_hours"""

        now = datetime.now()
        sessions_to_remove = []

        for session_id, session in self.active_sessions.items():
            if session.ended_at:
                age = (now - session.ended_at).total_seconds() / 3600
                if age > max_age_hours:
                    sessions_to_remove.append(session_id)

        for session_id in sessions_to_remove:
            del self.active_sessions[session_id]
