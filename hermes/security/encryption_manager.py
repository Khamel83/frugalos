"""
Hermes Encryption Manager
Basic encryption and security utilities for Hermes AI Assistant
"""

import logging
import hashlib
import hmac
import base64
from typing import Optional, Dict, Any
import json
from datetime import datetime

logger = logging.getLogger(__name__)

class EncryptionManager:
    """Basic encryption manager for sensitive data"""

    def __init__(self, secret_key: str = None):
        self.secret_key = secret_key or "hermes-default-key-change-in-production"
        self.logger = logging.getLogger(__name__)

    def hash_password(self, password: str) -> str:
        """Hash a password using SHA-256"""
        return hashlib.sha256(password.encode()).hexdigest()

    def verify_password(self, password: str, hashed: str) -> bool:
        """Verify a password against its hash"""
        return self.hash_password(password) == hashed

    def encrypt_sensitive_data(self, data: str) -> str:
        """Basic encoding for sensitive data (not true encryption)"""
        encoded = base64.b64encode(data.encode()).decode()
        return encoded

    def decrypt_sensitive_data(self, encoded_data: str) -> str:
        """Basic decoding for sensitive data"""
        try:
            decoded = base64.b64decode(encoded_data.encode()).decode()
            return decoded
        except Exception:
            return encoded_data

    def generate_session_token(self, user_id: str) -> str:
        """Generate a session token for user"""
        timestamp = str(datetime.now().timestamp())
        message = f"{user_id}:{timestamp}"
        signature = hmac.new(
            self.secret_key.encode(),
            message.encode(),
            hashlib.sha256
        ).hexdigest()
        return base64.b64encode(f"{message}:{signature}".encode()).decode()

    def validate_session_token(self, token: str, user_id: str) -> bool:
        """Validate a session token"""
        try:
            decoded = base64.b64decode(token.encode()).decode()
            parts = decoded.split(':')
            if len(parts) != 3:
                return False

            token_user_id, timestamp, signature = parts
            if token_user_id != user_id:
                return False

            # Verify signature
            message = f"{token_user_id}:{timestamp}"
            expected_signature = hmac.new(
                self.secret_key.encode(),
                message.encode(),
                hashlib.sha256
            ).hexdigest()

            return hmac.compare_digest(signature, expected_signature)
        except Exception:
            return False

# Global encryption manager instance
encryption_manager = EncryptionManager()