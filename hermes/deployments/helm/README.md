# Hermes AI Assistant Helm Chart

This Helm chart deploys the Hermes Autonomous AI Assistant on Kubernetes.

## Prerequisites

- Kubernetes 1.20+
- Helm 3.0+
- PV provisioner support in the underlying infrastructure (for persistence)

## Installing the Chart

To install the chart with the release name `hermes`:

```bash
helm repo add hermes https://charts.hermes-ai.com
helm install hermes hermes/hermes-ai-assistant
```

## Uninstalling the Chart

To uninstall/delete the `hermes` deployment:

```bash
helm delete hermes
```

## Configuration

The following table lists the configurable parameters of the Hermes chart and their default values.

| Parameter | Description | Default |
|-----------|-------------|---------|
| `image.registry` | Image registry | `docker.io` |
| `image.repository` | Image repository | `hermes-ai-assistant` |
| `image.tag` | Image tag | `1.0.0` |
| `image.pullPolicy` | Image pull policy | `IfNotPresent` |
| `replicaCount` | Number of replicas | `3` |
| `resources.limits.cpu` | CPU limit | `1000m` |
| `resources.limits.memory` | Memory limit | `2Gi` |
| `resources.requests.cpu` | CPU request | `500m` |
| `resources.requests.memory` | Memory request | `1Gi` |
| `autoscaling.enabled` | Enable autoscaling | `true` |
| `autoscaling.minReplicas` | Minimum replicas | `3` |
| `autoscaling.maxReplicas` | Maximum replicas | `10` |
| `autoscaling.targetCPUUtilizationPercentage` | Target CPU utilization | `70` |
| `ingress.enabled` | Enable ingress | `true` |
| `ingress.className` | Ingress class name | `nginx` |
| `ingress.hosts[0].host` | Ingress host | `hermes.example.com` |
| `persistence.data.enabled` | Enable data persistence | `true` |
| `persistence.data.size` | Data persistence size | `10Gi` |
| `persistence.cache.enabled` | Enable cache persistence | `true` |
| `persistence.cache.size` | Cache persistence size | `5Gi` |
| `postgresql.enabled` | Enable PostgreSQL dependency | `true` |
| `redis.enabled` | Enable Redis dependency | `true` |
| `monitoring.enabled` | Enable monitoring | `true` |
| `monitoring.prometheus.enabled` | Enable Prometheus monitoring | `true` |
| `monitoring.grafana.enabled` | Enable Grafana dashboards | `true` |

### Configuration Examples

#### Basic Installation

```bash
helm install hermes hermes/hermes-ai-assistant \
  --set secrets.hermes.secretKey="your-secret-key" \
  --set secrets.backendKeys.openaiApiKey="your-openai-key" \
  --set secrets.backendKeys.anthropicApiKey="your-anthropic-key"
```

#### Production Installation with Custom Values

Create a `values-production.yaml` file:

```yaml
replicaCount: 5
autoscaling:
  minReplicas: 5
  maxReplicas: 20
  targetCPUUtilizationPercentage: 60

ingress:
  hosts:
    - host: hermes.company.com
      paths:
        - path: /
          pathType: Prefix
  tls:
    - secretName: hermes-tls-prod
      hosts:
        - hermes.company.com

resources:
  limits:
    cpu: 2000m
    memory: 4Gi
  requests:
    cpu: 1000m
    memory: 2Gi

persistence:
  data:
    size: 50Gi
  cache:
    size: 20Gi

config:
  environment: production
  features:
    metaLearning: true
    autonomousOperations: true
    selfModification: true
    selfHealing: true

secrets:
  hermes:
    secretKey: "your-production-secret-key"
  backendKeys:
    openaiApiKey: "your-production-openai-key"
    anthropicApiKey: "your-production-anthropic-key"
    googleApiKey: "your-production-google-key"

monitoring:
  enabled: true
  prometheus:
    enabled: true
  grafana:
    enabled: true
    adminPassword: "your-grafana-password"
```

Install with custom values:

```bash
helm install hermes hermes/hermes-ai-assistant -f values-production.yaml
```

#### Development Installation

```bash
helm install hermes hermes/hermes-ai-assistant \
  --set replicaCount=1 \
  --set autoscaling.enabled=false \
  --set config.environment=development \
  --set config.debug=true \
  --set resources.requests.cpu=100m \
  --set resources.requests.memory=256Mi \
  --set persistence.data.size=1Gi \
  --set persistence.cache.size=512Mi
```

## Secrets Configuration

### Required Secrets

The following secrets are required for production deployment:

1. **Hermes Secret Key**: A random string for application security
2. **Backend API Keys**: API keys for enabled backends (OpenAI, Anthropic, Google)

### Automatic Secret Creation

Set the following values in your `values.yaml`:

```yaml
secrets:
  create: true
  hermes:
    secretKey: "your-very-secure-secret-key"
  backendKeys:
    openaiApiKey: "sk-your-openai-api-key"
    anthropicApiKey: "sk-ant-your-anthropic-api-key"
    googleApiKey: "your-google-api-key"
```

### Using Existing Secrets

If you prefer to manage secrets yourself:

```yaml
secrets:
  create: false
  existingSecrets:
    hermesSecret: "hermes-secrets"
    databaseSecret: "hermes-db-secrets"
    redisSecret: "hermes-redis-secrets"
```

## Backend Configuration

### Enable Specific Backends

```yaml
config:
  backends:
    openai:
      enabled: true
      maxTokens: 4096
      temperature: 0.7
    anthropic:
      enabled: true
      maxTokens: 4096
      temperature: 0.7
    google:
      enabled: false  # Disable Google AI
```

### Backend Configuration

Each backend can be configured with:

- `enabled`: Enable/disable the backend
- `maxTokens`: Maximum tokens for responses
- `temperature`: Response randomness (0.0-1.0)
- `timeout`: Request timeout in seconds

## Feature Flags

Control which features are enabled:

```yaml
config:
  features:
    metaLearning: true
    autonomousOperations: true
    selfModification: false  # Disable self-modification in production
    selfHealing: true
    advancedAnalytics: true
    threatDetection: true
    performanceMonitoring: true
```

## Monitoring and Observability

### Prometheus Metrics

Enable Prometheus monitoring:

```yaml
monitoring:
  enabled: true
  prometheus:
    enabled: true
    serviceMonitor:
      enabled: true
      interval: 30s
      path: /api/metrics
```

### Grafana Dashboards

Enable Grafana dashboards:

```yaml
monitoring:
  grafana:
    enabled: true
    adminPassword: "your-secure-password"
    sidecar:
      dashboards:
        enabled: true
```

## Persistence Configuration

### Storage Classes

Specify custom storage classes:

```yaml
global:
  storageClass: "fast-ssd"

persistence:
  data:
    storageClass: "fast-ssd"
    size: 50Gi
  cache:
    storageClass: "standard"
    size: 10Gi
```

### Existing Claims

Use existing persistent volume claims:

```yaml
persistence:
  data:
    enabled: true
    existingClaim: "hermes-data-pvc"
  cache:
    enabled: true
    existingClaim: "hermes-cache-pvc"
```

## Networking

### Ingress Configuration

Advanced ingress configuration:

```yaml
ingress:
  enabled: true
  className: "nginx"
  annotations:
    nginx.ingress.kubernetes.io/rewrite-target: /
    nginx.ingress.kubernetes.io/ssl-redirect: "true"
    nginx.ingress.kubernetes.io/proxy-body-size: "50m"
    nginx.ingress.kubernetes.io/rate-limit: "100"
    nginx.ingress.kubernetes.io/rate-limit-window: "1m"
    cert-manager.io/cluster-issuer: "letsencrypt-prod"
  hosts:
    - host: hermes.company.com
      paths:
        - path: /
          pathType: Prefix
  tls:
    - secretName: hermes-tls
      hosts:
        - hermes.company.com
```

### Network Policies

Enable network policies for security:

```yaml
networkPolicy:
  enabled: true
  ingress:
    enabled: true
    rules:
      - from:
          - podSelector:
              matchLabels:
                app.kubernetes.io/name: ingress-nginx
        ports:
          - protocol: TCP
            port: 8080
  egress:
    enabled: true
    rules:
      - to: []
        ports:
          - protocol: TCP
            port: 443  # HTTPS to external APIs
          - protocol: UDP
            port: 53   # DNS
          - protocol: TCP
            port: 53   # DNS
```

## Security

### Pod Security Context

```yaml
pod:
  securityContext:
    runAsNonRoot: true
    runAsUser: 1001
    runAsGroup: 1001
    fsGroup: 1001
    capabilities:
      drop:
        - ALL
```

### Resource Limits

Set appropriate resource limits:

```yaml
resources:
  limits:
    cpu: 2000m
    memory: 4Gi
  requests:
    cpu: 1000m
    memory: 2Gi
```

## Backup Configuration

Configure automated backups:

```yaml
backup:
  enabled: true
  schedule: "0 2 * * *"  # Daily at 2 AM
  retention: 30
  storage:
    type: s3
    s3:
      bucket: "hermes-backups"
      region: "us-west-2"
      accessKey: "your-access-key"
      secretKey: "your-secret-key"
      endpoint: "s3.amazonaws.com"
```

## Scaling

### Horizontal Pod Autoscaler

Configure HPA:

```yaml
autoscaling:
  enabled: true
  minReplicas: 3
  maxReplicas: 20
  targetCPUUtilizationPercentage: 70
  targetMemoryUtilizationPercentage: 80
  behavior:
    scaleDown:
      stabilizationWindowSeconds: 300
      policies:
        - type: Percent
          value: 10
          periodSeconds: 60
    scaleUp:
      stabilizationWindowSeconds: 60
      policies:
        - type: Percent
          value: 50
          periodSeconds: 60
```

### Pod Disruption Budget

Configure PDB:

```yaml
podDisruptionBudget:
  enabled: true
  minAvailable: 1
  # or
  maxUnavailable: 1
```

## Troubleshooting

### Common Issues

1. **Pods not starting**: Check resource requests and limits
2. **Database connection errors**: Verify database configuration and secrets
3. **High memory usage**: Adjust resource limits and enable caching configuration
4. **Ingress not working**: Check ingress class and annotations

### Debug Commands

```bash
# Check pod status
kubectl get pods -l app.kubernetes.io/name=hermes-ai-assistant

# Check pod logs
kubectl logs -l app.kubernetes.io/name=hermes-ai-assistant

# Describe pod
kubectl describe pod -l app.kubernetes.io/name=hermes-ai-assistant

# Check events
kubectl get events --field-selector involvedObject.name=hermes

# Port-forward for debugging
kubectl port-forward svc/hermes-ai-assistant 8080:8080
```

### Upgrading

To upgrade the deployment:

```bash
helm upgrade hermes hermes/hermes-ai-assistant -f values.yaml
```

To rollback to a previous version:

```bash
helm rollback hermes <revision>
```

## Contributing

If you'd like to contribute to the Helm chart, please:

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test the changes
5. Submit a pull request

## License

This chart is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Support

For support and questions:

- Documentation: https://docs.hermes-ai.com
- Issues: https://github.com/hermes-ai/hermes/issues
- Email: support@hermes-ai.com