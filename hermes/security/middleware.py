"""
Security Middleware for FastAPI Applications

This module provides security middleware components including:
- Authentication middleware
- Authorization middleware
- Security headers
- CSRF protection
- Rate limiting integration
- Audit logging
"""

import time
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Callable
from fastapi import FastAPI, Request, Response, HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.base import BaseHTTPMiddleware
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import RequestResponseEndpoint
from starlette.responses import JSONResponse
import logging
import ipaddress
import re
from urllib.parse import urlparse

from .auth_service import AuthenticationService, AuthResult, AuthMethod, Permission
from .encryption import EncryptionService
from .compliance import ComplianceManager, AuditEventType, DataClassification

logger = logging.getLogger(__name__)

# Global instances
auth_service: Optional[AuthenticationService] = None
encryption_service: Optional[EncryptionService] = None
compliance_manager: Optional[ComplianceManager] = None


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add security headers to all responses"""

    def __init__(self, app, security_config: Optional[Dict[str, Any]] = None):
        super().__init__(app)
        self.security_config = security_config or self._default_security_config()

    def _default_security_config(self) -> Dict[str, Any]:
        """Default security configuration"""
        return {
            "strict_transport_security": "max-age=31536000; includeSubDomains",
            "content_type_options": "nosniff",
            "frame_options": "DENY",
            "xss_protection": "1; mode=block",
            "referrer_policy": "strict-origin-when-cross-origin",
            "content_security_policy": (
                "default-src 'self'; "
                "script-src 'self' 'unsafe-inline' 'unsafe-eval'; "
                "style-src 'self' 'unsafe-inline'; "
                "img-src 'self' data: https:; "
                "font-src 'self' data:; "
                "connect-src 'self' https:; "
                "frame-ancestors 'none';"
            ),
            "permissions_policy": (
                "geolocation=(), "
                "microphone=(), "
                "camera=(), "
                "payment=(), "
                "usb=()"
            )
        }

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        response = await call_next(request)

        # Add security headers
        response.headers["X-Content-Type-Options"] = self.security_config["content_type_options"]
        response.headers["X-Frame-Options"] = self.security_config["frame_options"]
        response.headers["X-XSS-Protection"] = self.security_config["xss_protection"]
        response.headers["Referrer-Policy"] = self.security_config["referrer_policy"]
        response.headers["Content-Security-Policy"] = self.security_config["content_security_policy"]
        response.headers["Permissions-Policy"] = self.security_config["permissions_policy"]

        # Add HSTS header for HTTPS
        if request.url.scheme == "https":
            response.headers["Strict-Transport-Security"] = self.security_config["strict_transport_security"]

        # Add custom security headers
        response.headers["X-Request-ID"] = getattr(request.state, "request_id", str(uuid.uuid4()))
        response.headers["X-Response-Time"] = f"{getattr(request.state, 'start_time', time.time()):.3f}"

        return response


class AuthenticationMiddleware(BaseHTTPMiddleware):
    """Authentication middleware for API endpoints"""

    def __init__(
        self,
        app,
        auth_service: AuthenticationService,
        public_paths: Optional[List[str]] = None,
        api_key_paths: Optional[List[str]] = None
    ):
        super().__init__(app)
        self.auth_service = auth_service
        self.public_paths = public_paths or [
            "/health",
            "/status",
            "/docs",
            "/openapi.json",
            "/redoc",
            "/favicon.ico"
        ]
        self.api_key_paths = api_key_paths or [
            "/api/v1/",
            "/webhook/",
            "/integration/"
        ]

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        # Generate request ID and set start time
        request.state.request_id = str(uuid.uuid4())
        request.state.start_time = time.time()

        # Check if path is public
        if self._is_public_path(request.url.path):
            return await call_next(request)

        # Try to authenticate
        auth_result = await self._authenticate_request(request)

        if not auth_result.success:
            return self._create_auth_error_response(auth_result)

        # Store auth result in request state
        request.state.user = auth_result.user
        request.state.session = auth_result.session
        request.state.permissions = auth_result.permissions

        # Log successful authentication
        if compliance_manager:
            await compliance_manager.log_audit_event(
                event_type=AuditEventType.USER_LOGIN,
                user_id=auth_result.user.id if auth_result.user else None,
                session_id=auth_result.session.session_id if auth_result.session else None,
                ip_address=request.client.host,
                user_agent=request.headers.get("user-agent"),
                result="success",
                details={"auth_method": self._detect_auth_method(request)}
            )

        return await call_next(request)

    def _is_public_path(self, path: str) -> bool:
        """Check if path is public"""
        return any(path.startswith(public_path) for public_path in self.public_paths)

    async def _authenticate_request(self, request: Request) -> AuthResult:
        """Authenticate the request"""
        # Try API key authentication first for API paths
        if self._is_api_key_path(request.url.path):
            api_key = request.headers.get("X-API-Key")
            if api_key:
                return await self.auth_service.authenticate(
                    AuthMethod.API_KEY,
                    {"api_key": api_key},
                    ip_address=request.client.host,
                    user_agent=request.headers.get("user-agent")
                )

        # Try JWT authentication
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header[7:]  # Remove "Bearer " prefix
            return await self.auth_service.authenticate(
                AuthMethod.JWT,
                {"token": token},
                ip_address=request.client.host,
                user_agent=request.headers.get("user-agent")
            )

        # Try session cookie authentication (if implemented)
        session_cookie = request.cookies.get("session_id")
        if session_cookie:
            return await self.auth_service.authenticate(
                AuthMethod.JWT,
                {"token": session_cookie},  # Using JWT for session
                ip_address=request.client.host,
                user_agent=request.headers.get("user-agent")
            )

        # No authentication provided
        return AuthResult(
            success=False,
            error_message="Authentication required"
        )

    def _is_api_key_path(self, path: str) -> bool:
        """Check if path accepts API key authentication"""
        return any(path.startswith(api_path) for api_path in self.api_key_paths)

    def _detect_auth_method(self, request: Request) -> str:
        """Detect authentication method used"""
        if request.headers.get("X-API-Key"):
            return "api_key"
        elif request.headers.get("Authorization", "").startswith("Bearer "):
            return "jwt"
        elif request.cookies.get("session_id"):
            return "session"
        else:
            return "none"

    def _create_auth_error_response(self, auth_result: AuthResult) -> JSONResponse:
        """Create authentication error response"""
        status_code = status.HTTP_401_UNAUTHORIZED

        if auth_result.mfa_required:
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={
                    "error": "MFA required",
                    "message": "Multi-factor authentication required",
                    "mfa_token": auth_result.mfa_token
                },
                headers={"WWW-Authenticate": "MFA required"}
            )

        return JSONResponse(
            status_code=status_code,
            content={
                "error": "Authentication failed",
                "message": auth_result.error_message or "Invalid credentials"
            },
            headers={"WWW-Authenticate": "Bearer"}
        )


class AuthorizationMiddleware(BaseHTTPMiddleware):
    """Authorization middleware for role-based access control"""

    def __init__(
        self,
        app,
        permission_map: Optional[Dict[str, List[Permission]]] = None,
        admin_paths: Optional[List[str]] = None
    ):
        super().__init__(app)
        self.permission_map = permission_map or self._default_permission_map()
        self.admin_paths = admin_paths or [
            "/admin/",
            "/api/v1/admin/",
            "/system/"
        ]

    def _default_permission_map(self) -> Dict[str, List[Permission]]:
        """Default permission mapping"""
        return {
            "GET": [Permission.READ],
            "POST": [Permission.WRITE],
            "PUT": [Permission.WRITE],
            "PATCH": [Permission.WRITE],
            "DELETE": [Permission.DELETE],
            "/api/v1/users": [Permission.MANAGE_USERS],
            "/api/v1/quotas": [Permission.MANAGE_QUOTAS],
            "/api/v1/analytics": [Permission.VIEW_ANALYTICS],
            "/api/v1/api-keys": [Permission.MANAGE_API_KEYS],
            "/api/v1/models/all": [Permission.ACCESS_ALL_MODELS],
            "/api/v1/bulk": [Permission.BULK_OPERATIONS],
        }

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        # Skip authorization for public paths or if no user
        if not hasattr(request.state, "user") or not request.state.user:
            return await call_next(request)

        user = request.state.user
        method = request.method
        path = request.url.path

        # Check admin paths
        if self._is_admin_path(path):
            if not await self.auth_service.check_permission(user.id, Permission.ADMIN):
                return self._create_permission_error_response("Admin access required")

        # Check path-specific permissions
        required_permissions = self._get_required_permissions(method, path)
        if required_permissions:
            for permission in required_permissions:
                if not await self.auth_service.check_permission(user.id, permission):
                    return self._create_permission_error_response(
                        f"Permission required: {permission.value}"
                    )

        # Log authorized access
        if compliance_manager:
            await compliance_manager.log_audit_event(
                event_type=AuditEventType.DATA_ACCESS,
                user_id=user.id,
                ip_address=request.client.host,
                resource_path=path,
                action=method,
                result="authorized",
                details={
                    "permissions": [p.value for p in required_permissions],
                    "user_role": user.role.value
                }
            )

        return await call_next(request)

    def _is_admin_path(self, path: str) -> bool:
        """Check if path requires admin access"""
        return any(path.startswith(admin_path) for admin_path in self.admin_paths)

    def _get_required_permissions(self, method: str, path: str) -> List[Permission]:
        """Get required permissions for method and path"""
        # Check specific path permissions first
        for path_pattern, permissions in self.permission_map.items():
            if path.startswith(path_pattern):
                return permissions

        # Check method permissions
        method_permissions = self.permission_map.get(method, [])
        return method_permissions

    def _create_permission_error_response(self, message: str) -> JSONResponse:
        """Create permission error response"""
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content={
                "error": "Access denied",
                "message": message
            }
        )


class AuditLoggingMiddleware(BaseHTTPMiddleware):
    """Audit logging middleware"""

    def __init__(self, app, compliance_manager: ComplianceManager):
        super().__init__(app)
        self.compliance_manager = compliance_manager

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        start_time = time.time()
        response = await call_next(request)
        end_time = time.time()

        # Determine audit event type
        event_type = self._get_audit_event_type(request, response)

        # Get user information if available
        user_id = None
        if hasattr(request.state, "user") and request.state.user:
            user_id = request.state.user.id

        # Log audit event
        await self.compliance_manager.log_audit_event(
            event_type=event_type,
            user_id=user_id,
            ip_address=request.client.host,
            user_agent=request.headers.get("user-agent"),
            resource_path=request.url.path,
            action=request.method,
            result="success" if response.status_code < 400 else "error",
            details={
                "status_code": response.status_code,
                "response_time_ms": round((end_time - start_time) * 1000, 2),
                "request_id": getattr(request.state, "request_id", None),
                "content_length": response.headers.get("content-length"),
                "content_type": response.headers.get("content-type")
            },
            data_classification=self._classify_request_data(request)
        )

        return response

    def _get_audit_event_type(self, request: Request, response: Response) -> AuditEventType:
        """Determine audit event type based on request"""
        path = request.url.path
        method = request.method

        if "login" in path:
            return AuditEventType.USER_LOGIN
        elif "logout" in path:
            return AuditEventType.USER_LOGOUT
        elif "register" in path:
            return AuditEventType.USER_REGISTRATION
        elif "password" in path:
            return AuditEventType.PASSWORD_CHANGE
        elif "mfa" in path:
            if method == "POST":
                return AuditEventType.MFA_ENABLED
            else:
                return AuditEventType.MFA_DISABLED
        elif "api-key" in path:
            if method == "POST":
                return AuditEventType.API_KEY_CREATED
            elif method == "DELETE":
                return AuditEventType.API_KEY_REVOKED
        elif response.status_code >= 400:
            return AuditEventType.SECURITY_EVENT
        else:
            return AuditEventType.DATA_ACCESS

    def _classify_request_data(self, request: Request) -> DataClassification:
        """Classify data sensitivity of request"""
        path = request.url.path

        if any(keyword in path for keyword in ["admin", "system", "config"]):
            return DataClassification.RESTRICTED
        elif any(keyword in path for keyword in ["user", "profile", "quota"]):
            return DataClassification.CONFIDENTIAL
        elif any(keyword in path for keyword in ["public", "health", "status"]):
            return DataClassification.PUBLIC
        else:
            return DataClassification.INTERNAL


class IPWhitelistMiddleware(BaseHTTPMiddleware):
    """IP whitelist middleware for admin access"""

    def __init__(self, app, allowed_ips: Optional[List[str]] = None, whitelist_paths: Optional[List[str]] = None):
        super().__init__(app)
        self.allowed_networks = []
        if allowed_ips:
            for ip in allowed_ips:
                try:
                    self.allowed_networks.append(ipaddress.ip_network(ip))
                except ValueError:
                    logger.warning(f"Invalid IP network in whitelist: {ip}")

        self.whitelist_paths = whitelist_paths or [
            "/admin/",
            "/api/v1/admin/",
            "/system/"
        ]

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        # Only apply to whitelisted paths
        if not self._is_whitelist_path(request.url.path):
            return await call_next(request)

        # Check if IP is allowed
        client_ip = ipaddress.ip_address(request.client.host)
        if not any(client_ip in network for network in self.allowed_networks):
            # Log security event
            if compliance_manager:
                await compliance_manager.log_audit_event(
                    event_type=AuditEventType.SECURITY_EVENT,
                    ip_address=request.client.host,
                    resource_path=request.url.path,
                    action=request.method,
                    result="denied",
                    details={
                        "reason": "IP not in whitelist",
                        "client_ip": str(client_ip)
                    }
                )

            return JSONResponse(
                status_code=status.HTTP_403_FORBIDDEN,
                content={
                    "error": "Access denied",
                    "message": "IP address not authorized"
                }
            )

        return await call_next(request)

    def _is_whitelist_path(self, path: str) -> bool:
        """Check if path requires IP whitelist"""
        return any(path.startswith(whitelist_path) for whitelist_path in self.whitelist_paths)


class CSRFProtectionMiddleware(BaseHTTPMiddleware):
    """CSRF protection middleware"""

    def __init__(self, app, exempt_paths: Optional[List[str]] = None):
        super().__init__(app)
        self.exempt_paths = exempt_paths or [
            "/health",
            "/status",
            "/api/v1/webhook/",
            "/api/v1/integration/"
        ]

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        # Skip CSRF protection for exempt paths and safe methods
        if (self._is_exempt_path(request.url.path) or
            request.method in ["GET", "HEAD", "OPTIONS", "TRACE"]):
            return await call_next(request)

        # Check CSRF token for state-changing methods
        if request.method in ["POST", "PUT", "PATCH", "DELETE"]:
            csrf_token = request.headers.get("X-CSRF-Token")
            if not csrf_token:
                return JSONResponse(
                    status_code=status.HTTP_403_FORBIDDEN,
                    content={
                        "error": "CSRF protection",
                        "message": "CSRF token required"
                    }
                )

            # Validate CSRF token (simplified implementation)
            session_token = getattr(request.state, "session_id", None)
            if not self._validate_csrf_token(csrf_token, session_token):
                return JSONResponse(
                    status_code=status.HTTP_403_FORBIDDEN,
                    content={
                        "error": "CSRF protection",
                        "message": "Invalid CSRF token"
                    }
                )

        return await call_next(request)

    def _is_exempt_path(self, path: str) -> bool:
        """Check if path is exempt from CSRF protection"""
        return any(path.startswith(exempt_path) for exempt_path in self.exempt_paths)

    def _validate_csrf_token(self, csrf_token: str, session_token: Optional[str]) -> bool:
        """Validate CSRF token (simplified implementation)"""
        # In production, implement proper CSRF token validation
        # This is a placeholder that validates token format
        return len(csrf_token) >= 32 and session_token is not None


async def init_security_middleware(
    app: FastAPI,
    auth_service: AuthenticationService,
    encryption_service: EncryptionService,
    compliance_manager: ComplianceManager,
    security_config: Optional[Dict[str, Any]] = None
):
    """Initialize all security middleware"""
    global auth_service, encryption_service, compliance_manager
    auth_service = auth_service
    encryption_service = encryption_service
    compliance_manager = compliance_manager

    # Add security headers
    app.add_middleware(SecurityHeadersMiddleware, security_config=security_config)

    # Add authentication middleware
    app.add_middleware(AuthenticationMiddleware, auth_service=auth_service)

    # Add authorization middleware
    app.add_middleware(AuthorizationMiddleware)

    # Add audit logging middleware
    app.add_middleware(AuditLoggingMiddleware, compliance_manager=compliance_manager)

    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["https://hermes-ai.com", "https://www.hermes-ai.com"],
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE"],
        allow_headers=["*"],
    )

    logger.info("Security middleware initialized")


# Dependency functions for FastAPI
async def get_current_user(request: Request) -> Optional[Any]:
    """Get current authenticated user"""
    return getattr(request.state, "user", None)


async def get_current_permissions(request: Request) -> List[Permission]:
    """Get current user permissions"""
    return getattr(request.state, "permissions", [])


async def require_permission(permission: Permission):
    """Dependency to require specific permission"""
    async def dependency(
        request: Request,
        current_permissions: List[Permission] = Depends(get_current_permissions)
    ):
        if permission not in current_permissions:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission required: {permission.value}"
            )
        return True
    return dependency