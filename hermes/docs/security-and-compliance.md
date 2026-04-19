# Security and Compliance Framework

This document describes the comprehensive security and compliance framework implemented for the Hermes AI Assistant system.

## Overview

The security framework provides:

- **Multi-factor authentication** with TOTP, SMS, and email support
- **Role-based access control** with granular permissions
- **Advanced encryption** including AES-256-GCM and field-level encryption
- **Compliance management** for GDPR, SOC 2, HIPAA, and PCI DSS
- **Comprehensive audit logging** with tamper-evident storage
- **Security middleware** for FastAPI applications
- **Threat detection** and anomaly monitoring

## Architecture

### Core Components

1. **Authentication Service** (`security/auth_service.py`)
   - Multi-method authentication (password, API key, JWT, OAuth2, SAML, LDAP)
   - Multi-factor authentication with TOTP support
   - Session management with secure tokens
   - API key management with rotation capabilities

2. **Encryption Service** (`security/encryption.py`)
   - AES-256-GCM encryption for data at rest
   - RSA encryption for key exchange
   - Field-level encryption for sensitive data
   - Key management with automatic rotation

3. **Compliance Manager** (`security/compliance.py`)
   - GDPR, SOC 2, HIPAA, PCI DSS compliance support
   - Comprehensive audit logging
   - Data subject request processing
   - Automated compliance reporting

4. **Security Middleware** (`security/middleware.py`)
   - Authentication and authorization middleware
   - Security headers enforcement
   - CSRF protection
   - IP whitelisting
   - Audit logging integration

## Authentication and Authorization

### Authentication Methods

#### Password Authentication
```python
result = await auth_service.authenticate(
    AuthMethod.PASSWORD,
    {
        "username": "user@example.com",
        "password": "secure_password"
    },
    ip_address="192.168.1.100",
    user_agent="Mozilla/5.0..."
)
```

#### API Key Authentication
```python
result = await auth_service.authenticate(
    AuthMethod.API_KEY,
    {
        "api_key": "hk_abcdef123456789"
    }
)
```

#### JWT Authentication
```python
result = await auth_service.authenticate(
    AuthMethod.JWT,
    {
        "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
    }
)
```

#### Multi-Factor Authentication
```python
# Enable MFA for user
secret, qr_code = await auth_service.enable_mfa(user_id)

# Verify MFA code
result = await auth_service.authenticate(
    AuthMethod.MFA,
    {
        "mfa_token": "temp_token_123",
        "mfa_code": "123456"
    }
)
```

### User Roles and Permissions

#### Role Hierarchy
- **Admin**: Full system access
- **Enterprise Admin**: Organization management
- **Premium User**: Advanced features and API access
- **Basic User**: Standard features
- **Anonymous**: Public access only
- **Service Account**: System integration

#### Permission System
```python
# Check user permission
has_permission = await auth_service.check_permission(
    user_id="user123",
    permission=Permission.MANAGE_USERS
)

# Get user permissions
permissions = await auth_service.get_user_permissions(user_id="user123")
```

#### API Key Management
```python
# Create API key
key_id, api_key = await auth_service.create_api_key(
    user_id="user123",
    name="Production API Key",
    permissions=[Permission.READ, Permission.WRITE],
    expires_in_days=365
)

# Revoke API key
success = await auth_service.revoke_api_key(key_id, user_id="user123")
```

## Encryption and Data Protection

### Data Encryption

#### Symmetric Encryption (AES-256-GCM)
```python
from hermes.security import encryption_service

# Encrypt data
encrypted = await encryption_service.encrypt(
    data="sensitive_information",
    key_id="master-key-001"
)

# Decrypt data
decrypted = await encryption_service.decrypt(encrypted)
```

#### Field-Level Encryption
```python
# Encrypt specific fields in JSON
sensitive_fields = ["email", "phone", "ssn"]
encrypted_json = await encryption_service.encrypt_json(
    data=user_data,
    sensitive_fields=sensitive_fields
)

# Decrypt fields
decrypted_json = await encryption_service.decrypt_json(encrypted_json)
```

#### Key Management
```python
# Generate new encryption key
key_id, key_material = await encryption_service.generate_key(
    key_type=KeyType.DATA_ENCRYPTION,
    algorithm=EncryptionType.AES_256_GCM,
    expires_in_days=90
)

# Rotate keys
rotation_results = await encryption_service.rotate_keys()
```

### Security Features

- **Automatic Key Rotation**: Every 90 days
- **Envelope Encryption**: Master key + data keys
- **Secure Key Storage**: In-memory with Redis backup
- **Perfect Forward Secrecy**: Ephemeral keys for sessions

## Compliance Management

### Supported Frameworks

#### GDPR Compliance
```python
# Create data subject request
request = await compliance_manager.create_data_subject_request(
    subject_id="user@example.com",
    request_type="access"  # access, deletion, correction, portability
)

# Process request
await compliance_manager.process_data_subject_request(
    request_id=request.request_id,
    processed_by="admin_user",
    result={"data_export": "export_file.zip"}
)
```

#### Audit Logging
```python
# Log audit event
await compliance_manager.log_audit_event(
    event_type=AuditEventType.DATA_ACCESS,
    user_id="user123",
    ip_address="192.168.1.100",
    resource_id="document_456",
    action="read",
    result="success",
    compliance_frameworks=[ComplianceFramework.GDPR, ComplianceFramework.SOC2],
    data_classification=DataClassification.CONFIDENTIAL
)
```

#### Compliance Reporting
```python
# Generate compliance report
report = await compliance_manager.generate_compliance_report(
    framework=ComplianceFramework.GDPR,
    start_date=datetime.now() - timedelta(days=30),
    end_date=datetime.now()
)
```

### Data Classification

| Classification | Retention | Encryption | Audit Access |
|---------------|-----------|------------|--------------|
| Public | Permanent | Optional | No |
| Internal | 7 years | Required | Yes |
| Confidential | 7 years | Required | Yes |
| Restricted | 7 years | Required | Yes |

### Automated Compliance Rules

- **Data Minimization**: Collect only necessary data
- **Encryption Requirements**: Encrypt sensitive data by default
- **Access Logging**: Log all access to sensitive resources
- **Retention Policies**: Automatic data cleanup based on retention periods

## Security Middleware Integration

### FastAPI Integration
```python
from fastapi import FastAPI
from hermes.security import init_security_middleware
from hermes.security.auth_service import initialize_auth_service
from hermes.security.encryption import initialize_encryption_service
from hermes.security.compliance import initialize_compliance_manager

app = FastAPI()

# Initialize security services
auth_service = await initialize_auth_service(redis_url="redis://localhost:6379")
encryption_service = await initialize_encryption_service()
compliance_manager = await initialize_compliance_manager()

# Add security middleware
await init_security_middleware(
    app=app,
    auth_service=auth_service,
    encryption_service=encryption_service,
    compliance_manager=compliance_manager
)
```

### Security Features

#### Security Headers
- **Strict-Transport-Security**: HSTS with preload
- **Content-Type-Options**: Prevent MIME sniffing
- **Frame-Options**: Clickjacking protection
- **XSS-Protection**: Browser XSS filter
- **Content-Security-Policy**: Comprehensive CSP policy

#### Authentication Middleware
- **Multi-method support**: JWT, API keys, OAuth2
- **Session management**: Secure session tokens
- **Automatic MFA**: When required by role
- **IP tracking**: For audit and security

#### Authorization Middleware
- **Role-based access control**: Granular permissions
- **Resource-level permissions**: Fine-grained control
- **Admin path protection**: IP whitelisting
- **API endpoint security**: Method-based permissions

#### Audit Logging
- **Comprehensive logging**: All access and modifications
- **Compliance integration**: GDPR, SOC 2, HIPAA
- **Tamper evidence**: Cryptographic signatures
- **Long-term storage**: Multi-year retention

## Configuration

### Security Configuration
The system is configured via `config/security_config.yaml`:

```yaml
global:
  security_level: "high"
  session_timeout_minutes: 60
  max_login_attempts: 5
  lockout_duration_minutes: 15

authentication:
  methods:
    - type: "password"
      enabled: true
      mfa_required: false
    - type: "api_key"
      enabled: true
    - type: "jwt"
      enabled: true
      expiration_hours: 24

encryption:
  default_algorithm: "aes_256_gcm"
  key_rotation_days: 90
  data_at_rest:
    enabled: true
    algorithm: "aes_256_gcm"

compliance:
  frameworks:
    - name: "gdpr"
      enabled: true
      data_retention_days: 365
    - name: "soc2"
      enabled: true
      audit_logging: true
```

### Environment Variables
- `REDIS_URL`: Redis connection for sessions and caching
- `JWT_SECRET`: Secret for JWT token signing
- `ENCRYPTION_KEY`: Master encryption key (or generate automatically)
- `GOOGLE_CLIENT_ID`: OAuth2 Google client ID
- `MICROSOFT_CLIENT_ID`: OAuth2 Microsoft client ID

## Security Best Practices

### Password Security
- **Minimum 12 characters** with complexity requirements
- **Password history**: Prevent reuse of last 5 passwords
- **Age limits**: 90-day maximum age
- **Breach checking**: Verify against known breached passwords

### Session Security
- **Secure cookies**: HttpOnly, Secure, SameSite=Strict
- **Session timeout**: 60 minutes inactivity, 24 hours absolute
- **Concurrent sessions**: Maximum 3 per user
- **Secure storage**: Redis with encryption

### API Security
- **Rate limiting**: Tier-based rate limiting
- **API keys**: Rotatable, expirable, scoped permissions
- **CORS protection**: Configurable allowed origins
- **Request validation**: Size limits, content validation

### Network Security
- **IP whitelisting**: Admin access restrictions
- **DDoS protection**: Automatic detection and mitigation
- **TLS enforcement**: HTTPS-only for production
- **Certificate management**: Automatic renewal

## Monitoring and Alerting

### Security Metrics
- **Authentication events**: Successes, failures, MFA usage
- **Authorization events**: Permission denials, role changes
- **Encryption operations**: Key rotations, data encryption/decryption
- **Compliance violations**: Rule violations, remediation status

### Anomaly Detection
- **Unusual access patterns**: Time, location, frequency
- **Privilege escalation**: Unexpected permission changes
- **Data access anomalies**: Large data exports, unusual patterns
- **System anomalies**: Error rates, performance issues

### Alerting
- **Security events**: Immediate notification for critical events
- **Compliance violations**: Automated alerts for rule breaches
- **System health**: Monitoring for security service availability
- **Performance alerts**: Response time and throughput monitoring

## Testing and Validation

### Security Testing
- **Penetration testing**: Quarterly external assessments
- **Vulnerability scanning**: Weekly automated scans
- **Code review**: Security-focused code review process
- **Dependency scanning**: Automated vulnerability checking

### Compliance Validation
- **Automated checks**: Continuous compliance monitoring
- **Manual audits**: Annual compliance assessments
- **Documentation**: Comprehensive compliance documentation
- **Remediation**: Systematic violation remediation

## Deployment Considerations

### Production Deployment
- **High security level**: Maximum security controls
- **Enhanced monitoring**: Comprehensive security monitoring
- **Strict compliance**: Full compliance enforcement
- **Redundancy**: High availability for security services

### Staging Environment
- **Production-like setup**: Mirror production security
- **Testing credentials**: Separate test credentials
- **Reduced monitoring**: Appropriate for staging
- **Compliance testing**: Validate compliance features

### Development Environment
- **Relaxed security**: Easier development workflow
- **Mock authentication**: Simplified auth for testing
- **Debug mode**: Enhanced logging and debugging
- **Security warnings**: Reminders about security differences

## Troubleshooting

### Common Issues

1. **Authentication Failures**
   - Check credentials and account status
   - Verify MFA configuration
   - Review account lockout status

2. **Permission Errors**
   - Verify user role and permissions
   - Check resource-specific permissions
   - Review role assignments

3. **Encryption Issues**
   - Verify key availability and rotation status
   - Check encryption algorithm compatibility
   - Review key management configuration

4. **Compliance Violations**
   - Review violation details and recommendations
   - Check configuration for rule compliance
   - Validate data handling procedures

### Debug Mode
Enable security debug logging:
```python
import logging
logging.getLogger("hermes.security").setLevel(logging.DEBUG)
```

### Health Checks
```bash
# Check security service status
curl http://localhost:8000/health

# Check authentication status
curl -H "Authorization: Bearer <token>" http://localhost:8000/api/v1/auth/status

# Check compliance status
curl -H "X-API-Key: <key>" http://localhost:8000/api/v1/compliance/status
```

## Future Enhancements

1. **Advanced Threat Detection**
   - Machine learning-based anomaly detection
   - Behavioral analysis and user profiling
   - Real-time threat intelligence integration

2. **Enhanced Encryption**
   - Homomorphic encryption for computations
   - Quantum-resistant encryption algorithms
   - Hardware security module (HSM) integration

3. **Advanced Compliance**
   - Automated compliance reporting
   - Real-time compliance monitoring
   - Integration with compliance management platforms

4. **Zero Trust Architecture**
   - Continuous authentication and authorization
   - Micro-segmentation and least privilege
   - Advanced identity and access management