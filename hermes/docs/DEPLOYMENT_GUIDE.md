# Hermes AI Assistant - Deployment Guide

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Environment Setup](#environment-setup)
3. [Local Development](#local-development)
4. [Docker Deployment](#docker-deployment)
5. [Kubernetes Deployment](#kubernetes-deployment)
6. [Configuration Management](#configuration-management)
7. [Monitoring Setup](#monitoring-setup)
8. [Security Configuration](#security-configuration)
9. [Backup and Recovery](#backup-and-recovery)
10. [Troubleshooting](#troubleshooting)

---

## Prerequisites

### System Requirements

**Minimum Requirements**:
- CPU: 2 cores
- Memory: 4GB RAM
- Storage: 20GB available
- Network: 100Mbps

**Recommended for Production**:
- CPU: 8+ cores
- Memory: 16GB+ RAM
- Storage: 100GB+ SSD
- Network: 1Gbps

### Software Dependencies

```bash
# Required
Python 3.10+
Docker 20.10+
Kubernetes 1.25+ (for K8s deployment)
Redis 7.0+
PostgreSQL 14+

# Optional for local development
Ollama (for local models)
Kubectl (for Kubernetes management)
Helm 3.0+ (for Helm deployment)
```

### API Keys Required

```bash
# Required AI model APIs
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...

# Optional but recommended
COHERE_API_KEY=...
AZURE_OPENAI_API_KEY=...
GOOGLE_PALM_API_KEY=...
```

---

## Environment Setup

### 1. Clone Repository

```bash
git clone https://github.com/your-org/hermes.git
cd hermes
```

### 2. Create Python Virtual Environment

```bash
# Create virtual environment
python3.10 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Upgrade pip
pip install --upgrade pip
```

### 3. Install Dependencies

```bash
# Install in development mode
pip install -e .

# Install development dependencies
pip install -e ".[dev]"
```

### 4. Install Local Models (Optional)

```bash
# Install Ollama for local models
curl -fsSL https://ollama.ai/install.sh | sh

# Start Ollama service
ollama serve

# Download local models
ollama pull llama3.1:8b-instruct
ollama pull qwen2.5-coder:7b
```

### 5. Start Required Services

```bash
# Start Redis
redis-server --daemonize yes

# Start PostgreSQL (if not using cloud service)
brew services start postgresql  # macOS
# or
sudo systemctl start postgresql   # Linux

# Create database
createdb hermes
```

---

## Local Development

### Configuration

Create `.env` file:

```bash
# API Keys
OPENAI_API_KEY=your_openai_key_here
ANTHROPIC_API_KEY=your_anthropic_key_here

# Database
DATABASE_URL=postgresql://localhost/hermes

# Redis
REDIS_URL=redis://localhost:6379

# Development settings
DEBUG=true
LOG_LEVEL=DEBUG
FRUGAL_ALLOW_REMOTE=1

# Optional
COHERE_API_KEY=your_cohere_key_here
AZURE_OPENAI_API_KEY=your_azure_openai_key_here
```

### Run Local Development Server

```bash
# Method 1: Direct Python
python hermes/app.py

# Method 2: Gunicorn (recommended)
gunicorn -w 4 -k uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:8000 \
  --reload \
  hermes.app:app

# Method 3: Docker Compose
docker-compose -f docker-compose.dev.yml up
```

### Verify Installation

```bash
# Health check
curl http://localhost:8000/health

# Test model endpoint
curl -X POST http://localhost:8000/api/models/completions \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Hello, how are you?",
    "task_type": "chat_completion",
    "max_tokens": 100
  }'
```

---

## Docker Deployment

### Build Docker Image

```bash
# Build standard image
docker build -t hermes:latest .

# Build with specific tag
docker build -t hermes:v1.0.0 .

# Build for production (optimized)
docker build -f Dockerfile.prod -t hermes:prod .
```

### Docker Compose (Single Node)

Create `docker-compose.yml`:

```yaml
version: '3.8'

services:
  hermes-api:
    image: hermes:latest
    ports:
      - "8000:8000"
    environment:
      - REDIS_URL=redis://redis:6379
      - DATABASE_URL=postgresql://postgres:password@postgres:5432/hermes
      - OPENAI_API_KEY=${OPENAI_API_KEY}
      - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}
    depends_on:
      - redis
      - postgres
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    command: redis-server --appendonly yes
    restart: unless-stopped

  postgres:
    image: postgres:14-alpine
    ports:
      - "5432:5432"
    environment:
      - POSTGRES_DB=hermes
      - POSTGRES_USER=postgres
      - POSTGRES_PASSWORD=password
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./scripts/init_db.sql:/docker-entrypoint-initdb.d/init.sql
    restart: unless-stopped

  prometheus:
    image: prom/prometheus:latest
    ports:
      - "9090:9090"
    volumes:
      - ./monitoring/prometheus.yml:/etc/prometheus/prometheus.yml
      - prometheus_data:/prometheus
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'
      - '--storage.tsdb.path=/prometheus'
      - '--web.console.libraries=/etc/prometheus/console_libraries'
      - '--web.console.templates=/etc/prometheus/consoles'
    restart: unless-stopped

  grafana:
    image: grafana/grafana:latest
    ports:
      - "3000:3000"
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=admin
    volumes:
      - grafana_data:/var/lib/grafana
      - ./monitoring/grafana/dashboards:/etc/grafana/provisioning/dashboards
      - ./monitoring/grafana/datasources:/etc/grafana/provisioning/datasources
    restart: unless-stopped

volumes:
  postgres_data:
  redis_data:
  prometheus_data:
  grafana_data:
```

### Deploy with Docker Compose

```bash
# Start all services
docker-compose up -d

# Check logs
docker-compose logs -f hermes-api

# Scale API service
docker-compose up -d --scale hermes-api=3

# Stop services
docker-compose down
```

### Production Dockerfile

Create `Dockerfile.prod`:

```dockerfile
# Multi-stage build for production
FROM python:3.10-slim as builder

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# Production stage
FROM python:3.10-slim

WORKDIR /app

# Install runtime dependencies
RUN apt-get update && apt-get install -y \
    postgresql-client \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --shell /bin/bash hermes

# Copy from builder
COPY --from=builder /root/.local /home/hermes/.local

# Copy application
COPY hermes/ ./hermes/
COPY frugalos/ ./frugalos/
COPY scripts/ ./scripts/

# Set permissions
RUN chown -R hermes:hermes /app

# Switch to non-root user
USER hermes

# Add Python user bin to PATH
ENV PATH=/home/hermes/.local/bin:$PATH

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Expose port
EXPOSE 8000

# Run application
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "4", "--worker-class", "uvicorn.workers.UvicornWorker", "hermes.app:app"]
```

---

## Kubernetes Deployment

### Prerequisites

```bash
# Install kubectl
curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"
sudo install -o root -g root kubectl /usr/local/bin/kubectl

# Install Helm
curl https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash
```

### Helm Chart Deployment

#### 1. Install Helm Repository

```bash
# Add Hermes Helm repository (when published)
helm repo add hermes https://charts.hermes.ai
helm repo update
```

#### 2. Create Values File

Create `values-production.yaml`:

```yaml
# Application Configuration
image:
  repository: hermes/hermes
  tag: v1.0.0
  pullPolicy: IfNotPresent

replicaCount: 3

# Resource Configuration
resources:
  requests:
    cpu: 500m
    memory: 1Gi
  limits:
    cpu: 2000m
    memory: 4Gi

# Auto-scaling
autoscaling:
  enabled: true
  minReplicas: 3
  maxReplicas: 10
  targetCPUUtilizationPercentage: 70
  targetMemoryUtilizationPercentage: 80

# Service Configuration
service:
  type: ClusterIP
  port: 8000
  targetPort: 8000

# Ingress Configuration
ingress:
  enabled: true
  className: nginx
  annotations:
    cert-manager.io/cluster-issuer: letsencrypt-prod
    nginx.ingress.kubernetes.io/rate-limit: "100"
  hosts:
    - host: hermes.yourdomain.com
      paths:
        - path: /
          pathType: Prefix
  tls:
    - secretName: hermes-tls
      hosts:
        - hermes.yourdomain.com

# Database Configuration
postgresql:
  enabled: true
  auth:
    database: hermes
    username: hermes
    password: "secure_password_here"
  primary:
    persistence:
      enabled: true
      size: 20Gi

# Redis Configuration
redis:
  enabled: true
  auth:
    enabled: true
    password: "redis_password_here"
  master:
    persistence:
      enabled: true
      size: 8Gi

# Prometheus Configuration
prometheus:
  enabled: true
  service:
    type: ClusterIP
  persistence:
    enabled: true
    size: 10Gi

# Grafana Configuration
grafana:
  enabled: true
  service:
    type: ClusterIP
  persistence:
    enabled: true
    size: 5Gi

# Secrets
secrets:
  openaiApiKey: "your_openai_key_here"
  anthropicApiKey: "your_anthropic_key_here"
  redisPassword: "redis_password_here"
  postgresPassword: "postgres_password_here"

# Environment Variables
config:
  debug: false
  logLevel: INFO
  frugalAllowRemote: true
  enableAutoScaling: true

# Monitoring
monitoring:
  prometheusEnabled: true
  grafanaEnabled: true
  metricsPort: 9090
```

#### 3. Deploy Application

```bash
# Create namespace
kubectl create namespace hermes-prod

# Install Hermes
helm install hermes hermes/hermes-ai-assistant \
  --namespace hermes-prod \
  --values values-production.yaml
```

#### 4. Verify Deployment

```bash
# Check pods
kubectl get pods -n hermes-prod

# Check services
kubectl get services -n hermes-prod

# Check ingress
kubectl get ingress -n hermes-prod

# Check logs
kubectl logs -f deployment/hermes -n hermes-prod

# Port forward for testing
kubectl port-forward svc/hermes 8000:8000 -n hermes-prod
```

### Manual Kubernetes Manifests

If not using Helm, create individual manifests:

#### 1. Namespace

```yaml
apiVersion: v1
kind: Namespace
metadata:
  name: hermes-prod
  labels:
    name: hermes-prod
```

#### 2. Secrets

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: hermes-secrets
  namespace: hermes-prod
type: Opaque
data:
  openai-api-key: <base64-encoded-key>
  anthropic-api-key: <base64-encoded-key>
  database-url: <base64-encoded-url>
  redis-url: <base64-encoded-url>
```

#### 3. ConfigMap

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: hermes-config
  namespace: hermes-prod
data:
  DEBUG: "false"
  LOG_LEVEL: "INFO"
  FRUGAL_ALLOW_REMOTE: "true"
  ENABLE_AUTO_SCALING: "true"
  PERFORMANCE_COLLECTION_INTERVAL: "60"
```

#### 4. Deployment

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: hermes-api
  namespace: hermes-prod
  labels:
    app: hermes
    component: api
spec:
  replicas: 3
  selector:
    matchLabels:
      app: hermes
      component: api
  template:
    metadata:
      labels:
        app: hermes
        component: api
    spec:
      containers:
      - name: hermes-api
        image: hermes:latest
        ports:
        - containerPort: 8000
        env:
        - name: OPENAI_API_KEY
          valueFrom:
            secretKeyRef:
              name: hermes-secrets
              key: openai-api-key
        - name: ANTHROPIC_API_KEY
          valueFrom:
            secretKeyRef:
              name: hermes-secrets
              key: anthropic-api-key
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: hermes-secrets
              key: database-url
        - name: REDIS_URL
          valueFrom:
            secretKeyRef:
              name: hermes-secrets
              key: redis-url
        envFrom:
        - configMapRef:
            name: hermes-config
        resources:
          requests:
            cpu: 500m
            memory: 1Gi
          limits:
            cpu: 2000m
            memory: 4Gi
        livenessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /ready
            port: 8000
          initialDelaySeconds: 5
          periodSeconds: 5
```

#### 5. Service

```yaml
apiVersion: v1
kind: Service
metadata:
  name: hermes-service
  namespace: hermes-prod
spec:
  selector:
    app: hermes
    component: api
  ports:
  - protocol: TCP
    port: 8000
    targetPort: 8000
  type: ClusterIP
```

#### 6. HorizontalPodAutoscaler

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: hermes-hpa
  namespace: hermes-prod
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: hermes-api
  minReplicas: 3
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: 80
  behavior:
    scaleDown:
      stabilizationWindowSeconds: 300
      policies:
      - type: Percent
        value: 10
        periodSeconds: 60
    scaleUp:
      stabilizationWindowSeconds: 0
      policies:
      - type: Percent
        value: 100
        periodSeconds: 15
      - type: Pods
        value: 4
        periodSeconds: 15
      selectPolicy: Max
```

---

## Configuration Management

### Environment-Specific Configurations

#### Development (dev.yaml)

```yaml
debug: true
logLevel: DEBUG
database:
  url: postgresql://localhost/hermes_dev
redis:
  url: redis://localhost:6379
models:
  defaultProvider: ollama
  budgetCents: 0.0
security:
  mfaRequired: false
  sessionTimeout: 3600
monitoring:
  prometheusEnabled: false
  grafanaEnabled: false
```

#### Staging (staging.yaml)

```yaml
debug: false
logLevel: INFO
database:
  url: ${DATABASE_URL}
  maxConnections: 20
redis:
  url: ${REDIS_URL}
  maxConnections: 50
models:
  defaultProvider: openai
  budgetCents: 5.0
  enableFallback: true
security:
  mfaRequired: true
  sessionTimeout: 1800
monitoring:
  prometheusEnabled: true
  grafanaEnabled: true
  alertingEnabled: true
```

#### Production (prod.yaml)

```yaml
debug: false
logLevel: WARNING
database:
  url: ${DATABASE_URL}
  maxConnections: 50
  poolSize: 20
redis:
  url: ${REDIS_URL}
  maxConnections: 100
models:
  defaultProvider: openai
  budgetCents: 10.0
  enableFallback: true
  maxRetries: 3
security:
  mfaRequired: true
  sessionTimeout: 900
  encryptionKeyRotationDays: 30
monitoring:
  prometheusEnabled: true
  grafanaEnabled: true
  alertingEnabled: true
  distributedTracingEnabled: true
```

### Secret Management

#### Kubernetes Secrets

```bash
# Create secrets from environment variables
kubectl create secret generic hermes-secrets \
  --from-literal=openai-api-key=$OPENAI_API_KEY \
  --from-literal=anthropic-api-key=$ANTHROPIC_API_KEY \
  --from-literal=database-url=$DATABASE_URL \
  --from-literal=redis-url=$REDIS_URL \
  --namespace=hermes-prod

# Create secret from file
kubectl create secret generic hermes-tls \
  --from-file=tls.crt=./certs/tls.crt \
  --from-file=tls.key=./certs/tls.key \
  --namespace=hermes-prod
```

#### External Secret Management

**AWS Secrets Manager**:
```yaml
apiVersion: v1
kind: Secret
metadata:
  name: hermes-secrets
  namespace: hermes-prod
  annotations:
    eks.amazonaws.com/role-arn: arn:aws:iam::123456789012:role/hermes-secrets-role
type: Opaque
data:
  # Will be populated by external secret operator
```

**HashiCorp Vault**:
```yaml
apiVersion: v1
kind: Secret
metadata:
  name: hermes-vault-secrets
  namespace: hermes-prod
  annotations:
    vault.hashicorp.com/agent-inject: "true"
    vault.hashicorp.com/role: hermes
    vault.hashicorp.com/template-config: |
      {{- with secret "hermes/api-keys" -}}
      openai-api-key: {{ .Data.openai_key }}
      anthropic-api-key: {{ .Data.anthropic_key }}
      {{- end }}
```

---

## Monitoring Setup

### Prometheus Configuration

Create `monitoring/prometheus.yml`:

```yaml
global:
  scrape_interval: 15s
  evaluation_interval: 15s

rule_files:
  - "hermes_rules.yml"

alerting:
  alertmanagers:
    - static_configs:
        - targets:
          - alertmanager:9093

scrape_configs:
  - job_name: 'hermes-api'
    static_configs:
      - targets: ['hermes-api:8000']
    metrics_path: /metrics
    scrape_interval: 15s

  - job_name: 'redis'
    static_configs:
      - targets: ['redis:6379']

  - job_name: 'postgres'
    static_configs:
      - targets: ['postgres:5432']

  - job_name: 'node-exporter'
    static_configs:
      - targets: ['node-exporter:9100']
```

### Alert Rules

Create `monitoring/hermes_rules.yml`:

```yaml
groups:
  - name: hermes.rules
    rules:
      - alert: HermesHighErrorRate
        expr: rate(hermes_errors_total[5m]) > 0.05
        for: 2m
        labels:
          severity: critical
        annotations:
          summary: "Hermes error rate is {{ $value | humanizePercentage }}"
          description: "Error rate has been above 5% for more than 2 minutes"

      - alert: HermesHighLatency
        expr: histogram_quantile(0.95, rate(hermes_request_duration_seconds_bucket[5m])) > 2
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Hermes P95 latency is {{ $value }}s"
          description: "95th percentile latency has been above 2s for more than 5 minutes"

      - alert: HermesLowCacheHitRate
        expr: hermes_cache_hit_rate < 0.8
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "Cache hit rate is {{ $value | humanizePercentage }}"
          description: "Cache hit rate has been below 80% for more than 10 minutes"

      - alert: HermesHighCost
        expr: rate(hermes_cost_total_cents[1h]) > 100
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Hourly cost is ${{ $value }}"
          description: "Hourly cost has exceeded $100 for more than 5 minutes"
```

### Grafana Dashboards

Create `monitoring/grafana/dashboards/hermes-overview.json`:

```json
{
  "dashboard": {
    "title": "Hermes AI Assistant Overview",
    "panels": [
      {
        "title": "Request Rate",
        "type": "graph",
        "targets": [
          {
            "expr": "rate(hermes_requests_total[5m])",
            "legendFormat": "Requests/sec"
          }
        ]
      },
      {
        "title": "Error Rate",
        "type": "stat",
        "targets": [
          {
            "expr": "rate(hermes_errors_total[5m]) / rate(hermes_requests_total[5m])",
            "legendFormat": "Error Rate"
          }
        ]
      },
      {
        "title": "P95 Latency",
        "type": "graph",
        "targets": [
          {
            "expr": "histogram_quantile(0.95, rate(hermes_request_duration_seconds_bucket[5m]))",
            "legendFormat": "P95 Latency"
          }
        ]
      },
      {
        "title": "Model Usage",
        "type": "piechart",
        "targets": [
          {
            "expr": "sum by (model_id) (hermes_model_usage_total)",
            "legendFormat": "{{model_id}}"
          }
        ]
      },
      {
        "title": "Cache Hit Rate",
        "type": "stat",
        "targets": [
          {
            "expr": "hermes_cache_hit_rate",
            "legendFormat": "Hit Rate"
          }
        ]
      },
      {
        "title": "Total Cost",
        "type": "stat",
        "targets": [
          {
            "expr": "sum(hermes_cost_total_cents)",
            "legendFormat": "Total Cost (cents)"
          }
        ]
      }
    ],
    "time": {
      "from": "now-1h",
      "to": "now"
    },
    "refresh": "30s"
  }
}
```

---

## Security Configuration

### TLS/SSL Setup

#### Ingress TLS

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: hermes-ingress
  namespace: hermes-prod
  annotations:
    kubernetes.io/ingress.class: nginx
    cert-manager.io/cluster-issuer: letsencrypt-prod
    nginx.ingress.kubernetes.io/ssl-redirect: "true"
    nginx.ingress.kubernetes.io/force-ssl-redirect: "true"
spec:
  tls:
  - hosts:
    - hermes.yourdomain.com
    secretName: hermes-tls
  rules:
  - host: hermes.yourdomain.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: hermes-service
            port:
              number: 8000
```

#### Certificate Management

```bash
# Install cert-manager
kubectl apply -f https://github.com/cert-manager/cert-manager/releases/download/v1.12.0/cert-manager.yaml

# Create ClusterIssuer
kubectl apply -f - <<EOF
apiVersion: cert-manager.io/v1
kind: ClusterIssuer
metadata:
  name: letsencrypt-prod
spec:
  acme:
    server: https://acme-v02.api.letsencrypt.org/directory
    email: admin@yourdomain.com
    privateKeySecretRef:
      name: letsencrypt-prod
    solvers:
    - http01:
        ingress:
          class: nginx
EOF
```

### Network Policies

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: hermes-network-policy
  namespace: hermes-prod
spec:
  podSelector:
    matchLabels:
      app: hermes
  policyTypes:
  - Ingress
  - Egress
  ingress:
  - from:
    - namespaceSelector:
        matchLabels:
          name: ingress-nginx
    - podSelector:
        matchLabels:
          name: prometheus
    ports:
    - protocol: TCP
      port: 8000
  egress:
  - to:
    - podSelector:
        matchLabels:
          app: redis
    - podSelector:
        matchLabels:
          app: postgres
    - to: []
    ports:
    - protocol: TCP
      port: 443  # HTTPS to external APIs
    - protocol: TCP
      port: 80   # HTTP to external APIs
```

### RBAC Configuration

```yaml
apiVersion: v1
kind: ServiceAccount
metadata:
  name: hermes-service-account
  namespace: hermes-prod
---
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: hermes-role
  namespace: hermes-prod
rules:
- apiGroups: [""]
  resources: ["configmaps", "secrets"]
  verbs: ["get", "list"]
- apiGroups: ["apps"]
  resources: ["deployments"]
  verbs: ["get", "list"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: hermes-role-binding
  namespace: hermes-prod
subjects:
- kind: ServiceAccount
  name: hermes-service-account
  namespace: hermes-prod
roleRef:
  kind: Role
  name: hermes-role
  apiGroup: rbac.authorization.k8s.io
```

---

## Backup and Recovery

### Database Backup

#### PostgreSQL Backup Script

Create `scripts/backup_postgres.sh`:

```bash
#!/bin/bash

# Configuration
BACKUP_DIR="/backups/postgres"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="hermes_backup_${TIMESTAMP}.sql"
RETENTION_DAYS=30

# Create backup directory
mkdir -p $BACKUP_DIR

# Perform backup
pg_dump -h $DATABASE_HOST -U $DATABASE_USER -d $DATABASE_NAME > $BACKUP_DIR/$BACKUP_FILE

# Compress backup
gzip $BACKUP_DIR/$BACKUP_FILE

# Remove old backups
find $BACKUP_DIR -name "*.sql.gz" -mtime +$RETENTION_DAYS -delete

echo "Backup completed: $BACKUP_FILE.gz"
```

#### Kubernetes CronJob for Backups

```yaml
apiVersion: batch/v1
kind: CronJob
metadata:
  name: postgres-backup
  namespace: hermes-prod
spec:
  schedule: "0 2 * * *"  # Daily at 2 AM
  jobTemplate:
    spec:
      template:
        spec:
          containers:
          - name: postgres-backup
            image: postgres:14-alpine
            command:
            - /bin/bash
            - -c
            - |
              pg_dump -h postgres -U postgres -d hermes | gzip > /backup/hermes-$(date +%Y%m%d_%H%M%S).sql.gz
            env:
            - name: PGPASSWORD
              valueFrom:
                secretKeyRef:
                  name: hermes-secrets
                  key: postgres-password
            volumeMounts:
            - name: backup-storage
              mountPath: /backup
          restartPolicy: OnFailure
          volumes:
          - name: backup-storage
            persistentVolumeClaim:
              claimName: backup-pvc
  successfulJobsHistoryLimit: 7
  failedJobsHistoryLimit: 3
```

### Redis Backup

```bash
#!/bin/bash

# Redis backup script
BACKUP_DIR="/backups/redis"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="redis_backup_${TIMESTAMP}.rdb"

# Create backup directory
mkdir -p $BACKUP_DIR

# Create backup
redis-cli --rdb $BACKUP_DIR/$BACKUP_FILE

# Compress backup
gzip $BACKUP_DIR/$BACKUP_FILE

echo "Redis backup completed: $BACKUP_FILE.gz"
```

### Disaster Recovery

#### Recovery Procedure

1. **Stop Services**:
```bash
kubectl scale deployment hermes-api --replicas=0 -n hermes-prod
```

2. **Restore Database**:
```bash
# Download backup
kubectl get pods -n hermes-prod
kubectl cp backup-pod:/backup/latest_backup.sql.gz ./

# Extract backup
gunzip latest_backup.sql.gz

# Restore database
kubectl exec -it postgres-0 -n hermes-prod -- psql -U postgres -d hermes < latest_backup.sql
```

3. **Restore Redis**:
```bash
# Stop Redis
kubectl delete pod redis-0 -n hermes-prod

# Copy backup to Redis volume
kubectl cp redis_backup.rdb redis-pod:/data/dump.rdb -n hermes-prod

# Start Redis with restored data
kubectl apply -f redis-deployment.yaml -n hermes-prod
```

4. **Restart Services**:
```bash
kubectl scale deployment hermes-api --replicas=3 -n hermes-prod
```

5. **Verify Recovery**:
```bash
kubectl get pods -n hermes-prod
kubectl logs -f deployment/hermes-api -n hermes-prod
curl http://hermes.yourdomain.com/health
```

---

## Troubleshooting

### Common Issues

#### 1. High Memory Usage

**Symptoms**:
- Pods being evicted
- High memory usage in metrics

**Solutions**:
```bash
# Check pod memory usage
kubectl top pods -n hermes-prod

# Check memory limits
kubectl describe pod <pod-name> -n hermes-prod

# Adjust resource limits
kubectl patch deployment hermes-api -p '{"spec":{"template":{"spec":{"containers":[{"name":"hermes-api","resources":{"limits":{"memory":"6Gi"}}}]}}}}' -n hermes-prod
```

#### 2. Database Connection Issues

**Symptoms**:
- Connection timeouts
- Database errors in logs

**Solutions**:
```bash
# Check database connectivity
kubectl exec -it postgres-0 -n hermes-prod -- psql -U postgres -d hermes -c "SELECT 1;"

# Check connection pool settings
kubectl logs deployment/hermes-api -n hermes-prod | grep -i "database"

# Increase database connections
kubectl patch configmap hermes-config -p '{"data":{"DATABASE_MAX_CONNECTIONS":"50"}}' -n hermes-prod
```

#### 3. High Latency

**Symptoms**:
- Slow API responses
- High P95 latency metrics

**Solutions**:
```bash
# Check pod resource usage
kubectl top pods -n hermes-prod

# Check autoscaler status
kubectl get hpa -n hermes-prod
kubectl describe hpa hermes-hpa -n hermes-prod

# Scale up manually if needed
kubectl scale deployment hermes-api --replicas=5 -n hermes-prod
```

#### 4. Cache Issues

**Symptoms**:
- Low cache hit rate
- Redis connection errors

**Solutions**:
```bash
# Check Redis status
kubectl exec -it redis-0 -n hermes-prod -- redis-cli ping

# Check Redis memory usage
kubectl exec -it redis-0 -n hermes-prod -- redis-cli info memory

# Clear cache if needed
kubectl exec -it redis-0 -n hermes-prod -- redis-cli FLUSHALL
```

### Debug Commands

#### Pod Diagnostics

```bash
# Get pod events
kubectl describe pod <pod-name> -n hermes-prod

# Get pod logs
kubectl logs <pod-name> -n hermes-prod --tail=100

# Get pod resource usage
kubectl top pod <pod-name> -n hermes-prod

# Exec into pod for debugging
kubectl exec -it <pod-name> -n hermes-prod -- /bin/bash
```

#### Service Diagnostics

```bash
# Check service endpoints
kubectl get endpoints hermes-service -n hermes-prod

# Test service connectivity
kubectl run test-pod --image=curlimages/curl -it --rm -- /bin/sh
curl http://hermes-service.hermes-prod.svc.cluster.local:8000/health
```

#### Network Diagnostics

```bash
# Check network policies
kubectl get networkpolicy -n hermes-prod

# Test connectivity between pods
kubectl exec -it <source-pod> -n hermes-prod -- ping <target-pod-ip>

# Check DNS resolution
kubectl exec -it <pod-name> -n hermes-prod -- nslookup hermes-service.hermes-prod.svc.cluster.local
```

### Health Checks

#### Application Health

```bash
# Kubernetes health check
kubectl get pods -n hermes-prod

# Application health endpoint
curl http://hermes.yourdomain.com/health

# Detailed health check
curl http://hermes.yourdomain.com/api/optimization/health
curl http://hermes.yourdomain.com/api/models/health
```

#### Database Health

```bash
# PostgreSQL health
kubectl exec -it postgres-0 -n hermes-prod -- pg_isready

# Redis health
kubectl exec -it redis-0 -n hermes-prod -- redis-cli ping

# Check database connections
kubectl exec -it postgres-0 -n hermes-prod -- psql -U postgres -d hermes -c "SELECT count(*) FROM pg_stat_activity;"
```

---

## Conclusion

This deployment guide provides comprehensive instructions for deploying the Hermes AI Assistant platform in various environments:

✅ **Local Development**: Quick setup for development and testing
✅ **Docker Deployment**: Containerized deployment for consistency
✅ **Kubernetes Deployment**: Production-grade orchestration
✅ **Configuration Management**: Environment-specific configurations
✅ **Monitoring Setup**: Comprehensive observability
✅ **Security Configuration**: Enterprise-grade security
✅ **Backup and Recovery**: Disaster recovery procedures
✅ **Troubleshooting**: Common issues and solutions

The platform is **production-ready** and can be deployed at scale with confidence. Follow the monitoring dashboards and health checks to ensure optimal performance.

For additional support, refer to the [Architecture Overview](ARCHITECTURE_OVERVIEW.md) and [Complete Guide](HERMES_COMPLETE_GUIDE.md).