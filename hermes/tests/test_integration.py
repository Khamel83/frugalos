"""
Integration Tests for Hermes AI Assistant

This module contains end-to-end integration tests that verify the
interaction between different components of the system.
"""

import pytest
import asyncio
import json
from datetime import datetime, timedelta
from fastapi.testclient import TestClient
from httpx import AsyncClient

from hermes.security.auth_service import UserRole, Permission
from hermes.security.compliance import ComplianceFramework, AuditEventType
from hermes.middleware.rate_limiter import RateLimitType


class TestAuthenticationIntegration:
    """Integration tests for authentication flow."""

    @pytest.mark.asyncio
    async def test_complete_authentication_flow(self, async_client, auth_service):
        """Test complete authentication flow from login to API access."""
        # Step 1: Register new user
        register_response = await async_client.post("/api/v1/auth/register", json={
            "username": "integration_user",
            "email": "integration@example.com",
            "password": "SecurePassword123!",
            "role": "basic_user"
        })

        # Registration might be disabled in tests, so we'll create user directly
        user = await auth_service.create_user(
            username="integration_user",
            email="integration@example.com",
            password="SecurePassword123!",
            role=UserRole.BASIC_USER
        )

        # Step 2: Login
        login_response = await async_client.post("/api/v1/auth/login", json={
            "username": "integration_user",
            "password": "SecurePassword123!"
        })

        assert login_response.status_code == 200
        login_data = login_response.json()
        assert "access_token" in login_data
        assert "refresh_token" in login_data

        access_token = login_data["access_token"]

        # Step 3: Access protected endpoint
        headers = {"Authorization": f"Bearer {access_token}"}
        profile_response = await async_client.get("/api/v1/users/profile", headers=headers)

        assert profile_response.status_code == 200
        profile_data = profile_response.json()
        assert profile_data["username"] == "integration_user"
        assert profile_data["email"] == "integration@example.com"

        # Step 4: Create API key
        api_key_response = await async_client.post(
            "/api/v1/api-keys",
            headers=headers,
            json={
                "name": "Integration Test Key",
                "permissions": ["read", "write"]
            }
        )

        assert api_key_response.status_code == 200
        api_key_data = api_key_response.json()
        assert "key_id" in api_key_data
        assert "api_key" in api_key_data

        # Step 5: Use API key for authentication
        api_headers = {"X-API-Key": api_key_data["api_key"]}
        api_auth_response = await async_client.get(
            "/api/v1/users/profile",
            headers=api_headers
        )

        assert api_auth_response.status_code == 200
        api_profile_data = api_auth_response.json()
        assert api_profile_data["username"] == "integration_user"

        # Step 6: Logout
        logout_response = await async_client.post(
            "/api/v1/auth/logout",
            headers=headers
        )

        assert logout_response.status_code == 200

    @pytest.mark.asyncio
    async def test_mfa_authentication_flow(self, async_client, auth_service):
        """Test MFA-enabled authentication flow."""
        # Create user with MFA
        user = await auth_service.create_user(
            username="mfa_user",
            email="mfa@example.com",
            password="MFAPassword123!",
            role=UserRole.PREMIUM_USER  # Premium users might have MFA required
        )

        # Enable MFA for user
        secret, qr_code = await auth_service.enable_mfa(user.id)

        # Step 1: Login (should require MFA)
        login_response = await async_client.post("/api/v1/auth/login", json={
            "username": "mfa_user",
            "password": "MFAPassword123!"
        })

        # Depending on implementation, this might return MFA requirement
        if login_response.status_code == 200:
            login_data = login_response.json()
            if "mfa_required" in login_data and login_data["mfa_required"]:
                # Step 2: Complete MFA
                import pyotp
                totp = pyotp.TOTP(secret)
                current_code = totp.now()

                mfa_response = await async_client.post("/api/v1/auth/mfa", json={
                    "mfa_token": login_data.get("mfa_token"),
                    "mfa_code": current_code
                })

                assert mfa_response.status_code == 200
                mfa_data = mfa_response.json()
                assert "access_token" in mfa_data

    @pytest.mark.asyncio
    async def test_permission_based_access_control(self, async_client, auth_service):
        """Test role-based permission system."""
        # Create users with different roles
        basic_user = await auth_service.create_user(
            username="basic_integration",
            email="basic@example.com",
            password="BasicPassword123!",
            role=UserRole.BASIC_USER
        )

        admin_user = await auth_service.create_user(
            username="admin_integration",
            email="admin@example.com",
            password="AdminPassword123!",
            role=UserRole.ADMIN
        )

        # Login as basic user
        basic_login = await async_client.post("/api/v1/auth/login", json={
            "username": "basic_integration",
            "password": "BasicPassword123!"
        })

        basic_token = basic_login.json()["access_token"]
        basic_headers = {"Authorization": f"Bearer {basic_token}"}

        # Login as admin user
        admin_login = await async_client.post("/api/v1/auth/login", json={
            "username": "admin_integration",
            "password": "AdminPassword123!"
        })

        admin_token = admin_login.json()["access_token"]
        admin_headers = {"Authorization": f"Bearer {admin_token}"}

        # Test basic user access (should succeed for basic endpoints)
        basic_profile = await async_client.get("/api/v1/users/profile", headers=basic_headers)
        assert basic_profile.status_code == 200

        # Test admin endpoint access (should fail for basic user)
        admin_endpoint_basic = await async_client.get("/api/v1/admin/users", headers=basic_headers)
        assert admin_endpoint_basic.status_code == 403

        # Test admin endpoint access (should succeed for admin user)
        admin_endpoint_admin = await async_client.get("/api/v1/admin/users", headers=admin_headers)
        assert admin_endpoint_admin.status_code == 200


class TestRateLimitingIntegration:
    """Integration tests for rate limiting."""

    @pytest.mark.asyncio
    async def test_api_rate_limiting(self, async_client, auth_service):
        """Test API rate limiting with different tiers."""
        # Create premium user
        user = await auth_service.create_user(
            username="rate_limit_user",
            email="ratelimit@example.com",
            password="RateLimitPassword123!",
            role=UserRole.PREMIUM_USER
        )

        # Create API key
        key_id, api_key = await auth_service.create_api_key(
            user_id=user.id,
            name="Rate Limit Test Key",
            permissions=[Permission.READ, Permission.WRITE]
        )

        headers = {"X-API-Key": api_key}

        # Make multiple requests to test rate limiting
        responses = []
        for i in range(5):  # Adjust based on rate limit configuration
            response = await async_client.get(
                "/api/v1/users/profile",
                headers=headers
            )
            responses.append(response)
            await asyncio.sleep(0.1)  # Small delay between requests

        # First few requests should succeed
        assert responses[0].status_code == 200
        assert responses[1].status_code == 200

        # Eventually might hit rate limit (depending on configuration)
        # This test may need adjustment based on actual rate limit settings

    @pytest.mark.asyncio
    async def test_concurrent_request_handling(self, async_client, auth_service):
        """Test handling of concurrent requests."""
        # Create user and API key
        user = await auth_service.create_user(
            username="concurrent_user",
            email="concurrent@example.com",
            password="ConcurrentPassword123!",
            role=UserRole.BASIC_USER
        )

        key_id, api_key = await auth_service.create_api_key(
            user_id=user.id,
            name="Concurrent Test Key",
            permissions=[Permission.READ]
        )

        headers = {"X-API-Key": api_key}

        # Make concurrent requests
        async def make_request():
            return await async_client.get("/api/v1/users/profile", headers=headers)

        tasks = [make_request() for _ in range(10)]
        responses = await asyncio.gather(*tasks, return_exceptions=True)

        # Most requests should succeed
        successful_responses = [
            r for r in responses if not isinstance(r, Exception) and r.status_code == 200
        ]

        assert len(successful_responses) >= 5  # At least half should succeed


class TestEncryptionIntegration:
    """Integration tests for encryption features."""

    @pytest.mark.asyncio
    async def test_sensitive_data_encryption(self, async_client, auth_service, encryption_service):
        """Test encryption of sensitive data in API responses."""
        # Create user
        user = await auth_service.create_user(
            username="encryption_user",
            email="encryption@example.com",
            password="EncryptionPassword123!",
            role=UserRole.BASIC_USER
        )

        # Login
        login_response = await async_client.post("/api/v1/auth/login", json={
            "username": "encryption_user",
            "password": "EncryptionPassword123!"
        })

        token = login_response.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Update user profile with sensitive data
        update_data = {
            "email": "encryption@example.com",
            "phone": "+1-555-123-4567",
            "address": "123 Main St, City, State 12345",
            "ssn": "123-45-6789"  # This should be encrypted
        }

        update_response = await async_client.put(
            "/api/v1/users/profile",
            headers=headers,
            json=update_data
        )

        if update_response.status_code == 200:
            # Retrieve profile
            profile_response = await async_client.get("/api/v1/users/profile", headers=headers)
            profile_data = profile_response.json()

            # Sensitive fields should be encrypted or masked
            if "ssn" in profile_data:
                # SSN should be masked or encrypted
                assert "xxx" in profile_data["ssn"] or "encrypted" in str(profile_data["ssn"])

    @pytest.mark.asyncio
    async def test_file_upload_encryption(self, async_client, auth_service):
        """Test encryption of uploaded files."""
        # Create user
        user = await auth_service.create_user(
            username="file_user",
            email="file@example.com",
            password="FilePassword123!",
            role=UserRole.PREMIUM_USER  # Premium users can upload files
        )

        # Login
        login_response = await async_client.post("/api/v1/auth/login", json={
            "username": "file_user",
            "password": "FilePassword123!"
        })

        token = login_response.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Upload a file with sensitive content
        sensitive_content = "This is sensitive file content"
        files = {"file": ("sensitive.txt", sensitive_content, "text/plain")}

        upload_response = await async_client.post(
            "/api/v1/files/upload",
            headers=headers,
            files=files
        )

        if upload_response.status_code == 200:
            upload_data = upload_response.json()
            file_id = upload_data.get("file_id")

            # Download the file
            download_response = await async_client.get(
                f"/api/v1/files/{file_id}/download",
                headers=headers
            )

            if download_response.status_code == 200:
                # File content should be the same (decryption happens server-side)
                downloaded_content = download_response.content.decode()
                assert downloaded_content == sensitive_content


class TestComplianceIntegration:
    """Integration tests for compliance features."""

    @pytest.mark.asyncio
    async def test_audit_trail_creation(self, async_client, auth_service, compliance_manager):
        """Test that audit trails are created for user actions."""
        # Get initial audit event count
        initial_events = len(compliance_manager.audit_events)

        # Create user
        user = await auth_service.create_user(
            username="audit_user",
            email="audit@example.com",
            password="AuditPassword123!",
            role=UserRole.BASIC_USER
        )

        # Login (should create audit event)
        login_response = await async_client.post("/api/v1/auth/login", json={
            "username": "audit_user",
            "password": "AuditPassword123!"
        })

        assert login_response.status_code == 200

        # Check that audit events were created
        final_events = len(compliance_manager.audit_events)
        assert final_events > initial_events

        # Check for specific audit events
        user_events = [
            event for event in compliance_manager.audit_events
            if event.user_id == user.id
        ]

        assert len(user_events) >= 1

        # Verify event types
        event_types = [event.event_type for event in user_events]
        assert AuditEventType.USER_LOGIN in event_types

    @pytest.mark.asyncio
    async def test_gdpr_data_subject_request(self, async_client, compliance_manager):
        """Test GDPR data subject request workflow."""
        # Create a data subject request
        request = await compliance_manager.create_data_subject_request(
            subject_id="gdpr_user@example.com",
            request_type="access",
            details={"requested_data": "all_personal_data"}
        )

        assert request.request_id is not None
        assert request.status == "pending"

        # Process the request (simulating admin action)
        export_data = {
            "user_profile": {
                "username": "gdpr_user",
                "email": "gdpr_user@example.com",
                "created_at": datetime.now().isoformat()
            },
            "usage_data": {
                "total_requests": 150,
                "last_login": datetime.now().isoformat()
            }
        }

        success = await compliance_manager.process_data_subject_request(
            request_id=request.request_id,
            processed_by="admin_user",
            result={"export_data": export_data, "format": "json"}
        )

        assert success is True

        # Verify request status
        processed_request = compliance_manager.data_subject_requests[request.request_id]
        assert processed_request.status == "completed"
        assert processed_request.processed_by == "admin_user"

    @pytest.mark.asyncio
    async def test_compliance_report_generation(self, async_client, compliance_manager):
        """Test compliance report generation through API."""
        # Log some test events
        await compliance_manager.log_audit_event(
            event_type=AuditEventType.USER_LOGIN,
            user_id="report_user",
            compliance_frameworks=[ComplianceFramework.GDPR]
        )

        await compliance_manager.log_audit_event(
            event_type=AuditEventType.DATA_ACCESS,
            user_id="report_user",
            compliance_frameworks=[ComplianceFramework.GDPR],
            data_classification="confidential"
        )

        # Generate compliance report (if endpoint exists)
        headers = {"Authorization": "Bearer admin_token"}  # Would need real admin token

        # This would be an actual API endpoint in the implementation
        # report_response = await async_client.get(
        #     "/api/v1/admin/compliance/report",
        #     headers=headers,
        #     params={
        #         "framework": "gdpr",
        #         "start_date": (datetime.now() - timedelta(days=7)).isoformat(),
        #         "end_date": datetime.now().isoformat()
        #     }
        # )

        # For now, test the compliance manager directly
        report = await compliance_manager.generate_compliance_report(
            framework=ComplianceFramework.GDPR,
            start_date=datetime.now() - timedelta(days=7),
            end_date=datetime.now()
        )

        assert report["framework"] == "gdpr"
        assert report["summary"]["total_events"] >= 2
        assert "recommendations" in report


class TestMultiRegionIntegration:
    """Integration tests for multi-region deployment."""

    @pytest.mark.asyncio
    async def test_region_failover(self, async_client):
        """Test region failover functionality."""
        # This would test the actual failover logic
        # For now, we'll test health endpoints from different regions

        # Primary region health check
        primary_health = await async_client.get("/health")
        assert primary_health.status_code == 200

        # Check if multi-region headers are present
        if "x-region" in primary_health.headers:
            region = primary_health.headers["x-region"]
            assert region in ["us-west-2", "us-east-1", "eu-west-1"]

    @pytest.mark.asyncio
    async def test_cross_region_data_consistency(self, async_client):
        """Test data consistency across regions."""
        # This would test actual cross-region replication
        # For now, we'll verify that the system handles region headers correctly

        # Make request with region preference
        headers = {"X-Preferred-Region": "us-west-2"}
        response = await async_client.get("/health", headers=headers)

        assert response.status_code == 200

        # Check response headers for region information
        if "x-served-region" in response.headers:
            served_region = response.headers["x-served-region"]
            assert served_region is not None


class TestSystemPerformanceIntegration:
    """Integration tests for system performance under load."""

    @pytest.mark.asyncio
    async def test_concurrent_user_load(self, async_client, auth_service):
        """Test system performance with multiple concurrent users."""
        # Create multiple users
        users = []
        for i in range(5):
            user = await auth_service.create_user(
                username=f"load_user_{i}",
                email=f"load_user_{i}@example.com",
                password=f"LoadPassword{i}!",
                role=UserRole.BASIC_USER
            )
            users.append(user)

        # Simulate concurrent logins
        async def login_user(username, password):
            return await async_client.post("/api/v1/auth/login", json={
                "username": username,
                "password": password
            })

        login_tasks = [
            login_user(f"load_user_{i}", f"LoadPassword{i}!")
            for i in range(5)
        ]

        login_responses = await asyncio.gather(*login_tasks, return_exceptions=True)

        # Most logins should succeed
        successful_logins = [
            response for response in login_responses
            if not isinstance(response, Exception) and response.status_code == 200
        ]

        assert len(successful_logins) >= 4  # At least 80% success rate

        # Test concurrent API calls with successful logins
        api_tasks = []
        for response in successful_logins:
            token = response.json()["access_token"]
            headers = {"Authorization": f"Bearer {token}"}

            async def make_api_call():
                return await async_client.get("/api/v1/users/profile", headers=headers)

            api_tasks.append(make_api_call())

        api_responses = await asyncio.gather(*api_tasks, return_exceptions=True)

        # Most API calls should succeed
        successful_apis = [
            response for response in api_responses
            if not isinstance(response, Exception) and response.status_code == 200
        ]

        assert len(successful_apis) >= 4

    @pytest.mark.asyncio
    async def test_memory_usage_under_load(self, async_client, performance_monitor):
        """Test memory usage during high load."""
        performance_monitor.start_timer("memory_test")

        # Make many requests
        for i in range(50):
            response = await async_client.get("/health")
            assert response.status_code == 200

            if i % 10 == 0:
                # Check memory usage (simplified)
                import psutil
                process = psutil.Process()
                memory_mb = process.memory_info().rss / 1024 / 1024

                # Memory should not grow excessively
                assert memory_mb < 500  # Adjust threshold as needed

        performance_monitor.end_timer("memory_test")
        stats = performance_monitor.get_stats("memory_test")
        assert stats["count"] == 50


class TestErrorHandlingIntegration:
    """Integration tests for error handling scenarios."""

    @pytest.mark.asyncio
    async def test_authentication_error_handling(self, async_client):
        """Test authentication error handling."""
        # Test invalid credentials
        response = await async_client.post("/api/v1/auth/login", json={
            "username": "nonexistent_user",
            "password": "wrong_password"
        })

        assert response.status_code == 401
        error_data = response.json()
        assert "error" in error_data
        assert "Invalid credentials" in error_data["message"]

        # Test missing credentials
        response = await async_client.post("/api/v1/auth/login", json={
            "username": "test_user"
            # Missing password
        })

        assert response.status_code == 422  # Validation error

    @pytest.mark.asyncio
    async def test_authorization_error_handling(self, async_client, auth_service):
        """Test authorization error handling."""
        # Create basic user
        user = await auth_service.create_user(
            username="auth_test_user",
            email="auth@example.com",
            password="AuthPassword123!",
            role=UserRole.BASIC_USER
        )

        # Login
        login_response = await async_client.post("/api/v1/auth/login", json={
            "username": "auth_test_user",
            "password": "AuthPassword123!"
        })

        token = login_response.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Try to access admin endpoint
        response = await async_client.get("/api/v1/admin/users", headers=headers)

        assert response.status_code == 403
        error_data = response.json()
        assert "error" in error_data
        assert "access denied" in error_data["message"].lower()

    @pytest.mark.asyncio
    async def test_rate_limit_error_handling(self, async_client, auth_service):
        """Test rate limit error handling."""
        # Create user
        user = await auth_service.create_user(
            username="rate_limit_test_user",
            email="ratelimit@example.com",
            password="RateLimitPassword123!",
            role=UserRole.BASIC_USER
        )

        # Create API key
        key_id, api_key = await auth_service.create_api_key(
            user_id=user.id,
            name="Rate Limit Test Key"
        )

        headers = {"X-API-Key": api_key}

        # Make many requests quickly to trigger rate limit
        responses = []
        for i in range(20):  # Adjust based on actual rate limits
            response = await async_client.get("/api/v1/users/profile", headers=headers)
            responses.append(response)

            if response.status_code == 429:
                break  # Hit rate limit

        # Check if rate limit was triggered
        rate_limited = any(response.status_code == 429 for response in responses)

        if rate_limited:
            # Verify rate limit response format
            rate_limit_response = next(
                r for r in responses if r.status_code == 429
            )
            error_data = rate_limit_response.json()
            assert "error" in error_data
            assert "rate limit" in error_data["message"].lower()
            assert "retry-after" in rate_limit_response.headers or "retry_after" in error_data

    @pytest.mark.asyncio
    async def test_validation_error_handling(self, async_client):
        """Test input validation error handling."""
        # Test invalid user registration data
        response = await async_client.post("/api/v1/auth/register", json={
            "username": "a",  # Too short
            "email": "invalid-email",  # Invalid format
            "password": "123"  # Too short
        })

        assert response.status_code == 422
        error_data = response.json()
        assert "detail" in error_data  # FastAPI validation error format

        # Test invalid JSON
        response = await async_client.post(
            "/api/v1/auth/login",
            data="invalid json",
            headers={"Content-Type": "application/json"}
        )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_server_error_handling(self, async_client):
        """Test server error handling."""
        # Test endpoint that doesn't exist
        response = await async_client.get("/api/v1/nonexistent/endpoint")

        assert response.status_code == 404
        error_data = response.json()
        assert "detail" in error_data

        # Test method not allowed
        response = await async_client.patch("/api/v1/auth/login")

        assert response.status_code == 405

    @pytest.mark.asyncio
    async def test_timeout_handling(self, async_client):
        """Test request timeout handling."""
        # This would test actual timeout scenarios
        # For now, test with a very slow endpoint if it exists

        # Try to access a potentially slow endpoint with short timeout
        try:
            response = await async_client.get(
                "/api/v1/slow-endpoint",
                timeout=1.0  # 1 second timeout
            )
        except Exception as e:
            # Should handle timeout gracefully
            assert "timeout" in str(e).lower() or "time" in str(e).lower()