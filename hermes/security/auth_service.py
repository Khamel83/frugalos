"""
Advanced Authentication Service for Hermes AI Assistant

This module provides comprehensive authentication and authorization capabilities
including multi-factor authentication, OAuth2, JWT tokens, role-based access control,
and advanced security features.
"""

import asyncio
import base64
import hashlib
import hmac
import json
import secrets
import time
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional, Tuple, Union, Any
import logging
from dataclasses import dataclass, field
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import redis.asyncio as redis
import pyotp
import qrcode
from io import BytesIO
import bcrypt
import jwt

logger = logging.getLogger(__name__)


class AuthMethod(Enum):
    """Authentication methods"""
    PASSWORD = "password"
    API_KEY = "api_key"
    JWT = "jwt"
    OAUTH2 = "oauth2"
    MFA = "mfa"
    SAML = "saml"
    LDAP = "ldap"


class UserRole(Enum):
    """User roles"""
    ADMIN = "admin"
    ENTERPRISE_ADMIN = "enterprise_admin"
    PREMIUM_USER = "premium_user"
    BASIC_USER = "basic_user"
    ANONYMOUS = "anonymous"
    SERVICE_ACCOUNT = "service_account"


class Permission(Enum):
    """Permissions"""
    READ = "read"
    WRITE = "write"
    DELETE = "delete"
    ADMIN = "admin"
    MANAGE_USERS = "manage_users"
    MANAGE_QUOTAS = "manage_quotas"
    VIEW_ANALYTICS = "view_analytics"
    MANAGE_API_KEYS = "manage_api_keys"
    ACCESS_ALL_MODELS = "access_all_models"
    BULK_OPERATIONS = "bulk_operations"


@dataclass
class User:
    """User entity"""
    id: str
    username: str
    email: str
    role: UserRole
    permissions: List[Permission] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    last_login: Optional[datetime] = None
    is_active: bool = True
    mfa_enabled: bool = False
    mfa_secret: Optional[str] = None
    password_hash: Optional[str] = None
    api_keys: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class APICredential:
    """API credential"""
    key_id: str
    key_hash: str
    user_id: str
    permissions: List[Permission]
    created_at: datetime = field(default_factory=datetime.now)
    expires_at: Optional[datetime] = None
    last_used: Optional[datetime] = None
    is_active: bool = True
    rate_limit_tier: str = "basic"
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Session:
    """User session"""
    session_id: str
    user_id: str
    created_at: datetime = field(default_factory=datetime.now)
    expires_at: datetime = field(default_factory=lambda: datetime.now() + timedelta(hours=24))
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    is_active: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AuthResult:
    """Authentication result"""
    success: bool
    user: Optional[User] = None
    session: Optional[Session] = None
    token: Optional[str] = None
    permissions: List[Permission] = field(default_factory=list)
    error_message: Optional[str] = None
    mfa_required: bool = False
    mfa_token: Optional[str] = None


class AuthenticationService:
    """
    Advanced authentication service with multiple auth methods
    """

    def __init__(self, redis_url: Optional[str] = None, jwt_secret: Optional[str] = None):
        self.redis_url = redis_url
        self.jwt_secret = jwt_secret or secrets.token_urlsafe(32)
        self.redis_client: Optional[redis.Redis] = None
        self.encryption_key = Fernet.generate_key()
        self.cipher_suite = Fernet(self.encryption_key)

        # In-memory storage (in production, use database)
        self.users: Dict[str, User] = {}
        self.api_credentials: Dict[str, APICredential] = {}
        self.sessions: Dict[str, Session] = {}

        # Role-based permissions
        self.role_permissions = {
            UserRole.ADMIN: list(Permission),
            UserRole.ENTERPRISE_ADMIN: [
                Permission.READ, Permission.WRITE, Permission.DELETE,
                Permission.MANAGE_USERS, Permission.MANAGE_QUOTAS,
                Permission.VIEW_ANALYTICS, Permission.MANAGE_API_KEYS,
                Permission.ACCESS_ALL_MODELS, Permission.BULK_OPERATIONS
            ],
            UserRole.PREMIUM_USER: [
                Permission.READ, Permission.WRITE,
                Permission.VIEW_ANALYTICS, Permission.ACCESS_ALL_MODELS
            ],
            UserRole.BASIC_USER: [
                Permission.READ, Permission.WRITE
            ],
            UserRole.SERVICE_ACCOUNT: [
                Permission.READ, Permission.WRITE
            ],
            UserRole.ANONYMOUS: [
                Permission.READ
            ]
        }

    async def initialize(self):
        """Initialize the authentication service"""
        if self.redis_url:
            try:
                self.redis_client = redis.from_url(self.redis_url, decode_responses=True)
                await self.redis_client.ping()
                logger.info("Authentication service connected to Redis")
            except Exception as e:
                logger.error(f"Failed to connect to Redis: {e}")
                self.redis_client = None

        # Create default admin user if not exists
        await self._create_default_admin()

    async def _create_default_admin(self):
        """Create default admin user"""
        admin_username = "admin"
        if not any(u.username == admin_username for u in self.users.values()):
            admin_user = User(
                id="admin-001",
                username=admin_username,
                email="admin@hermes-ai.com",
                role=UserRole.ADMIN,
                permissions=self.role_permissions[UserRole.ADMIN]
            )

            # Set default password
            admin_user.password_hash = await self._hash_password("admin123")
            self.users[admin_user.id] = admin_user

            logger.info("Default admin user created (username: admin, password: admin123)")

    async def authenticate(
        self,
        method: AuthMethod,
        credentials: Dict[str, Any],
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> AuthResult:
        """
        Authenticate user using specified method
        """
        try:
            if method == AuthMethod.PASSWORD:
                return await self._authenticate_password(credentials, ip_address, user_agent)
            elif method == AuthMethod.API_KEY:
                return await self._authenticate_api_key(credentials, ip_address, user_agent)
            elif method == AuthMethod.JWT:
                return await self._authenticate_jwt(credentials, ip_address, user_agent)
            elif method == AuthMethod.MFA:
                return await self._authenticate_mfa(credentials, ip_address, user_agent)
            else:
                return AuthResult(
                    success=False,
                    error_message=f"Authentication method {method.value} not supported"
                )
        except Exception as e:
            logger.error(f"Authentication error: {e}")
            return AuthResult(
                success=False,
                error_message="Authentication failed due to internal error"
            )

    async def _authenticate_password(
        self,
        credentials: Dict[str, Any],
        ip_address: Optional[str],
        user_agent: Optional[str]
    ) -> AuthResult:
        """Authenticate with username/password"""
        username = credentials.get("username")
        password = credentials.get("password")

        if not username or not password:
            return AuthResult(
                success=False,
                error_message="Username and password required"
            )

        # Find user
        user = next((u for u in self.users.values() if u.username == username), None)
        if not user:
            return AuthResult(
                success=False,
                error_message="Invalid credentials"
            )

        if not user.is_active:
            return AuthResult(
                success=False,
                error_message="Account is disabled"
            )

        # Verify password
        if not await self._verify_password(password, user.password_hash or ""):
            return AuthResult(
                success=False,
                error_message="Invalid credentials"
            )

        # Check if MFA is required
        if user.mfa_enabled:
            mfa_token = secrets.token_urlsafe(32)
            await self._store_mfa_token(user.id, mfa_token)
            return AuthResult(
                success=False,
                mfa_required=True,
                mfa_token=mfa_token,
                user=user,
                error_message="MFA verification required"
            )

        # Create session and token
        session = await self._create_session(user.id, ip_address, user_agent)
        token = await self._create_jwt_token(user)

        # Update last login
        user.last_login = datetime.now()
        await self._store_user(user)

        return AuthResult(
            success=True,
            user=user,
            session=session,
            token=token,
            permissions=user.permissions
        )

    async def _authenticate_api_key(
        self,
        credentials: Dict[str, Any],
        ip_address: Optional[str],
        user_agent: Optional[str]
    ) -> AuthResult:
        """Authenticate with API key"""
        api_key = credentials.get("api_key")

        if not api_key:
            return AuthResult(
                success=False,
                error_message="API key required"
            )

        # Find API credential
        api_credential = None
        for cred in self.api_credentials.values():
            if hmac.compare_digest(cred.key_hash, self._hash_api_key(api_key)):
                api_credential = cred
                break

        if not api_credential:
            return AuthResult(
                success=False,
                error_message="Invalid API key"
            )

        if not api_credential.is_active:
            return AuthResult(
                success=False,
                error_message="API key is disabled"
            )

        # Check expiration
        if api_credential.expires_at and datetime.now() > api_credential.expires_at:
            return AuthResult(
                success=False,
                error_message="API key has expired"
            )

        # Get user
        user = self.users.get(api_credential.user_id)
        if not user or not user.is_active:
            return AuthResult(
                success=False,
                error_message="User account is disabled"
            )

        # Update last used
        api_credential.last_used = datetime.now()
        await self._store_api_credential(api_credential)

        # Create temporary session for API key
        session = Session(
            session_id=secrets.token_urlsafe(32),
            user_id=user.id,
            expires_at=datetime.now() + timedelta(hours=1),
            ip_address=ip_address,
            user_agent=user_agent,
            metadata={"auth_method": "api_key", "key_id": api_credential.key_id}
        )

        return AuthResult(
            success=True,
            user=user,
            session=session,
            permissions=api_credential.permissions
        )

    async def _authenticate_jwt(
        self,
        credentials: Dict[str, Any],
        ip_address: Optional[str],
        user_agent: Optional[str]
    ) -> AuthResult:
        """Authenticate with JWT token"""
        token = credentials.get("token")

        if not token:
            return AuthResult(
                success=False,
                error_message="JWT token required"
            )

        try:
            # Decode and verify token
            payload = jwt.decode(
                token,
                self.jwt_secret,
                algorithms=["HS256"],
                options={"verify_exp": True}
            )

            user_id = payload.get("sub")
            if not user_id:
                return AuthResult(
                    success=False,
                    error_message="Invalid token format"
                )

            # Get user
            user = self.users.get(user_id)
            if not user or not user.is_active:
                return AuthResult(
                    success=False,
                    error_message="User not found or disabled"
                )

            # Check if session is still valid
            session_id = payload.get("session_id")
            if session_id:
                session = await self._get_session(session_id)
                if not session or not session.is_active or datetime.now() > session.expires_at:
                    return AuthResult(
                        success=False,
                        error_message="Session has expired"
                    )

            return AuthResult(
                success=True,
                user=user,
                permissions=user.permissions
            )

        except jwt.ExpiredSignatureError:
            return AuthResult(
                success=False,
                error_message="Token has expired"
            )
        except jwt.InvalidTokenError as e:
            return AuthResult(
                success=False,
                error_message=f"Invalid token: {str(e)}"
            )

    async def _authenticate_mfa(
        self,
        credentials: Dict[str, Any],
        ip_address: Optional[str],
        user_agent: Optional[str]
    ) -> AuthResult:
        """Authenticate with MFA code"""
        mfa_token = credentials.get("mfa_token")
        mfa_code = credentials.get("mfa_code")

        if not mfa_token or not mfa_code:
            return AuthResult(
                success=False,
                error_message="MFA token and code required"
            )

        # Verify MFA token
        user_id = await self._verify_mfa_token(mfa_token)
        if not user_id:
            return AuthResult(
                success=False,
                error_message="Invalid or expired MFA token"
            )

        # Get user
        user = self.users.get(user_id)
        if not user or not user.mfa_enabled:
            return AuthResult(
                success=False,
                error_message="MFA not enabled for user"
            )

        # Verify TOTP code
        if not self._verify_totp_code(mfa_code, user.mfa_secret):
            return AuthResult(
                success=False,
                error_message="Invalid MFA code"
            )

        # Consume MFA token
        await self._consume_mfa_token(mfa_token)

        # Create session and token
        session = await self._create_session(user.id, ip_address, user_agent)
        token = await self._create_jwt_token(user)

        return AuthResult(
            success=True,
            user=user,
            session=session,
            token=token,
            permissions=user.permissions
        )

    async def create_user(
        self,
        username: str,
        email: str,
        password: str,
        role: UserRole = UserRole.BASIC_USER,
        permissions: Optional[List[Permission]] = None
    ) -> User:
        """Create a new user"""
        if any(u.username == username for u in self.users.values()):
            raise ValueError(f"Username {username} already exists")

        if any(u.email == email for u in self.users.values()):
            raise ValueError(f"Email {email} already exists")

        user_id = secrets.token_urlsafe(16)
        user_permissions = permissions or self.role_permissions.get(role, [])

        user = User(
            id=user_id,
            username=username,
            email=email,
            role=role,
            permissions=user_permissions,
            password_hash=await self._hash_password(password)
        )

        self.users[user_id] = user
        await self._store_user(user)

        logger.info(f"Created user {username} with role {role.value}")
        return user

    async def create_api_key(
        self,
        user_id: str,
        name: str,
        permissions: List[Permission],
        expires_in_days: Optional[int] = None,
        rate_limit_tier: str = "basic"
    ) -> Tuple[str, str]:
        """Create API key for user"""
        user = self.users.get(user_id)
        if not user:
            raise ValueError("User not found")

        key_id = secrets.token_urlsafe(16)
        api_key = f"hk_{secrets.token_urlsafe(32)}"

        expires_at = None
        if expires_in_days:
            expires_at = datetime.now() + timedelta(days=expires_in_days)

        api_credential = APICredential(
            key_id=key_id,
            key_hash=self._hash_api_key(api_key),
            user_id=user_id,
            permissions=permissions,
            expires_at=expires_at,
            rate_limit_tier=rate_limit_tier,
            metadata={"name": name}
        )

        self.api_credentials[key_id] = api_credential
        user.api_keys.append(key_id)

        await self._store_api_credential(api_credential)
        await self._store_user(user)

        logger.info(f"Created API key {key_id} for user {user.username}")
        return key_id, api_key

    async def enable_mfa(self, user_id: str) -> Tuple[str, str]:
        """Enable MFA for user and return secret and QR code"""
        user = self.users.get(user_id)
        if not user:
            raise ValueError("User not found")

        # Generate TOTP secret
        secret = pyotp.random_base32()
        user.mfa_secret = secret
        user.mfa_enabled = True

        await self._store_user(user)

        # Generate QR code
        totp_uri = pyotp.totp.TOTP(secret).provisioning_uri(
            name=user.email,
            issuer_name="Hermes AI Assistant"
        )

        qr = qrcode.QRCode(version=1, box_size=10, border=5)
        qr.add_data(totp_uri)
        qr.make(fit=True)

        img = qr.make_image(fill_color="black", back_color="white")
        buffer = BytesIO()
        img.save(buffer, format='PNG')
        qr_code_data = base64.b64encode(buffer.getvalue()).decode()

        logger.info(f"Enabled MFA for user {user.username}")
        return secret, qr_code_data

    async def disable_mfa(self, user_id: str, verification_code: str) -> bool:
        """Disable MFA for user"""
        user = self.users.get(user_id)
        if not user or not user.mfa_enabled:
            return False

        # Verify current TOTP code
        if not self._verify_totp_code(verification_code, user.mfa_secret):
            return False

        user.mfa_enabled = False
        user.mfa_secret = None

        await self._store_user(user)
        logger.info(f"Disabled MFA for user {user.username}")
        return True

    async def revoke_api_key(self, key_id: str, user_id: str) -> bool:
        """Revoke API key"""
        api_credential = self.api_credentials.get(key_id)
        if not api_credential or api_credential.user_id != user_id:
            return False

        api_credential.is_active = False
        await self._store_api_credential(api_credential)

        user = self.users.get(user_id)
        if user and key_id in user.api_keys:
            user.api_keys.remove(key_id)
            await self._store_user(user)

        logger.info(f"Revoked API key {key_id}")
        return True

    async def logout(self, session_id: str) -> bool:
        """Logout user session"""
        session = await self._get_session(session_id)
        if not session:
            return False

        session.is_active = False
        await self._store_session(session)

        logger.info(f"Logged out session {session_id}")
        return True

    async def logout_all_sessions(self, user_id: str) -> int:
        """Logout all sessions for user"""
        count = 0
        for session in self.sessions.values():
            if session.user_id == user_id and session.is_active:
                session.is_active = False
                await self._store_session(session)
                count += 1

        logger.info(f"Logged out {count} sessions for user {user_id}")
        return count

    async def refresh_token(self, token: str) -> Optional[str]:
        """Refresh JWT token"""
        try:
            payload = jwt.decode(
                token,
                self.jwt_secret,
                algorithms=["HS256"],
                options={"verify_exp": False}
            )

            user_id = payload.get("sub")
            if not user_id:
                return None

            user = self.users.get(user_id)
            if not user or not user.is_active:
                return None

            # Create new token
            return await self._create_jwt_token(user)

        except jwt.InvalidTokenError:
            return None

    async def get_user_permissions(self, user_id: str) -> List[Permission]:
        """Get user permissions"""
        user = self.users.get(user_id)
        return user.permissions if user else []

    async def check_permission(
        self,
        user_id: str,
        permission: Permission,
        resource_id: Optional[str] = None
    ) -> bool:
        """Check if user has permission"""
        user = self.users.get(user_id)
        if not user or not user.is_active:
            return False

        # Admin has all permissions
        if user.role == UserRole.ADMIN:
            return True

        # Check direct permissions
        if permission in user.permissions:
            return True

        # Check role-based permissions
        role_perms = self.role_permissions.get(user.role, [])
        if permission in role_perms:
            return True

        return False

    # Helper methods
    async def _hash_password(self, password: str) -> str:
        """Hash password using bcrypt"""
        return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

    async def _verify_password(self, password: str, password_hash: str) -> bool:
        """Verify password against hash"""
        return bcrypt.checkpw(password.encode('utf-8'), password_hash.encode('utf-8'))

    def _hash_api_key(self, api_key: str) -> str:
        """Hash API key"""
        return hashlib.sha256(api_key.encode('utf-8')).hexdigest()

    def _verify_totp_code(self, code: str, secret: str) -> bool:
        """Verify TOTP code"""
        try:
            totp = pyotp.TOTP(secret)
            return totp.verify(code, valid_window=1)  # Allow 1 step tolerance
        except Exception:
            return False

    async def _create_session(
        self,
        user_id: str,
        ip_address: Optional[str],
        user_agent: Optional[str]
    ) -> Session:
        """Create new session"""
        session = Session(
            session_id=secrets.token_urlsafe(32),
            user_id=user_id,
            ip_address=ip_address,
            user_agent=user_agent
        )

        self.sessions[session.session_id] = session
        await self._store_session(session)
        return session

    async def _create_jwt_token(self, user: User) -> str:
        """Create JWT token for user"""
        payload = {
            "sub": user.id,
            "username": user.username,
            "role": user.role.value,
            "permissions": [p.value for p in user.permissions],
            "iat": datetime.now(),
            "exp": datetime.now() + timedelta(hours=24)
        }

        return jwt.encode(payload, self.jwt_secret, algorithm="HS256")

    async def _store_mfa_token(self, user_id: str, mfa_token: str):
        """Store MFA token"""
        if self.redis_client:
            await self.redis_client.setex(
                f"mfa_token:{mfa_token}",
                300,  # 5 minutes
                user_id
            )

    async def _verify_mfa_token(self, mfa_token: str) -> Optional[str]:
        """Verify MFA token"""
        if self.redis_client:
            return await self.redis_client.get(f"mfa_token:{mfa_token}")
        return None

    async def _consume_mfa_token(self, mfa_token: str):
        """Consume MFA token"""
        if self.redis_client:
            await self.redis_client.delete(f"mfa_token:{mfa_token}")

    async def _store_user(self, user: User):
        """Store user in Redis"""
        if self.redis_client:
            user_data = {
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "role": user.role.value,
                "permissions": [p.value for p in user.permissions],
                "created_at": user.created_at.isoformat(),
                "last_login": user.last_login.isoformat() if user.last_login else None,
                "is_active": user.is_active,
                "mfa_enabled": user.mfa_enabled,
                "password_hash": user.password_hash,
                "api_keys": json.dumps(user.api_keys),
                "metadata": json.dumps(user.metadata)
            }
            await self.redis_client.hset(f"user:{user.id}", mapping=user_data)

    async def _store_api_credential(self, credential: APICredential):
        """Store API credential in Redis"""
        if self.redis_client:
            cred_data = {
                "key_id": credential.key_id,
                "key_hash": credential.key_hash,
                "user_id": credential.user_id,
                "permissions": [p.value for p in credential.permissions],
                "created_at": credential.created_at.isoformat(),
                "expires_at": credential.expires_at.isoformat() if credential.expires_at else None,
                "last_used": credential.last_used.isoformat() if credential.last_used else None,
                "is_active": credential.is_active,
                "rate_limit_tier": credential.rate_limit_tier,
                "metadata": json.dumps(credential.metadata)
            }
            await self.redis_client.hset(f"api_key:{credential.key_id}", mapping=cred_data)

    async def _store_session(self, session: Session):
        """Store session in Redis"""
        if self.redis_client:
            session_data = {
                "session_id": session.session_id,
                "user_id": session.user_id,
                "created_at": session.created_at.isoformat(),
                "expires_at": session.expires_at.isoformat(),
                "ip_address": session.ip_address,
                "user_agent": session.user_agent,
                "is_active": session.is_active,
                "metadata": json.dumps(session.metadata)
            }
            await self.redis_client.hset(f"session:{session.session_id}", mapping=session_data)
            await self.redis_client.expireat(
                f"session:{session.session_id}",
                int(session.expires_at.timestamp())
            )

    async def _get_session(self, session_id: str) -> Optional[Session]:
        """Get session from Redis"""
        if self.redis_client:
            data = await self.redis_client.hgetall(f"session:{session_id}")
            if data:
                return Session(
                    session_id=data["session_id"],
                    user_id=data["user_id"],
                    created_at=datetime.fromisoformat(data["created_at"]),
                    expires_at=datetime.fromisoformat(data["expires_at"]),
                    ip_address=data.get("ip_address"),
                    user_agent=data.get("user_agent"),
                    is_active=data["is_active"] == "True",
                    metadata=json.loads(data.get("metadata", "{}"))
                )
        return self.sessions.get(session_id)

    async def get_user(self, user_id: str) -> Optional[User]:
        """Get user by ID"""
        if self.redis_client:
            data = await self.redis_client.hgetall(f"user:{user_id}")
            if data:
                return User(
                    id=data["id"],
                    username=data["username"],
                    email=data["email"],
                    role=UserRole(data["role"]),
                    permissions=[Permission(p) for p in json.loads(data["permissions"])],
                    created_at=datetime.fromisoformat(data["created_at"]),
                    last_login=datetime.fromisoformat(data["last_login"]) if data.get("last_login") else None,
                    is_active=data["is_active"] == "True",
                    mfa_enabled=data["mfa_enabled"] == "True",
                    password_hash=data.get("password_hash"),
                    api_keys=json.loads(data.get("api_keys", "[]")),
                    metadata=json.loads(data.get("metadata", "{}"))
                )
        return self.users.get(user_id)


# Global authentication service instance
auth_service = AuthenticationService()


async def initialize_auth_service(redis_url: Optional[str] = None, jwt_secret: Optional[str] = None):
    """Initialize the global authentication service"""
    global auth_service
    auth_service = AuthenticationService(redis_url, jwt_secret)
    await auth_service.initialize()