"""
Pytest configuration and fixtures for Hermes AI Assistant testing

This module provides common test fixtures, configurations, and utilities
for unit, integration, and end-to-end testing.
"""

import asyncio
import pytest
import pytest_asyncio
import tempfile
import shutil
from pathlib import Path
from typing import AsyncGenerator, Generator, Dict, Any
import json
import os
from unittest.mock import Mock, AsyncMock, patch
import redis.asyncio as redis
from fastapi.testclient import TestClient
from httpx import AsyncClient

# Import Hermes modules
from hermes.app import create_app
from hermes.security.auth_service import AuthenticationService, UserRole, Permission
from hermes.security.encryption import EncryptionService
from hermes.security.compliance import ComplianceManager
from hermes.middleware.rate_limiter import RateLimiter
from hermes.middleware.quota_manager import QuotaManager


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    """Create a temporary directory for test files."""
    temp_path = Path(tempfile.mkdtemp())
    yield temp_path
    shutil.rmtree(temp_path)


@pytest.fixture
async def redis_client() -> AsyncGenerator[redis.Redis, None]:
    """Create a Redis client for testing."""
    # Try to connect to local Redis, fallback to fakeredis if not available
    try:
        client = redis.from_url("redis://localhost:6379/15", decode_responses=True)
        await client.ping()
        yield client
        await client.flushdb()  # Clean up test data
        await client.close()
    except (redis.ConnectionError, ConnectionRefusedError):
        # Use fakeredis if available
        try:
            import fakeredis.aioredis as fake_redis
            client = fake_redis.FakeRedis(decode_responses=True)
            yield client
            await client.flushdb()
            await client.close()
        except ImportError:
            pytest.skip("Redis not available and fakeredis not installed")


@pytest.fixture
async def auth_service(redis_client: redis.Redis) -> AuthenticationService:
    """Create an authentication service for testing."""
    service = AuthenticationService(redis_url="redis://localhost:6379/15")
    await service.initialize()

    # Create test users
    await service.create_user(
        username="testuser",
        email="test@example.com",
        password="testpassword123",
        role=UserRole.BASIC_USER
    )

    await service.create_user(
        username="adminuser",
        email="admin@example.com",
        password="adminpassword123",
        role=UserRole.ADMIN
    )

    await service.create_user(
        username="premiumuser",
        email="premium@example.com",
        password="premiumpassword123",
        role=UserRole.PREMIUM_USER
    )

    return service


@pytest.fixture
async def encryption_service() -> EncryptionService:
    """Create an encryption service for testing."""
    service = EncryptionService()
    await service.initialize()
    return service


@pytest.fixture
async def compliance_manager(temp_dir: Path) -> ComplianceManager:
    """Create a compliance manager for testing."""
    service = ComplianceManager(storage_path=str(temp_dir / "compliance"))
    return service


@pytest.fixture
async def rate_limiter(redis_client: redis.Redis) -> RateLimiter:
    """Create a rate limiter for testing."""
    service = RateLimiter(redis_url="redis://localhost:6379/15")
    await service.initialize()
    return service


@pytest.fixture
async def quota_manager() -> QuotaManager:
    """Create a quota manager for testing."""
    service = QuotaManager()
    return service


@pytest.fixture
async def app(
    auth_service: AuthenticationService,
    encryption_service: EncryptionService,
    compliance_manager: ComplianceManager,
    rate_limiter: RateLimiter,
    quota_manager: QuotaManager
):
    """Create a FastAPI application for testing."""
    app = create_app()

    # Initialize security services
    from hermes.security.middleware import init_security_middleware
    await init_security_middleware(
        app=app,
        auth_service=auth_service,
        encryption_service=encryption_service,
        compliance_manager=compliance_manager
    )

    # Initialize rate limiting and quota management
    from hermes.middleware.rate_limit_integration import init_rate_limiting
    await init_rate_limiting(app, redis_url="redis://localhost:6379/15")

    return app


@pytest.fixture
def client(app) -> TestClient:
    """Create a test client for the FastAPI application."""
    return TestClient(app)


@pytest.fixture
async def async_client(app) -> AsyncGenerator[AsyncClient, None]:
    """Create an async test client for the FastAPI application."""
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac


@pytest.fixture
def test_user_data() -> Dict[str, Any]:
    """Sample user data for testing."""
    return {
        "username": "newuser",
        "email": "newuser@example.com",
        "password": "newpassword123",
        "role": "basic_user"
    }


@pytest.fixture
def test_encryption_data() -> Dict[str, Any]:
    """Sample data for encryption testing."""
    return {
        "simple_text": "This is a secret message",
        "json_data": {
            "user_id": "12345",
            "email": "user@example.com",
            "preferences": {
                "theme": "dark",
                "notifications": True
            }
        },
        "large_text": "A" * 10000  # 10KB of text
    }


@pytest.fixture
def test_compliance_events() -> Dict[str, Any]:
    """Sample compliance events for testing."""
    return {
        "login_event": {
            "event_type": "user_login",
            "user_id": "testuser",
            "ip_address": "192.168.1.100",
            "result": "success"
        },
        "data_access_event": {
            "event_type": "data_access",
            "user_id": "testuser",
            "resource_id": "document_123",
            "action": "read",
            "result": "success"
        },
        "security_event": {
            "event_type": "security_event",
            "user_id": "testuser",
            "ip_address": "192.168.1.100",
            "details": {
                "violation_type": "rate_limit_exceeded",
                "description": "User exceeded rate limit"
            }
        }
    }


@pytest.fixture
def mock_openai_response():
    """Mock OpenAI API response for testing."""
    return {
        "id": "chatcmpl-test123",
        "object": "chat.completion",
        "created": 1677652288,
        "model": "gpt-3.5-turbo",
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": "This is a test response from the AI assistant."
                },
                "finish_reason": "stop"
            }
        ],
        "usage": {
            "prompt_tokens": 10,
            "completion_tokens": 10,
            "total_tokens": 20
        }
    }


@pytest.fixture
def sample_config_data() -> Dict[str, Any]:
    """Sample configuration data for testing."""
    return {
        "model": {
            "name": "gpt-3.5-turbo",
            "temperature": 0.7,
            "max_tokens": 1000
        },
        "system": {
            "debug": False,
            "log_level": "INFO"
        },
        "features": {
            "streaming": True,
            "function_calling": True
        }
    }


# Test utilities
@pytest.fixture
def create_test_user(auth_service: AuthenticationService):
    """Utility fixture to create test users."""
    async def _create_user(
        username: str,
        email: str,
        password: str,
        role: UserRole = UserRole.BASIC_USER
    ) -> Dict[str, Any]:
        user = await auth_service.create_user(
            username=username,
            email=email,
            password=password,
            role=role
        )
        return {
            "user": user,
            "username": username,
            "password": password
        }

    return _create_user


@pytest.fixture
def create_api_key(auth_service: AuthenticationService):
    """Utility fixture to create API keys."""
    async def _create_api_key(
        user_id: str,
        name: str = "Test API Key",
        permissions: list = None
    ) -> tuple[str, str]:
        if permissions is None:
            permissions = [Permission.READ, Permission.WRITE]

        key_id, api_key = await auth_service.create_api_key(
            user_id=user_id,
            name=name,
            permissions=permissions
        )
        return key_id, api_key

    return _create_api_key


@pytest.fixture
def authenticate_client(client: TestClient, auth_service: AuthenticationService):
    """Utility fixture to authenticate a test client."""
    async def _authenticate(username: str, password: str) -> Dict[str, str]:
        # Login and get token
        response = client.post("/api/v1/auth/login", json={
            "username": username,
            "password": password
        })

        if response.status_code == 200:
            data = response.json()
            return {
                "Authorization": f"Bearer {data['access_token']}",
                "Content-Type": "application/json"
            }
        return {}

    return _authenticate


# Mock fixtures
@pytest.fixture
def mock_redis():
    """Create a mock Redis client."""
    mock_client = AsyncMock()
    mock_client.ping.return_value = True
    mock_client.get.return_value = None
    mock_client.set.return_value = True
    mock_client.setex.return_value = True
    mock_client.delete.return_value = 1
    mock_client.exists.return_value = 0
    mock_client.expire.return_value = True
    mock_client.keys.return_value = []
    mock_client.hgetall.return_value = {}
    mock_client.hset.return_value = True
    mock_client.hget.return_value = None
    return mock_client


@pytest.fixture
def mock_openai():
    """Create a mock OpenAI client."""
    mock_client = Mock()
    mock_response = Mock()
    mock_response.choices = [Mock()]
    mock_response.choices[0].message.content = "Test response"
    mock_response.choices[0].finish_reason = "stop"
    mock_response.usage.prompt_tokens = 10
    mock_response.usage.completion_tokens = 10
    mock_response.usage.total_tokens = 20
    mock_client.chat.completions.create.return_value = mock_response
    return mock_client


@pytest.fixture
def mock_s3():
    """Create a mock S3 client."""
    mock_client = Mock()
    mock_client.upload_fileobj.return_value = None
    mock_client.download_fileobj.return_value = None
    mock_client.list_objects_v2.return_value = {"Contents": []}
    mock_client.delete_object.return_value = None
    return mock_client


# Environment setup fixtures
@pytest.fixture(autouse=True)
def setup_test_environment():
    """Set up test environment variables."""
    original_env = os.environ.copy()

    # Set test environment variables
    os.environ.update({
        "TESTING": "true",
        "REDIS_URL": "redis://localhost:6379/15",
        "JWT_SECRET": "test-secret-key-for-jwt-signing",
        "ENCRYPTION_KEY": "test-encryption-key-32-bytes-long-key",
        "LOG_LEVEL": "DEBUG",
        "OPENAI_API_KEY": "test-openai-key",
        "AWS_ACCESS_KEY_ID": "test-aws-key",
        "AWS_SECRET_ACCESS_KEY": "test-aws-secret",
        "AWS_DEFAULT_REGION": "us-east-1"
    })

    yield

    # Restore original environment
    os.environ.clear()
    os.environ.update(original_env)


# Async test utilities
@pytest_asyncio.fixture
async def async_test_client(app):
    """Create an async test client with proper cleanup."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        yield client


# Database fixtures (if using database for testing)
@pytest.fixture
def test_database_url():
    """Provide a test database URL."""
    return "sqlite:///./test.db"


# Performance testing fixtures
@pytest.fixture
def performance_monitor():
    """Monitor performance during tests."""
    import time
    from collections import defaultdict

    class PerformanceMonitor:
        def __init__(self):
            self.metrics = defaultdict(list)
            self.start_times = {}

        def start_timer(self, name: str):
            self.start_times[name] = time.time()

        def end_timer(self, name: str):
            if name in self.start_times:
                duration = time.time() - self.start_times[name]
                self.metrics[name].append(duration)
                del self.start_times[name]
                return duration
            return None

        def get_stats(self, name: str) -> Dict[str, float]:
            if name not in self.metrics or not self.metrics[name]:
                return {}

            durations = self.metrics[name]
            return {
                "count": len(durations),
                "total": sum(durations),
                "average": sum(durations) / len(durations),
                "min": min(durations),
                "max": max(durations)
            }

    return PerformanceMonitor()


# Security testing fixtures
@pytest.fixture
def security_test_data():
    """Data for security testing."""
    return {
        "malicious_payload": {
            "sql_injection": "'; DROP TABLE users; --",
            "xss_payload": "<script>alert('xss')</script>",
            "path_traversal": "../../../etc/passwd",
            "command_injection": "; ls -la /"
        },
        "valid_payloads": {
            "normal_text": "This is normal text",
            "json_data": '{"key": "value"}',
            "email": "user@example.com",
            "phone": "+1-555-123-4567"
        }
    }


# Error handling fixtures
@pytest.fixture
def error_scenarios():
    """Common error scenarios for testing."""
    return {
        "network_errors": [
            "ConnectionError",
            "TimeoutError",
            "ConnectionRefusedError"
        ],
        "api_errors": [
            {"status_code": 400, "detail": "Bad Request"},
            {"status_code": 401, "detail": "Unauthorized"},
            {"status_code": 403, "detail": "Forbidden"},
            {"status_code": 404, "detail": "Not Found"},
            {"status_code": 429, "detail": "Rate Limited"},
            {"status_code": 500, "detail": "Internal Server Error"}
        ],
        "validation_errors": [
            {"field": "email", "message": "Invalid email format"},
            {"field": "password", "message": "Password too short"},
            {"field": "username", "message": "Username required"}
        ]
    }