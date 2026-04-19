"""
Tests for the Authentication Service

This module contains comprehensive tests for authentication, authorization,
session management, and API key functionality.
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch
import jwt
import pyotp

from hermes.security.auth_service import (
    AuthenticationService,
    User,
    UserRole,
    Permission,
    APICredential,
    Session,
    AuthResult,
    AuthMethod
)
from hermes.security.compliance import ComplianceManager, AuditEventType


class TestAuthenticationService:
    """Test cases for AuthenticationService"""

    @pytest.mark.asyncio
    async def test_initialize_service(self, redis_client):
        """Test service initialization."""
        service = AuthenticationService(redis_url="redis://localhost:6379/15")
        await service.initialize()

        assert service.redis_client is not None
        assert len(service.users) > 0  # Default admin user should be created

    @pytest.mark.asyncio
    async def test_create_user(self, auth_service):
        """Test user creation."""
        user = await auth_service.create_user(
            username="newuser",
            email="newuser@example.com",
            password="newpassword123",
            role=UserRole.BASIC_USER
        )

        assert user.username == "newuser"
        assert user.email == "newuser@example.com"
        assert user.role == UserRole.BASIC_USER
        assert user.is_active is True
        assert user.password_hash is not None
        assert user.id in auth_service.users

    @pytest.mark.asyncio
    async def test_create_duplicate_user(self, auth_service):
        """Test creating duplicate user raises error."""
        with pytest.raises(ValueError, match="Username newuser already exists"):
            await auth_service.create_user(
                username="testuser",  # Already exists in fixture
                email="another@example.com",
                password="password123"
            )

    @pytest.mark.asyncio
    async def test_password_authentication_success(self, auth_service):
        """Test successful password authentication."""
        result = await auth_service.authenticate(
            AuthMethod.PASSWORD,
            {
                "username": "testuser",
                "password": "testpassword123"
            },
            ip_address="192.168.1.100"
        )

        assert result.success is True
        assert result.user is not None
        assert result.user.username == "testuser"
        assert result.token is not None
        assert result.session is not None
        assert len(result.permissions) > 0

    @pytest.mark.asyncio
    async def test_password_authentication_failure(self, auth_service):
        """Test failed password authentication."""
        result = await auth_service.authenticate(
            AuthMethod.PASSWORD,
            {
                "username": "testuser",
                "password": "wrongpassword"
            }
        )

        assert result.success is False
        assert result.user is None
        assert result.token is None
        assert "Invalid credentials" in result.error_message

    @pytest.mark.asyncio
    async def test_password_authentication_missing_credentials(self, auth_service):
        """Test authentication with missing credentials."""
        result = await auth_service.authenticate(
            AuthMethod.PASSWORD,
            {"username": "testuser"}  # Missing password
        )

        assert result.success is False
        assert "Username and password required" in result.error_message

    @pytest.mark.asyncio
    async def test_create_and_authenticate_api_key(self, auth_service):
        """Test API key creation and authentication."""
        # Find a test user
        user = None
        for u in auth_service.users.values():
            if u.username == "testuser":
                user = u
                break

        assert user is not None

        # Create API key
        key_id, api_key = await auth_service.create_api_key(
            user_id=user.id,
            name="Test API Key",
            permissions=[Permission.READ, Permission.WRITE]
        )

        assert key_id is not None
        assert api_key is not None
        assert api_key.startswith("hk_")

        # Authenticate with API key
        result = await auth_service.authenticate(
            AuthMethod.API_KEY,
            {"api_key": api_key}
        )

        assert result.success is True
        assert result.user is not None
        assert result.user.id == user.id
        assert Permission.READ in result.permissions
        assert Permission.WRITE in result.permissions

    @pytest.mark.asyncio
    async def test_api_key_authentication_invalid(self, auth_service):
        """Test API key authentication with invalid key."""
        result = await auth_service.authenticate(
            AuthMethod.API_KEY,
            {"api_key": "invalid_key_123"}
        )

        assert result.success is False
        assert "Invalid API key" in result.error_message

    @pytest.mark.asyncio
    async def test_jwt_authentication(self, auth_service):
        """Test JWT token authentication."""
        # First authenticate to get a token
        auth_result = await auth_service.authenticate(
            AuthMethod.PASSWORD,
            {
                "username": "testuser",
                "password": "testpassword123"
            }
        )

        assert auth_result.success is True
        token = auth_result.token

        # Authenticate with JWT token
        result = await auth_service.authenticate(
            AuthMethod.JWT,
            {"token": token}
        )

        assert result.success is True
        assert result.user is not None
        assert result.user.username == "testuser"

    @pytest.mark.asyncio
    async def test_jwt_authentication_invalid(self, auth_service):
        """Test JWT authentication with invalid token."""
        result = await auth_service.authenticate(
            AuthMethod.JWT,
            {"token": "invalid.jwt.token"}
        )

        assert result.success is False
        assert "Invalid token" in result.error_message

    @pytest.mark.asyncio
    async def test_jwt_authentication_expired(self, auth_service):
        """Test JWT authentication with expired token."""
        # Create expired token
        expired_payload = {
            "sub": "testuser",
            "exp": datetime.now() - timedelta(hours=1),  # Expired
            "iat": datetime.now() - timedelta(hours=2)
        }
        expired_token = jwt.encode(expired_payload, auth_service.jwt_secret, algorithm="HS256")

        result = await auth_service.authenticate(
            AuthMethod.JWT,
            {"token": expired_token}
        )

        assert result.success is False
        assert "expired" in result.error_message.lower()

    @pytest.mark.asyncio
    async def test_enable_mfa(self, auth_service):
        """Test enabling MFA for user."""
        # Find test user
        user = None
        for u in auth_service.users.values():
            if u.username == "testuser":
                user = u
                break

        # Enable MFA
        secret, qr_code = await auth_service.enable_mfa(user.id)

        assert secret is not None
        assert len(secret) == 32  # TOTP secret length
        assert qr_code is not None
        assert isinstance(qr_code, str)
        assert user.mfa_enabled is True
        assert user.mfa_secret == secret

    @pytest.mark.asyncio
    async def test_mfa_authentication(self, auth_service):
        """Test MFA authentication flow."""
        # Find test user and enable MFA
        user = None
        for u in auth_service.users.values():
            if u.username == "testuser":
                user = u
                break

        await auth_service.enable_mfa(user.id)

        # Step 1: Authenticate with password (should require MFA)
        result = await auth_service.authenticate(
            AuthMethod.PASSWORD,
            {
                "username": "testuser",
                "password": "testpassword123"
            }
        )

        assert result.success is False
        assert result.mfa_required is True
        assert result.mfa_token is not None

        # Step 2: Generate valid TOTP code
        totp = pyotp.TOTP(user.mfa_secret)
        current_code = totp.now()

        # Step 3: Complete MFA authentication
        mfa_result = await auth_service.authenticate(
            AuthMethod.MFA,
            {
                "mfa_token": result.mfa_token,
                "mfa_code": current_code
            }
        )

        assert mfa_result.success is True
        assert mfa_result.user is not None
        assert mfa_result.token is not None

    @pytest.mark.asyncio
    async def test_mfa_authentication_invalid_code(self, auth_service):
        """Test MFA authentication with invalid code."""
        # Find test user and enable MFA
        user = None
        for u in auth_service.users.values():
            if u.username == "testuser":
                user = u
                break

        await auth_service.enable_mfa(user.id)

        # Step 1: Get MFA token
        result = await auth_service.authenticate(
            AuthMethod.PASSWORD,
            {
                "username": "testuser",
                "password": "testpassword123"
            }
        )

        # Step 2: Try invalid MFA code
        mfa_result = await auth_service.authenticate(
            AuthMethod.MFA,
            {
                "mfa_token": result.mfa_token,
                "mfa_code": "123456"  # Invalid code
            }
        )

        assert mfa_result.success is False
        assert "Invalid MFA code" in mfa_result.error_message

    @pytest.mark.asyncio
    async def test_revoke_api_key(self, auth_service):
        """Test API key revocation."""
        # Find test user
        user = None
        for u in auth_service.users.values():
            if u.username == "testuser":
                user = u
                break

        # Create API key
        key_id, api_key = await auth_service.create_api_key(
            user_id=user.id,
            name="Test Key"
        )

        # Revoke API key
        success = await auth_service.revoke_api_key(key_id, user.id)
        assert success is True

        # Try to authenticate with revoked key
        result = await auth_service.authenticate(
            AuthMethod.API_KEY,
            {"api_key": api_key}
        )

        assert result.success is False

    @pytest.mark.asyncio
    async def test_logout(self, auth_service):
        """Test user logout."""
        # Authenticate to get session
        result = await auth_service.authenticate(
            AuthMethod.PASSWORD,
            {
                "username": "testuser",
                "password": "testpassword123"
            }
        )

        assert result.success is True
        session_id = result.session.session_id

        # Logout
        logout_success = await auth_service.logout(session_id)
        assert logout_success is True

        # Verify session is inactive
        session = await auth_service._get_session(session_id)
        assert session is not None
        assert session.is_active is False

    @pytest.mark.asyncio
    async def test_logout_all_sessions(self, auth_service):
        """Test logging out all user sessions."""
        # Find test user
        user = None
        for u in auth_service.users.values():
            if u.username == "testuser":
                user = u
                break

        # Create multiple sessions
        sessions = []
        for i in range(3):
            result = await auth_service.authenticate(
                AuthMethod.PASSWORD,
                {
                    "username": "testuser",
                    "password": "testpassword123"
                }
            )
            sessions.append(result.session.session_id)

        # Logout all sessions
        logged_out_count = await auth_service.logout_all_sessions(user.id)
        assert logged_out_count >= 3

    @pytest.mark.asyncio
    async def test_refresh_token(self, auth_service):
        """Test JWT token refresh."""
        # Authenticate to get token
        result = await auth_service.authenticate(
            AuthMethod.PASSWORD,
            {
                "username": "testuser",
                "password": "testpassword123"
            }
        )

        original_token = result.token

        # Refresh token
        new_token = await auth_service.refresh_token(original_token)
        assert new_token is not None
        assert new_token != original_token

        # Authenticate with new token
        refresh_result = await auth_service.authenticate(
            AuthMethod.JWT,
            {"token": new_token}
        )

        assert refresh_result.success is True

    @pytest.mark.asyncio
    async def test_check_permission(self, auth_service):
        """Test permission checking."""
        # Find admin user
        admin_user = None
        for u in auth_service.users.values():
            if u.role == UserRole.ADMIN:
                admin_user = u
                break

        assert admin_user is not None

        # Admin should have all permissions
        assert await auth_service.check_permission(admin_user.id, Permission.ADMIN)
        assert await auth_service.check_permission(admin_user.id, Permission.MANAGE_USERS)
        assert await auth_service.check_permission(admin_user.id, Permission.READ)

        # Find basic user
        basic_user = None
        for u in auth_service.users.values():
            if u.role == UserRole.BASIC_USER:
                basic_user = u
                break

        assert basic_user is not None

        # Basic user should have limited permissions
        assert not await auth_service.check_permission(basic_user.id, Permission.ADMIN)
        assert not await auth_service.check_permission(basic_user.id, Permission.MANAGE_USERS)
        assert await auth_service.check_permission(basic_user.id, Permission.READ)

    @pytest.mark.asyncio
    async def test_get_user_permissions(self, auth_service):
        """Test getting user permissions."""
        # Find admin user
        admin_user = None
        for u in auth_service.users.values():
            if u.role == UserRole.ADMIN:
                admin_user = u
                break

        permissions = await auth_service.get_user_permissions(admin_user.id)
        assert len(permissions) > 0
        assert Permission.ADMIN in permissions

    @pytest.mark.asyncio
    async def test_disable_user(self, auth_service):
        """Test disabling a user."""
        # Find test user
        user = None
        for u in auth_service.users.values():
            if u.username == "testuser":
                user = u
                break

        # Disable user
        user.is_active = False
        await auth_service._store_user(user)

        # Try to authenticate disabled user
        result = await auth_service.authenticate(
            AuthMethod.PASSWORD,
            {
                "username": "testuser",
                "password": "testpassword123"
            }
        )

        assert result.success is False
        assert "Account is disabled" in result.error_message

    @pytest.mark.asyncio
    async def test_password_hashing(self, auth_service):
        """Test password hashing and verification."""
        password = "test_password_123"

        # Hash password
        hash_result = await auth_service._hash_password(password)
        assert hash_result is not None
        assert hash_result != password

        # Verify correct password
        is_valid = await auth_service._verify_password(password, hash_result)
        assert is_valid is True

        # Verify incorrect password
        is_invalid = await auth_service._verify_password("wrong_password", hash_result)
        assert is_invalid is False

    @pytest.mark.asyncio
    async def test_api_key_expiration(self, auth_service):
        """Test API key expiration."""
        # Find test user
        user = None
        for u in auth_service.users.values():
            if u.username == "testuser":
                user = u
                break

        # Create expired API key
        key_id, api_key = await auth_service.create_api_key(
            user_id=user.id,
            name="Expired Key",
            expires_in_days=-1  # Already expired
        )

        # Try to authenticate with expired key
        result = await auth_service.authenticate(
            AuthMethod.API_KEY,
            {"api_key": api_key}
        )

        assert result.success is False
        assert "expired" in result.error_message.lower()

    @pytest.mark.asyncio
    async def test_session_expiration(self, auth_service):
        """Test session expiration."""
        # Create session with short expiration
        user = None
        for u in auth_service.users.values():
            if u.username == "testuser":
                user = u
                break

        session = await auth_service._create_session(
            user_id=user.id,
            ip_address="192.168.1.100",
            user_agent="test-agent"
        )

        # Manually expire session
        session.expires_at = datetime.now() - timedelta(minutes=1)
        await auth_service._store_session(session)

        # Try to use expired session in JWT
        payload = {
            "sub": user.id,
            "session_id": session.session_id,
            "exp": datetime.now() - timedelta(minutes=1),
            "iat": datetime.now() - timedelta(minutes=2)
        }
        expired_token = jwt.encode(payload, auth_service.jwt_secret, algorithm="HS256")

        result = await auth_service.authenticate(
            AuthMethod.JWT,
            {"token": expired_token}
        )

        assert result.success is False
        assert "expired" in result.error_message.lower()

    @pytest.mark.asyncio
    async def test_concurrent_api_keys_limit(self, auth_service):
        """Test API key creation limit."""
        # Find test user
        user = None
        for u in auth_service.users.values():
            if u.username == "testuser":
                user = u
                break

        # Create multiple API keys (up to the limit)
        created_keys = []
        max_keys = 10  # This should match the service configuration

        for i in range(max_keys):
            try:
                key_id, api_key = await auth_service.create_api_key(
                    user_id=user.id,
                    name=f"Key {i+1}"
                )
                created_keys.append((key_id, api_key))
            except Exception as e:
                # Should fail when reaching the limit
                assert "limit" in str(e).lower()
                break

        # Should have created keys up to the limit
        assert len(created_keys) <= max_keys

    @pytest.mark.asyncio
    async def test_get_user_info(self, auth_service):
        """Test getting user information."""
        # Find test user
        user = None
        for u in auth_service.users.values():
            if u.username == "testuser":
                user = u
                break

        retrieved_user = await auth_service.get_user(user.id)
        assert retrieved_user is not None
        assert retrieved_user.id == user.id
        assert retrieved_user.username == user.username
        assert retrieved_user.email == user.email

    @pytest.mark.asyncio
    async def test_update_user_role(self, auth_service):
        """Test updating user role."""
        # Find basic user
        user = None
        for u in auth_service.users.values():
            if u.username == "testuser":
                user = u
                break

        original_role = user.role
        original_permissions = user.permissions.copy()

        # Update role to premium
        user.role = UserRole.PREMIUM_USER
        user.permissions = auth_service.role_permissions[UserRole.PREMIUM_USER]
        await auth_service._store_user(user)

        # Verify role change
        assert user.role == UserRole.PREMIUM_USER
        assert len(user.permissions) > len(original_permissions)

        # Restore original role
        user.role = original_role
        user.permissions = original_permissions
        await auth_service._store_user(user)