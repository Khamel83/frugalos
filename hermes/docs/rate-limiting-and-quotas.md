# API Rate Limiting and Quota Management

This document describes the comprehensive rate limiting and quota management system implemented for the Hermes AI Assistant.

## Overview

The rate limiting and quota management system provides:

- **Multi-tier rate limiting** with different limits for anonymous, basic, premium, and enterprise users
- **Advanced quota management** with automatic adjustments and fair sharing
- **Burst handling** with token bucket algorithm
- **Real-time monitoring** and alerting
- **Flexible configuration** via YAML files
- **Redis-based distributed** rate limiting for scalability
- **FastAPI integration** with middleware components

## Architecture

### Core Components

1. **RateLimiter** (`middleware/rate_limiter.py`)
   - Sliding window counters for accurate rate limiting
   - Token bucket algorithm for burst handling
   - Redis backend for distributed deployment
   - Automatic penalty system for abuse prevention

2. **QuotaManager** (`middleware/quota_manager.py`)
   - Dynamic quota allocation based on usage patterns
   - Fair share algorithms for resource distribution
   - Automatic quota adjustments with configurable rules
   - Support for multiple quota types (tokens, requests, etc.)

3. **RateLimitMiddleware** (`middleware/rate_limit_integration.py`)
   - FastAPI middleware for automatic rate limiting
   - Client identification and tier determination
   - Request/response header management
   - Integration with monitoring systems

## Rate Limiting Features

### Rate Limit Types

- **Requests per minute/hour/day**: Traditional request-based limiting
- **Tokens per minute**: Token-based limiting for LLM applications
- **Concurrent requests**: Limit simultaneous requests
- **Burst handling**: Temporary capacity increases

### Client Tiers

| Tier | Requests/Min | Requests/Hour | Tokens/Min | Concurrent | Features |
|------|--------------|---------------|------------|------------|----------|
| Anonymous | 10 | 100 | N/A | 3 | Basic access |
| Basic | 60 | 1,000 | 10,000 | 10 | File uploads |
| Premium | 300 | 10,000 | 100,000 | 50 | Priority processing |
| Enterprise | 1,000 | 100,000 | 1,000,000 | 200 | Full access |

### Rate Limiting Strategies

1. **Sliding Window**: Accurate time-based limiting
2. **Token Bucket**: Burst handling with refill rate
3. **Fixed Window**: Simple periodic resets
4. **Adaptive**: Dynamic adjustment based on usage

## Quota Management Features

### Quota Types

- **Monthly/Daily Tokens**: Token consumption quotas
- **Monthly/Daily Requests**: Request count quotas
- **Custom Quotas**: Extensible for new quota types

### Quota Allocation Strategies

1. **Fixed**: Static allocation
2. **Proportional**: Based on historical usage
3. **Fair Share**: Equal distribution among clients
4. **Priority-Based**: Weighted by client priority
5. **Hybrid**: Combination of multiple strategies

### Auto-Adjustment Rules

- **Usage-Based**: Increase quotas for high-usage clients
- **Fair Share**: Reduce quotas for under-utilization
- **Demand-Based**: Adjust based on system load
- **Custom Rules**: Extensible rule system

## Configuration

### Main Configuration File

The system is configured via `config/rate_limit_config.yaml`:

```yaml
global:
  redis_url: "${REDIS_URL:-redis://localhost:6379}"
  default_tier: "anonymous"

tiers:
  premium:
    rate_limits:
      - type: "requests_per_minute"
        limit: 300
        burst_multiplier: 3.0
    quotas:
      - type: "monthly_tokens"
        limit: 10000000
        auto_scale: true
```

### Environment Variables

- `REDIS_URL`: Redis connection string
- `RATE_LIMIT_CONFIG_PATH`: Custom config file path

## Usage Examples

### Basic Rate Limiting

```python
from hermes.middleware import rate_limiter

# Check rate limit
result = await rate_limiter.check_rate_limit(
    client_id="user123",
    tier="premium",
    token_count=100
)

if result.allowed:
    # Process request
    pass
else:
    # Handle rate limit exceeded
    retry_after = result.retry_after
```

### FastAPI Integration

```python
from fastapi import FastAPI
from hermes.middleware.rate_limit_integration import init_rate_limiting

app = FastAPI()

# Initialize rate limiting
await init_rate_limiting(app, redis_url="redis://localhost:6379")

@app.get("/api/chat")
async def chat_endpoint():
    # Rate limiting automatically applied
    return {"response": "Hello!"}
```

### Quota Management

```python
from hermes.middleware import quota_manager, QuotaType

# Allocate quota to client
allocation = await quota_manager.allocate_quota(
    client_id="user123",
    quota_definition_key="premium_tokens",
    custom_limit=5000000
)

# Consume quota
success, allocation = await quota_manager.consume_quota(
    client_id="user123",
    quota_type=QuotaType.TOKENS,
    amount=1000
)
```

## API Endpoints

### Client Status

```bash
# Get rate limit status
GET /api/v1/rate-limits/status

# Get quota status
GET /api/v1/quotas/status
```

### Admin Operations

```bash
# Reset client limits (admin)
POST /api/v1/admin/reset-client-limits
{
  "client_id": "user123",
  "admin_key": "admin-key"
}

# Get system statistics (admin)
GET /api/v1/admin/system-stats

# Update client tier (admin)
POST /api/v1/admin/update-client-tier
{
  "client_id": "user123",
  "new_tier": "premium"
}
```

## Monitoring and Alerting

### Metrics

The system provides comprehensive metrics:

- **Rate Limit Metrics**: Requests, rejections, burst usage
- **Quota Metrics**: Allocation, consumption, utilization
- **Client Metrics**: Active clients, tier distribution
- **System Metrics**: Redis usage, performance metrics

### Alerting

Configurable alerts for:

- **High Usage**: When clients approach limits
- **Quota Exhaustion**: When quotas are fully consumed
- **Abuse Detection**: Suspicious usage patterns
- **System Overload**: High system utilization

### Integration with Monitoring Systems

- **Prometheus**: Export metrics for monitoring
- **Grafana**: Pre-built dashboards
- **AlertManager**: Alert routing and notification
- **Custom Webhooks**: Integration with existing systems

## Security Features

### Abuse Prevention

- **Automatic Penalties**: Exponential backoff for violations
- **IP Blocking**: Temporary blocking for abusive clients
- **Request Validation**: Validate and sanitize requests
- **Rate Limit Bypass**: Secure admin bypass mechanisms

### Client Authentication

- **API Keys**: Secure key-based authentication
- **JWT Tokens**: Token-based authentication
- **IP Whitelisting**: Trusted IP ranges
- **Multi-factor**: Enhanced security for sensitive operations

## Performance Considerations

### Redis Optimization

- **Connection Pooling**: Efficient Redis connections
- **Batch Operations**: Reduce Redis round trips
- **TTL Management**: Automatic key expiration
- **Memory Management**: Efficient data structures

### Caching

- **Local Caching**: Reduce Redis lookups
- **Cache Invalidation**: Consistent cache updates
- **Memory Usage**: Controlled cache size

### Scalability

- **Distributed Rate Limiting**: Multi-instance support
- **Horizontal Scaling**: Load balancer compatible
- **Database Sharding**: Large-scale deployment support

## Deployment

### Docker Configuration

```dockerfile
# Install Redis dependencies
RUN pip install redis

# Environment variables
ENV REDIS_URL=redis://redis:6379
ENV RATE_LIMIT_CONFIG_PATH=/app/config/rate_limit_config.yaml
```

### Kubernetes Deployment

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: hermes-api
spec:
  template:
    spec:
      containers:
      - name: api
        env:
        - name: REDIS_URL
          value: "redis://redis-service:6379"
```

### High Availability

- **Redis Cluster**: Distributed Redis deployment
- **Health Checks**: Container health monitoring
- **Graceful Degradation**: Fallback mechanisms
- **Circuit Breakers**: Fault tolerance

## Troubleshooting

### Common Issues

1. **Redis Connection Failed**
   - Check Redis URL configuration
   - Verify Redis is running and accessible
   - Check network connectivity

2. **Rate Limits Too Strict**
   - Review configuration settings
   - Check client tier assignments
   - Monitor actual usage patterns

3. **Quota Not Working**
   - Verify quota initialization
   - Check quota allocation rules
   - Review client usage history

### Debug Mode

Enable debug logging:

```python
import logging
logging.getLogger("hermes.middleware").setLevel(logging.DEBUG)
```

### Health Checks

```bash
# Check Redis connection
curl http://localhost:8000/health

# Check rate limiter status
curl http://localhost:8000/api/v1/rate-limits/status

# Check system statistics
curl http://localhost:8000/api/v1/admin/system-stats
```

## Best Practices

1. **Configuration Management**
   - Use environment-specific configs
   - Regularly review and adjust limits
   - Monitor system performance

2. **Client Tier Management**
   - Regularly audit client assignments
   - Implement upgrade/downgrade processes
   - Document tier benefits clearly

3. **Monitoring and Alerting**
   - Set up comprehensive monitoring
   - Configure appropriate alert thresholds
   - Regularly review alert effectiveness

4. **Security**
   - Rotate admin keys regularly
   - Monitor for abuse patterns
   - Implement IP-based restrictions

5. **Performance**
   - Monitor Redis performance
   - Optimize query patterns
   - Use connection pooling

## Future Enhancements

1. **Machine Learning Integration**
   - Predictive quota allocation
   - Intelligent burst handling
   - Anomaly detection

2. **Advanced Quota Types**
   - CPU time quotas
   - Memory usage quotas
   - Custom resource quotas

3. **Multi-tenant Support**
   - Organization-level quotas
   - Hierarchical quota management
   - Cross-tenant resource sharing

4. **Enhanced Analytics**
   - Usage pattern analysis
   - Performance optimization suggestions
   - Cost optimization recommendations