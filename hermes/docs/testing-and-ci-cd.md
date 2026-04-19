# Testing and CI/CD Pipeline

This document describes the comprehensive testing strategy and CI/CD pipeline implemented for the Hermes AI Assistant system.

## Overview

The testing and CI/CD pipeline provides:

- **Multi-tier testing** with unit, integration, performance, and E2E tests
- **Automated quality checks** including linting, type checking, and security scanning
- **CI/CD automation** with GitHub Actions
- **Docker containerization** with multi-architecture support
- **Kubernetes deployment** with Helm charts and blue-green strategy
- **Continuous monitoring** with artifact collection and reporting

## Testing Strategy

### Test Pyramid

#### 1. Unit Tests
- **Coverage**: 90%+ code coverage target
- **Scope**: Individual modules and functions
- **Tools**: pytest, pytest-cov, pytest-asyncio
- **Location**: `tests/unit/`

```python
# Example unit test
import pytest
from hermes.security.auth_service import AuthenticationService

@pytest.mark.asyncio
async def test_user_creation(auth_service):
    user = await auth_service.create_user(
        username="testuser",
        email="test@example.com",
        password="testpassword123",
        role="basic_user"
    )
    assert user.username == "testuser"
    assert user.is_active is True
```

#### 2. Integration Tests
- **Coverage**: Component interactions and API endpoints
- **Scope**: Database integration, Redis operations, authentication flows
- **Tools**: pytest, httpx, testcontainers
- **Location**: `tests/integration/`

```python
# Example integration test
import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_authentication_flow(async_client, auth_service):
    # Create user
    user = await auth_service.create_user(
        username="integration_user",
        email="integration@example.com",
        password="password123",
        role="basic_user"
    )

    # Test login
    response = await async_client.post("/api/v1/auth/login", json={
        "username": "integration_user",
        "password": "password123"
    })
    assert response.status_code == 200
    assert "access_token" in response.json()
```

#### 3. Performance Tests
- **Coverage**: Load testing, stress testing, performance benchmarks
- **Tools**: Locust, Artillery
- **Metrics**: Response time, throughput, error rates
- **Location**: `tests/performance/`

```python
# Example Locust test
from locust import HttpUser, task, between

class HermesUser(HttpUser):
    @task
    def chat_completion(self):
        self.client.post("/api/v1/chat", json={
            "message": "Hello, how are you?",
            "model": "gpt-3.5-turbo"
        })

    @task(3)
    def health_check(self):
        self.client.get("/health")
```

#### 4. End-to-End Tests
- **Coverage**: Complete user workflows and system integration
- **Tools**: Playwright, Selenium
- **Environment**: Staging and production
- **Location**: `tests/e2e/`

### Test Configuration

#### Test Fixtures (`tests/conftest.py`)
```python
@pytest.fixture
async def auth_service(redis_client):
    service = AuthenticationService(redis_url="redis://localhost:6379/15")
    await service.initialize()
    return service

@pytest.fixture
async def encryption_service():
    service = EncryptionService()
    await service.initialize()
    return service

@pytest.fixture
async def compliance_manager(temp_dir):
    return ComplianceManager(storage_path=str(temp_dir / "compliance"))
```

#### Test Data Management
- **Factory Pattern**: For generating test data
- **Database Cleanup**: Automatic cleanup between tests
- **Mock Services**: For external dependencies

## CI/CD Pipeline

### GitHub Actions Workflow

#### Pipeline Triggers
- **Push**: All branches (`main`, `develop`, `feature/*`, `release/*`)
- **Pull Request**: `main`, `develop` branches
- **Release**: Published releases

#### Pipeline Stages

##### 1. Code Quality and Security
```yaml
code-quality:
  runs-on: ubuntu-latest
  steps:
    - name: Checkout code
      uses: actions/checkout@v4

    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: "3.11"

    - name: Lint with flake8
      run: |
        flake8 hermes --count --select=E9,F63,F7,F82 --show-source --statistics
        flake8 hermes --count --exit-zero --max-complexity=10 --max-line-length=127 --statistics

    - name: Type checking with mypy
      run: |
        mypy hermes --ignore-missing-imports --no-strict-optional

    - name: Security scan with bandit
      run: |
        bandit -r hermes -f json -o bandit-report.json
        bandit -r hermes
```

##### 2. Unit Tests
```yaml
unit-tests:
  runs-on: ubuntu-latest
  strategy:
    matrix:
      python-version: ["3.9", "3.10", "3.11"]

  steps:
    - name: Run unit tests
      run: |
        pytest tests/unit/ -v --cov=hermes --cov-report=xml --cov-report=html --junitxml=junit.xml

    - name: Upload coverage to Codecov
      uses: codecov/codecov-action@v3
      with:
        file: ./coverage.xml
        flags: unittests
        name: codecov-umbrella
```

##### 3. Integration Tests
```yaml
integration-tests:
  runs-on: ubuntu-latest
  needs: [code-quality, unit-tests]

  services:
    postgres:
      image: postgres:15
      env:
        POSTGRES_PASSWORD: postgres
        POSTGRES_DB: hermes_test

    redis:
      image: redis:7
      options: >-
        --health-cmd "redis-cli ping"
        --health-interval 10s
        --health-timeout 5s
        --health-retries 5

  steps:
    - name: Run integration tests
      env:
        DATABASE_URL: postgresql://postgres:postgres@localhost:5432/hermes_test
        REDIS_URL: redis://localhost:6379/15
        TESTING: true
      run: |
        pytest tests/integration/ -v --junitxml=integration-junit.xml
```

##### 4. Security Scanning
```yaml
security-scan:
  runs-on: ubuntu-latest
  needs: [code-quality]

  steps:
    - name: Run Trivy vulnerability scanner
      uses: aquasecurity/trivy-action@master
      with:
        scan-type: 'fs'
        scan-ref: '.'
        format: 'sarif'
        output: 'trivy-results.sarif'

    - name: Upload Trivy scan results to GitHub Security tab
      uses: github/codeql-action/upload-sarif@v2
      with:
        sarif_file: 'trivy-results.sarif'
```

##### 5. Build and Push Docker Image
```yaml
build-and-push:
  runs-on: ubuntu-latest
  needs: [unit-tests, integration-tests]
  if: github.event_name != 'pull_request'

  steps:
    - name: Set up Docker Buildx
      uses: docker/setup-buildx-action@v3

    - name: Log in to Container Registry
      uses: docker/login-action@v3
      with:
        registry: ghcr.io
        username: ${{ github.actor }}
        password: ${{ secrets.GITHUB_TOKEN }}

    - name: Build and push Docker image
      uses: docker/build-push-action@v5
      with:
        context: .
        platforms: linux/amd64,linux/arm64
        push: true
        tags: |
          type=ref,event=branch
          type=semver,pattern={{version}}
          type=sha
        cache-from: type=gha
        cache-to: type=gha,mode=max
```

##### 6. Deploy to Staging
```yaml
deploy-staging:
  runs-on: ubuntu-latest
  needs: [build-and-push, performance-tests]
  if: github.ref == 'refs/heads/develop'
  environment: staging

  steps:
    - name: Deploy to staging
      run: |
        helm upgrade --install hermes-staging ./deployments/helm \
          --namespace hermes-staging \
          --create-namespace \
          --set image.tag=${{ needs.build-and-push.outputs.image-tag }} \
          --set environment=staging \
          --values ./deployments/environments/staging.yaml

    - name: Run smoke tests
      run: |
        pytest tests/smoke/ --base-url=https://staging.hermes-ai.com -v
```

##### 7. Deploy to Production (Blue-Green)
```yaml
deploy-production:
  runs-on: ubuntu-latest
  needs: [build-and-push, deploy-staging]
  if: github.event_name == 'release'
  environment: production

  steps:
    - name: Deploy to production (blue-green)
      run: |
        # Deploy to green environment first
        helm upgrade --install hermes-green ./deployments/helm \
          --namespace hermes-prod \
          --set image.tag=${{ needs.build-and-push.outputs.image-tag }} \
          --set environment=production \
          --set deployment.color=green \
          --values ./deployments/environments/production.yaml

        # Wait for green deployment to be ready
        kubectl rollout status deployment/hermes-green -n hermes-prod

        # Run health checks on green
        kubectl wait --for=condition=ready pod -l app=hermes,color=green -n hermes-prod --timeout=300s

        # Switch traffic to green
        kubectl patch service hermes-prod -n hermes-prod -p '{"spec":{"selector":{"color":"green"}}}'

        # Clean up blue deployment
        helm uninstall hermes-blue -n hermes-prod || true
```

### Deployment Strategies

#### Blue-Green Deployment
- **Zero Downtime**: Traffic switching without service interruption
- **Rollback Capability**: Instant rollback if issues detected
- **Health Checks**: Comprehensive validation before traffic switch
- **Environment Isolation**: Separate staging and production environments

#### Helm Chart Configuration
- **Template-driven**: Kubernetes manifests as templates
- **Environment-specific**: Different values for staging/production
- **Dependency Management**: Automatic installation of dependencies
- **Rolling Updates**: Gradual rollout with health checks

## Quality Assurance

### Code Quality Metrics

#### Coverage Requirements
- **Unit Test Coverage**: 90% minimum
- **Integration Test Coverage**: 80% minimum
- **Overall Coverage**: 85% minimum

#### Code Quality Standards
- **Linting**: flake8 with strict rules
- **Type Checking**: mypy with strict mode
- **Complexity**: Maximum cyclomatic complexity of 10
- **Documentation**: All public functions and classes documented

#### Security Standards
- **Static Analysis**: Bandit security scanning
- **Dependency Scanning**: Safety vulnerability checking
- **Container Security**: Trivy vulnerability scanning
- **CodeQL Analysis**: GitHub Advanced Security

### Performance Benchmarks

#### Response Time Targets
- **API Endpoints**: < 200ms (95th percentile)
- **Authentication**: < 500ms
- **File Upload**: < 2s (10MB file)
- **Complex Queries**: < 5s

#### Throughput Targets
- **Concurrent Users**: 1000 simultaneous users
- **Requests per Second**: 1000 RPS
- **File Uploads**: 100 concurrent uploads
- **Database Operations**: 5000 TPS

### Reliability Requirements

#### Uptime Targets
- **Production**: 99.9% uptime
- **Staging**: 99.5% uptime
- **API Availability**: 99.95% uptime

#### Error Rate Targets
- **4xx Errors**: < 1% of total requests
- **5xx Errors**: < 0.1% of total requests
- **Timeout Errors**: < 0.5% of total requests

## Monitoring and Reporting

### Test Reporting

#### Coverage Reports
- **HTML Reports**: Detailed coverage visualization
- **XML Reports**: CI/CD integration
- **Codecov Integration**: Coverage tracking over time

#### Test Results
- **JUnit XML**: Test result format for CI/CD
- **HTML Reports**: Human-readable test reports
- **Performance Reports**: Load testing visualization
- **Security Reports**: Vulnerability scan results

### Artifact Management
- **Test Reports**: Automated collection and storage
- **Coverage Data**: Historical tracking
- **Performance Metrics**: Baseline and trend analysis
- **Security Scan Results**: Vulnerability tracking

## Testing Best Practices

### Test Organization
```
tests/
├── unit/                    # Unit tests
│   ├── test_auth_service.py
│   ├── test_encryption.py
│   ├── test_compliance.py
│   └── test_rate_limiter.py
├── integration/            # Integration tests
│   ├── test_api_endpoints.py
│   ├── test_database.py
│   └── test_middleware.py
├── performance/           # Performance tests
│   ├── locustfile.py
│   ├── artillery-config.yml
│   └── benchmarks/
├── e2e/                   # End-to-end tests
│   ├── test_user_workflows.py
│   ├── test_admin_features.py
│   └── test_api_integration.py
├── security/              # Security tests
│   ├── test_authentication.py
│   ├── test_authorization.py
│   └── test_data_protection.py
├── smoke/                 # Smoke tests
│   └── test_basic_functionality.py
└── fixtures/              # Test fixtures and utilities
    ├── conftest.py
    ├── factories.py
    └── helpers.py
```

### Test Data Management
- **Factory Pattern**: Consistent test data generation
- **Database Transactions**: Rollback after each test
- **Isolation**: Tests don't interfere with each other
- **Cleanup**: Automatic cleanup of test resources

### Mocking Strategies
- **External Services**: Mock OpenAI, AWS, etc.
- **Time and Dates**: Consistent test time handling
- **Random Data**: Controlled randomness for reproducibility
- **Network Requests**: Mock HTTP calls and responses

### Environment Configuration
- **Test Environment**: Isolated test database and Redis
- **Configuration Management**: Environment-specific settings
- **Secret Management**: Secure handling of test credentials
- **Service Dependencies**: Testcontainers for external services

## Troubleshooting

### Common Test Issues

#### 1. Test Failures in CI
```bash
# Debug failing tests locally
pytest tests/unit/test_auth_service.py::test_user_creation -v -s

# Check test dependencies
pip list | grep -E "(pytest|test-)"

# Verify test environment
python -c "import hermes; print('Import successful')"
```

#### 2. Integration Test Issues
```bash
# Check database connectivity
psql $DATABASE_URL -c "SELECT 1"

# Verify Redis connection
redis-cli -u $REDIS_URL ping

# Check service health
curl -f http://localhost:8000/health
```

#### 3. Performance Test Issues
```bash
# Run performance tests locally
locust -f tests/performance/locustfile.py --headless -u 10 -t 30s --host=http://localhost:8000

# Monitor system resources
htop
docker stats
```

#### 4. Docker Build Issues
```bash
# Check Dockerfile syntax
docker build -t test-build .

# Debug build failures
docker build --progress=plain -t test-build .

# Verify multi-platform build
docker buildx build --platform linux/amd64,linux/arm64 -t test-build .
```

### CI/CD Pipeline Debugging

#### GitHub Actions Logs
```yaml
# Enable debug logging
- name: Debug information
  run: |
    echo "Python version: $(python --version)"
    echo "Docker version: $(docker --version)"
    echo "kubectl version: $(kubectl version --client)"
    echo "Helm version: $(helm version)"
```

#### Artifact Collection
```yaml
# Upload debug artifacts
- name: Upload debug information
  uses: actions/upload-artifact@v3
  if: always()
  with:
    name: debug-info
    path: |
      .env
      docker-compose.yml
      kubectl-config
```

#### Rollback Procedures
```bash
# Manual rollback if CI/CD fails
helm rollback hermes-green -n hermes-prod

# Restore previous deployment
kubectl apply -f deployments/kubernetes/backup.yaml

# Verify rollback
kubectl get pods -n hermes-prod
```

## Future Enhancements

### Testing Improvements
1. **Visual Testing**: Automated UI testing with screenshot comparison
2. **Contract Testing**: API contract validation with Pact
3. **Chaos Engineering**: Fault injection testing for resilience
4. **Canary Deployments: Gradual production rollouts

### CI/CD Enhancements
1. **Multi-Environment**: Support for multiple staging environments
2. **Automated Scaling**: Dynamic resource allocation based on test load
3. **Test Parallelization**: Parallel test execution for faster feedback
4. **Smart Dependencies**: Pipeline optimization with intelligent dependency analysis

### Monitoring Improvements
1. **Real-time Metrics**: Live test execution monitoring
2. **Anomaly Detection**: Automatic identification of performance regressions
3. **Predictive Analytics**: ML-based test failure prediction
4. **Alerting Integration**: Enhanced notification and escalation systems