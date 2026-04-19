"""
Hermes Authentication Manager
Basic authentication management for Hermes AI Assistant
"""

import logging
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
import uuid
from enum import Enum

logger = logging.getLogger(__name__)

class Permission(Enum):
    """User permission levels"""
    READ = "read"
    WRITE = "write"
    ADMIN = "admin"
    SUPERUSER = "superuser"

class User:
    """Basic user class for authentication"""

    def __init__(self, user_id: str, username: str, email: str = None):
        self.user_id = user_id
        self.username = username
        self.email = email
        self.created_at = datetime.now()
        self.last_active = datetime.now()
        self.is_active = True

class AuthManager:
    """Basic authentication manager"""

    def __init__(self):
        self.users: Dict[str, User] = {}
        self.sessions: Dict[str, str] = {}  # session_token -> user_id
        self.logger = logging.getLogger(__name__)

    def create_user(self, username: str, email: str = None) -> User:
        """Create a new user"""
        user_id = str(uuid.uuid4())
        user = User(user_id, username, email)
        self.users[user_id] = user
        self.logger.info(f"Created user {username} with ID {user_id}")
        return user

    def get_user(self, user_id: str) -> Optional[User]:
        """Get user by ID"""
        return self.users.get(user_id)

    def create_session(self, user_id: str) -> str:
        """Create a session for user"""
        session_token = str(uuid.uuid4())
        self.sessions[session_token] = user_id

        # Update last active
        if user := self.get_user(user_id):
            user.last_active = datetime.now()

        self.logger.info(f"Created session for user {user_id}")
        return session_token

    def validate_session(self, session_token: str) -> Optional[User]:
        """Validate session token and return user"""
        user_id = self.sessions.get(session_token)
        if user_id:
            return self.get_user(user_id)
        return None

# Global auth manager instance
auth_manager = AuthManager()

# Create a default test user
default_user = auth_manager.create_user("test_user", "test@example.com")