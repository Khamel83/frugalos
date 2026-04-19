# Hermes AI Assistant - API Reference

## Table of Contents

1. [Authentication](#authentication)
2. [Model Management](#model-management)
3. [Conversation Management](#conversation-management)
4. [Performance Optimization](#performance-optimization)
5. [Memory System](#memory-system)
6. [Monitoring](#monitoring)
7. [Security](#security)
8. [Error Handling](#error-handling)
9. [Rate Limiting](#rate-limiting)
10. [Webhooks](#webhooks)

---

## Authentication

### Overview

Hermes uses JWT-based authentication with optional multi-factor authentication. All API requests (except health checks) require authentication.

### Authentication Endpoints

#### POST `/api/auth/login`

Login with username and password.

**Request**:
```json
{
  "username": "john_doe",
  "password": "secure_password",
  "mfa_code": "123456"  // Required if MFA is enabled
}
```

**Response**:
```json
{
  "success": true,
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "expires_in": 3600,
  "user": {
    "user_id": "user_123",
    "username": "john_doe",
    "email": "john@example.com",
    "role": "basic_user",
    "mfa_enabled": true,
    "created_at": "2025-01-20T10:00:00Z"
  }
}
```

#### POST `/api/auth/refresh`

Refresh access token using refresh token.

**Request**:
```json
{
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

**Response**:
```json
{
  "success": true,
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "expires_in": 3600
}
```

#### POST `/api/auth/logout`

Logout and invalidate tokens.

**Headers**:
```
Authorization: Bearer <access_token>
```

**Response**:
```json
{
  "success": true,
  "message": "Successfully logged out"
}
```

### Authentication Headers

All protected endpoints require:

```
Authorization: Bearer <access_token>
```

### Error Codes

| Code | Description |
|------|-------------|
| 401 | Unauthorized - Invalid or missing token |
| 403 | Forbidden - Insufficient permissions |
| 429 | Too Many Requests - Rate limit exceeded |

---

## Model Management

### Overview

The model management endpoints provide access to AI model orchestration, including intelligent routing, performance monitoring, and cost optimization.

### Model Execution

#### POST `/api/models/completions`

Execute an AI completion with intelligent model selection.

**Request**:
```json
{
  "prompt": "Explain quantum computing in simple terms",
  "task_type": "text_generation",
  "max_tokens": 500,
  "temperature": 0.7,
  "complexity": "moderate",
  "budget_cents": 0.10,
  "latency_requirement_ms": 2000,
  "preferred_provider": "anthropic",
  "enable_fallback": true,
  "context": {
    "user_id": "user_123",
    "session_id": "session_456"
  }
}
```

**Parameters**:

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| prompt | string | Yes | The prompt text |
| task_type | string | No | Task type: `text_generation`, `code_generation`, `chat_completion`, `reasoning` |
| max_tokens | integer | No | Maximum tokens to generate (default: 500) |
| temperature | float | No | Sampling temperature (0.0-1.0, default: 0.7) |
| complexity | string | No | Task complexity: `simple`, `moderate`, `complex`, `expert` |
| budget_cents | float | No | Maximum cost in cents |
| latency_requirement_ms | integer | No | Maximum response time in milliseconds |
| preferred_provider | string | No | Preferred AI provider |
| enable_fallback | boolean | No | Enable automatic fallback (default: true) |
| context | object | No | Additional context metadata |

**Task Types**:

- `text_generation`: General text generation tasks
- `code_generation`: Code writing and analysis
- `chat_completion`: Conversational responses
- `reasoning`: Logical problem solving

**Complexity Levels**:

- `simple`: Straightforward tasks (routes to cheaper models)
- `moderate`: Standard tasks (balanced routing)
- `complex`: Multi-step reasoning (premium models)
- `expert`: Highest complexity (best available models)

**Response**:
```json
{
  "success": true,
  "request_id": "req_123456789",
  "model_id": "claude-3-sonnet-20240229",
  "provider": "anthropic",
  "content": "Quantum computing is a revolutionary approach to computing...",
  "tokens": {
    "input": 15,
    "output": 234,
    "total": 249
  },
  "latency_ms": 1245.6,
  "cost": 0.00373,
  "finish_reason": "end_turn",
  "cached": false,
  "fallback_used": false,
  "metadata": {
    "selection_score": 87.5,
    "original_model": "claude-3-sonnet-20240229",
    "routing_reason": "Best balance of quality and cost for moderate complexity task"
  }
}
```

### Model Registry

#### GET `/api/models/registry`

List all available models with their configurations and performance metrics.

**Query Parameters**:

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| provider | string | No | Filter by provider (openai, anthropic, ollama) |
| capability | string | No | Filter by capability |
| enabled_only | boolean | No | Show only enabled models (default: true) |

**Response**:
```json
{
  "models": [
    {
      "model_id": "gpt-4-turbo-preview",
      "name": "GPT-4 Turbo",
      "provider": "openai",
      "capabilities": ["text_generation", "code_generation", "reasoning"],
      "max_tokens": 4096,
      "context_window": 128000,
      "cost": {
        "input_per_1k": 0.01,
        "output_per_1k": 0.03
      },
      "priority": 1,
      "enabled": true,
      "performance": {
        "avg_latency_ms": 2100,
        "success_rate": 98.5,
        "total_requests": 15420,
        "total_cost": 234.56
      }
    }
  ],
  "count": 7
}
```

#### GET `/api/models/registry/{model_id}`

Get detailed information about a specific model.

**Response**:
```json
{
  "model_id": "claude-3-sonnet-20240229",
  "name": "Claude 3 Sonnet",
  "provider": "anthropic",
  "capabilities": ["text_generation", "code_generation", "reasoning"],
  "limits": {
    "max_tokens": 4096,
    "context_window": 200000
  },
  "cost": {
    "input_per_1k_tokens": 0.003,
    "output_per_1k_tokens": 0.015
  },
  "priority": 2,
  "enabled": true,
  "performance": {
    "total_requests": 8934,
    "successful_requests": 8812,
    "failed_requests": 122,
    "success_rate": 98.63,
    "tokens": {
      "total_input": 234567,
      "total_output": 189234
    },
    "cost": {
      "total": 156.78,
      "avg_per_request": 0.0175
    },
    "latency": {
      "avg_ms": 1456.7,
      "p95_ms": 2100,
      "p99_ms": 3200
    },
    "last_used": "2025-01-20T15:30:00Z",
    "last_error": null
  }
}
```

### Model Selection

#### POST `/api/models/select`

Get model recommendation without executing the request.

**Request**:
```json
{
  "task_type": "code_generation",
  "complexity": "moderate",
  "budget_cents": 0.05,
  "latency_requirement_ms": 1500,
  "preferred_provider": "openai"
}
```

**Response**:
```json
{
  "selected_model": {
    "model_id": "gpt-3.5-turbo",
    "name": "GPT-3.5 Turbo",
    "provider": "openai",
    "capabilities": ["code_generation"],
    "priority": 2,
    "cost": {
      "input_per_1k": 0.0005,
      "output_per_1k": 0.0015
    },
    "performance": {
      "avg_latency_ms": 850,
      "success_rate": 99.2
    }
  },
  "selection_criteria": {
    "task_type": "code_generation",
    "complexity": "moderate",
    "budget_cents": 0.05,
    "latency_requirement_ms": 1500,
    "preferred_provider": "openai"
  },
  "alternative_models": [
    {
      "model_id": "qwen2.5-coder:7b",
      "reason": "Free local alternative"
    }
  ]
}
```

### Statistics

#### GET `/api/models/statistics`

Get usage statistics for the specified time period.

**Query Parameters**:

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| hours | integer | No | Time period in hours (default: 24) |
| model_id | string | No | Filter by specific model |

**Response**:
```json
{
  "period_hours": 24,
  "total_requests": 1234,
  "successful_requests": 1218,
  "success_rate": 98.7,
  "total_cost": 12.45,
  "avg_cost_per_request": 0.0101,
  "avg_latency_ms": 1456.7,
  "models_used": 5,
  "breakdown_by_model": {
    "gpt-3.5-turbo": {
      "count": 450,
      "cost": 2.25,
      "tokens": 125000
    },
    "claude-3-haiku-20240307": {
      "count": 650,
      "cost": 1.85,
      "tokens": 180000
    }
  },
  "token_usage": {
    "total_input": 234567,
    "total_output": 189234,
    "total": 423801
  }
}
```

### Performance Metrics

#### GET `/api/models/metrics`

Get performance metrics for all models.

**Response**:
```json
{
  "metrics": {
    "gpt-3.5-turbo": {
      "total_requests": 5234,
      "successful_requests": 5189,
      "success_rate": 99.14,
      "avg_latency_ms": 856.3,
      "p95_latency_ms": 1200,
      "p99_latency_ms": 1800,
      "total_cost": 45.67,
      "total_tokens": 156789,
      "last_used": "2025-01-20T16:45:00Z"
    }
  },
  "timestamp": "2025-01-20T17:00:00Z"
}
```

### Health Check

#### GET `/api/models/health`

Health check for model orchestration system.

**Response**:
```json
{
  "timestamp": "2025-01-20T17:00:00Z",
  "components": {
    "orchestrator": "available",
    "benchmark_system": "available",
    "comparative_benchmark": "available"
  },
  "status": "healthy",
  "model_count": 7,
  "providers": ["openai", "anthropic", "ollama"]
}
```

---

## Conversation Management

### Overview

The conversation management endpoints provide access to context optimization, long-term memory, and conversation analysis.

### Context Management

#### POST `/api/conversations/{conversation_id}/messages`

Add a message to a conversation.

**Request**:
```json
{
  "role": "user",
  "content": "What's the capital of France?",
  "metadata": {
    "source": "web",
    "session_id": "session_123"
  }
}
```

**Parameters**:

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| role | string | Yes | Message role: `system`, `user`, `assistant`, `function`, `tool` |
| content | string | Yes | Message content |
| metadata | object | No | Additional metadata |

**Response**:
```json
{
  "success": true,
  "message_id": "msg_123456789",
  "tokens": 12,
  "timestamp": "2025-01-20T17:00:00Z",
  "conversation_stats": {
    "total_messages": 23,
    "total_tokens": 1456,
    "context_utilization": 35.6
  }
}
```

#### GET `/api/conversations/{conversation_id}/context`

Get optimized context window for the next request.

**Query Parameters**:

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| max_tokens | integer | No | Maximum tokens for context (default: conversation max) |
| model | string | No | Optimize for specific model context window |

**Response**:
```json
{
  "messages": [
    {
      "role": "system",
      "content": "You are a helpful assistant.",
      "tokens": 8,
      "timestamp": "2025-01-20T15:00:00Z"
    },
    {
      "role": "user",
      "content": "Hello! Can you help me?",
      "tokens": 6,
      "timestamp": "2025-01-20T15:01:00Z"
    }
  ],
  "total_tokens": 145,
  "compression_applied": false,
  "strategy_used": "hybrid",
  "summary": null
}
```

#### GET `/api/conversations/{conversation_id}/stats`

Get conversation statistics and analysis.

**Response**:
```json
{
  "conversation_id": "conv_123",
  "total_messages": 45,
  "message_counts": {
    "user": 23,
    "assistant": 22
  },
  "total_tokens": 2345,
  "max_tokens": 4096,
  "utilization": 57.3,
  "strategy": "hybrid",
  "created_at": "2025-01-20T10:00:00Z",
  "last_updated": "2025-01-20T17:00:00Z",
  "duration_minutes": 420.5,
  "compression_events": 2,
  "summaries_created": 1
}
```

### Branching

#### POST `/api/conversations/{conversation_id}/branches`

Create a branch from a specific point in the conversation.

**Request**:
```json
{
  "branch_from_index": 10,
  "branch_name": "Alternative approach"
}
```

**Response**:
```json
{
  "success": true,
  "branch_id": "conv_123_branch_0",
  "branch_name": "Alternative approach",
  "branch_from_index": 10,
  "message_count": 11
}
```

#### POST `/api/conversations/{conversation_id}/branches/{branch_id}/merge`

Merge a branch back into the main conversation.

**Request**:
```json
{
  "keep_original": true
}
```

**Response**:
```json
{
  "success": true,
  "messages_merged": 5,
  "merged_at": "2025-01-20T17:00:00Z"
}
```

### Memory System

#### GET `/api/conversations/{conversation_id}/memories`

Retrieve memories associated with a conversation.

**Query Parameters**:

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| limit | integer | No | Maximum memories to return (default: 50) |
| type | string | No | Filter by memory type |
| tags | string | No | Filter by tags (comma-separated) |

**Response**:
```json
{
  "memories": [
    {
      "memory_id": "mem_123456789",
      "content": "User expressed interest in Python programming",
      "memory_type": "fact",
      "importance_score": 0.75,
      "access_count": 3,
      "last_accessed": "2025-01-20T16:30:00Z",
      "tags": ["python", "programming", "interest"],
      "metadata": {
        "source_message": "msg_123",
        "extraction_method": "keyword"
      }
    }
  ],
  "total_count": 23,
  "types": ["fact", "entity", "summary"]
}
```

#### POST `/api/conversations/{conversation_id}/memories/search`

Search for relevant memories using semantic search.

**Request**:
```json
{
  "query": "What programming languages did we discuss?",
  "max_results": 10,
  "min_relevance": 0.6,
  "memory_types": ["fact", "summary"]
}
```

**Response**:
```json
{
  "search_results": [
    {
      "memory": {
        "memory_id": "mem_234567890",
        "content": "Discussed Python for data science and JavaScript for web development",
        "memory_type": "summary",
        "importance_score": 0.85
      },
      "relevance_score": 0.92
    }
  ],
  "total_found": 5,
  "search_strategy": "semantic_search"
}
```

#### GET `/api/conversations/{conversation_id}/insights`

Get conversation insights and analytics.

**Response**:
```json
{
  "conversation_id": "conv_123",
  "total_summaries": 3,
  "total_memories": 47,
  "top_topics": [
    {"topic": "python", "count": 15},
    {"topic": "programming", "count": 12},
    {"topic": "data", "count": 8}
  ],
  "top_entities": [
    {"entity": "Python", "count": 12},
    {"entity": "JavaScript", "count": 8},
    {"entity": "TensorFlow", "count": 5}
  ],
  "memory_types": {
    "fact": 28,
    "entity": 15,
    "summary": 4
  },
  "conversation_metrics": {
    "avg_message_length": 45.6,
    "response_time_avg": 2.3,
    "topic_diversity": 0.73
  }
}
```

---

## Performance Optimization

### Overview

Performance optimization endpoints provide access to caching, resource monitoring, and auto-scaling management.

### Caching

#### GET `/api/optimization/cache/stats`

Get cache performance statistics.

**Response**:
```json
{
  "multi_tier": {
    "hits": 15234,
    "misses": 3456,
    "sets": 12890,
    "hit_rate": 81.5,
    "total_requests": 18690
  },
  "l1_memory": {
    "hits": 12345,
    "misses": 2345,
    "sets": 9876,
    "hit_rate": 84.0,
    "max_size": 1000,
    "current_size": 856,
    "strategy": "lru"
  },
  "l2_redis": {
    "hits": 2889,
    "misses": 1111,
    "sets": 3014,
    "hit_rate": 72.2,
    "max_size": 10000,
    "current_size": 5432,
    "ttl": 300
  },
  "timestamp": "2025-01-20T17:00:00Z"
}
```

#### POST `/api/optimization/cache/invalidate`

Invalidate cache entries by tag.

**Request**:
```json
{
  "tag": "user_data",
  "pattern": "user_*"
}
```

**Response**:
```json
{
  "success": true,
  "entries_invalidated": 156,
  "tag": "user_data",
  "invalidation_time": "2025-01-20T17:00:00Z"
}
```

#### POST `/api/optimization/cache/clear`

Clear the entire cache.

**Response**:
```json
{
  "success": true,
  "message": "Cache cleared successfully",
  "cleared_entries": 2456,
  "clear_time": "2025-01-20T17:00:00Z"
}
```

### Resource Monitoring

#### GET `/api/optimization/resources/current`

Get current resource usage.

**Response**:
```json
{
  "timestamp": "2025-01-20T17:00:00Z",
  "cpu_percent": 65.4,
  "memory_percent": 78.2,
  "memory_used_mb": 6256.7,
  "disk_usage_percent": 45.8,
  "network": {
    "bytes_sent": 123456789,
    "bytes_recv": 987654321
  },
  "gpu": {
    "utilization": null,
    "memory_used": null
  },
  "kubernetes": {
    "pod_count": 3,
    "node_count": 1
  }
}
```

#### GET `/api/optimization/resources/prediction`

Get resource usage predictions.

**Query Parameters**:

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| type | string | No | Resource type: `cpu`, `memory`, `disk` |
| window | integer | No | Prediction window in minutes (default: 60) |

**Response**:
```json
{
  "current_value": 65.4,
  "predicted_mean": 68.7,
  "predicted_max": 75.2,
  "predicted_min": 62.1,
  "trend_slope": 0.3,
  "confidence_interval": 5.2,
  "prediction_minutes": 60,
  "data_points_used": 144,
  "recommendation": "CPU usage is trending upward, consider scaling up if trend continues"
}
```

### Auto-Scaling

#### GET `/api/optimization/scaling/decisions`

Get recent auto-scaling decisions.

**Query Parameters**:

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| limit | integer | No | Number of decisions to return (default: 10) |

**Response**:
```json
{
  "decisions": [
    {
      "timestamp": "2025-01-20T16:45:00Z",
      "resource_type": "cpu",
      "direction": "up",
      "current_value": 85.2,
      "threshold": 80.0,
      "target_replicas": 5,
      "reason": "High CPU usage: 85.2% exceeds max threshold 80%",
      "confidence": 0.92,
      "cost_impact": 2.50,
      "executed": true
    }
  ],
  "count": 5
}
```

#### POST `/api/optimization/scaling/evaluate`

Manually trigger scaling evaluation.

**Response**:
```json
{
  "decisions": [
    {
      "resource_type": "memory",
      "direction": "none",
      "current_value": 72.3,
      "threshold": 80.0,
      "target_replicas": 3,
      "reason": "Memory usage within normal range",
      "confidence": 0.15,
      "cost_impact": 0.0
    }
  ],
  "count": 1,
  "timestamp": "2025-01-20T17:00:00Z"
}
```

### Cost Analysis

#### GET `/api/optimization/cost/estimate`

Get current cost estimate.

**Query Parameters**:

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| hours | float | No | Time period in hours (default: 24) |

**Response**:
```json
{
  "cost_breakdown": {
    "cpu_cost": 2.45,
    "memory_cost": 1.23,
    "disk_cost": 0.34,
    "total_cost": 4.02
  },
  "period_hours": 24,
  "timestamp": "2025-01-20T17:00:00Z"
}
```

#### GET `/api/optimization/cost/optimizations`

Get cost optimization suggestions.

**Query Parameters**:

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| max_cpu | float | No | Maximum CPU utilization (default: 80) |
| max_memory | float | No | Maximum memory utilization (default: 85) |

**Response**:
```json
{
  "suggestions": [
    {
      "type": "cpu_optimization",
      "priority": "medium",
      "description": "Average CPU usage: 65.4% - potential for cost optimization",
      "recommendations": [
        "Consider reducing CPU allocation",
        "Implement more aggressive request queuing",
        "Optimize CPU-intensive operations"
      ],
      "estimated_savings": "15-25%"
    }
  ],
  "count": 3,
  "timestamp": "2025-01-20T17:00:00Z"
}
```

---

## Monitoring

### Overview

Monitoring endpoints provide access to system health, performance metrics, and alerting.

### Health Checks

#### GET `/api/optimization/health`

Health check for optimization systems.

**Response**:
```json
{
  "timestamp": "2025-01-20T17:00:00Z",
  "components": {
    "performance_monitoring": "active",
    "resource_monitoring": "active",
    "cache_system": "available",
    "auto_scaling": "available"
  },
  "status": "healthy",
  "uptime_seconds": 86400,
  "version": "1.0.0"
}
```

#### GET `/health`

Main application health check.

**Response**:
```json
{
  "status": "operational",
  "timestamp": "2025-01-20T17:00:00Z",
  "version": "1.0.0",
  "components": {
    "database": "connected",
    "redis": "connected",
    "models": "available",
    "monitoring": "active"
  }
}
```

### Performance Metrics

#### GET `/api/metrics`

Get current system metrics.

**Response**:
```json
{
  "system": {
    "cpu_percent": 65.4,
    "memory_percent": 78.2,
    "disk_usage_percent": 45.8,
    "uptime_seconds": 86400
  },
  "application": {
    "requests_per_second": 45.6,
    "avg_response_time_ms": 1234.5,
    "error_rate": 0.02
  },
  "models": {
    "active_models": 7,
    "avg_latency_ms": 1456.7,
    "success_rate": 98.5
  }
}
```

---

## Security

### Overview

Security endpoints provide access to user management, authentication, and compliance features.

### User Management

#### POST `/api/security/users`

Create a new user.

**Request**:
```json
{
  "username": "john_doe",
  "email": "john@example.com",
  "password": "secure_password_123",
  "role": "basic_user"
}
```

**Response**:
```json
{
  "success": true,
  "user_id": "user_123456789",
  "username": "john_doe",
  "email": "john@example.com",
  "role": "basic_user",
  "mfa_enabled": false,
  "created_at": "2025-01-20T17:00:00Z"
}
```

#### GET `/api/security/users/{user_id}`

Get user details.

**Response**:
```json
{
  "user_id": "user_123456789",
  "username": "john_doe",
  "email": "john@example.com",
  "role": "basic_user",
  "mfa_enabled": true,
  "last_login": "2025-01-20T16:30:00Z",
  "created_at": "2025-01-15T10:00:00Z",
  "active": true
}
```

### MFA Management

#### POST `/api/security/mfa/setup`

Setup multi-factor authentication for a user.

**Response**:
```json
{
  "success": true,
  "mfa_secret": "JBSWY3DPEHPK3PXP",
  "qr_code": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAA...",
  "backup_codes": ["123456", "789012", "345678", "901234"],
  "instructions": "Scan QR code with authenticator app"
}
```

#### POST `/api/security/mfa/verify`

Verify MFA setup.

**Request**:
```json
{
  "mfa_code": "123456"
}
```

**Response**:
```json
{
  "success": true,
  "message": "MFA setup completed successfully",
  "backup_codes_remaining": 8
}
```

### Compliance

#### GET `/api/security/compliance/audit`

Get audit trail for user actions.

**Query Parameters**:

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| user_id | string | No | Filter by user ID |
| start_date | string | No | Start date (ISO format) |
| end_date | string | No | End date (ISO format) |
| action | string | No | Filter by action type |

**Response**:
```json
{
  "audit_events": [
    {
      "event_id": "audit_123456789",
      "user_id": "user_123456789",
      "action": "login",
      "resource": "/api/auth/login",
      "ip_address": "192.168.1.100",
      "user_agent": "Mozilla/5.0...",
      "timestamp": "2025-01-20T16:30:00Z",
      "success": true,
      "details": {
        "mfa_used": true,
        "session_duration": 3600
      }
    }
  ],
  "total_count": 125,
  "filtered_count": 23
}
```

---

## Error Handling

### Standard Error Response Format

All API errors follow this consistent format:

```json
{
  "error": {
    "code": "RESOURCE_NOT_FOUND",
    "message": "The requested resource was not found",
    "details": "Model 'invalid-model' does not exist in registry",
    "timestamp": "2025-01-20T17:00:00Z",
    "request_id": "req_123456789"
  }
}
```

### Common Error Codes

| Code | HTTP Status | Description |
|------|-------------|-------------|
| `INVALID_REQUEST` | 400 | Request validation failed |
| `UNAUTHORIZED` | 401 | Authentication required |
| `FORBIDDEN` | 403 | Insufficient permissions |
| `RESOURCE_NOT_FOUND` | 404 | Resource not found |
| `METHOD_NOT_ALLOWED` | 405 | HTTP method not allowed |
| `RATE_LIMIT_EXCEEDED` | 429 | Rate limit exceeded |
| `MODEL_UNAVAILABLE` | 503 | Model service unavailable |
| `INTERNAL_ERROR` | 500 | Internal server error |

### Model-Specific Errors

| Code | Description |
|------|-------------|
| `MODEL_NOT_FOUND` | Specified model not available |
| `MODEL_RATE_LIMITED` | Model API rate limit exceeded |
| `MODEL_INSUFFICIENT_TOKENS` | Not enough tokens for request |
| `MODEL_CONTENT_FILTERED` | Content filtered by model provider |
| `MODEL_OVERLOADED` | Model service overloaded |

---

## Rate Limiting

### Rate Limiting Rules

Rate limits are applied based on user role and API tier:

| Role | Requests/Minute | Burst | Daily Limit |
|------|----------------|-------|------------|
| anonymous | 10 | 20 | 100 |
| basic_user | 50 | 100 | 1000 |
| power_user | 200 | 400 | 10000 |
| admin | 1000 | 2000 | Unlimited |

### Rate Limit Headers

Responses include rate limiting information:

```
X-RateLimit-Limit: 50
X-RateLimit-Remaining: 45
X-RateLimit-Reset: 1642695600
X-RateLimit-Retry-After: 30
```

### Rate Limit Error Response

```json
{
  "error": {
    "code": "RATE_LIMIT_EXCEEDED",
    "message": "Rate limit exceeded",
    "details": "Rate limit of 50 requests per minute exceeded",
    "retry_after": 30
  }
}
```

---

## Webhooks

### Overview

Webhooks provide real-time notifications for important events.

### Webhook Configuration

#### POST `/api/webhooks`

Create a webhook subscription.

**Request**:
```json
{
  "url": "https://your-app.com/webhooks/hermes",
  "events": ["model.completed", "conversation.created", "error.occurred"],
  "secret": "webhook_secret_123",
  "active": true
}
```

**Response**:
```json
{
  "success": true,
  "webhook_id": "webhook_123456789",
  "url": "https://your-app.com/webhooks/hermes",
  "events": ["model.completed", "conversation.created", "error.occurred"],
  "active": true,
  "created_at": "2025-01-20T17:00:00Z"
}
```

### Webhook Events

#### Model Completion Event

```json
{
  "event": "model.completed",
  "timestamp": "2025-01-20T17:00:00Z",
  "data": {
    "request_id": "req_123456789",
    "model_id": "claude-3-sonnet-20240229",
    "latency_ms": 1245.6,
    "tokens": 249,
    "cost": 0.00373,
    "success": true
  }
}
```

#### Error Event

```json
{
  "event": "error.occurred",
  "timestamp": "2025-01-20T17:00:00Z",
  "data": {
    "error_code": "MODEL_RATE_LIMITED",
    "error_message": "OpenAI API rate limit exceeded",
    "request_id": "req_123456789",
    "user_id": "user_123456789",
    "severity": "warning"
  }
}
```

### Webhook Security

Webhooks use HMAC signatures for security:

```python
import hmac
import hashlib

def verify_webhook_signature(payload, signature, secret):
    expected_signature = hmac.new(
        secret.encode('utf-8'),
        payload.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()

    return hmac.compare_digest(expected_signature, signature)
```

---

## API Versioning

### Current Version

- **Current API Version**: v1
- **Base URL**: `https://api.hermes.ai/v1`

### Version Support

- **v1**: Current stable version
- **v0**: Deprecated (support ends 2025-06-01)

### Versioning Strategy

- URL path versioning: `/api/v1/models/completions`
- Backward compatibility maintained within major versions
- Deprecation notices sent 90 days before removal

### Version Headers

Responses include version information:

```
API-Version: 1.0
Supported-Versions: 1.0
Deprecated-Versions: 0.x
```

---

## SDKs and Libraries

### Python SDK

```python
from hermes_sdk import HermesClient

client = HermesClient(
    api_key="your_api_key",
    base_url="https://api.hermes.ai/v1"
)

# Generate completion
response = client.models.completions.create(
    prompt="Explain quantum computing",
    task_type="text_generation",
    max_tokens=300
)

print(response.content)
```

### JavaScript SDK

```javascript
import { HermesClient } from '@hermes/sdk';

const client = new HermesClient({
  apiKey: 'your_api_key',
  baseURL: 'https://api.hermes.ai/v1'
});

const response = await client.models.completions.create({
  prompt: 'Explain quantum computing',
  taskType: 'text_generation',
  maxTokens: 300
});

console.log(response.content);
```

### Community SDKs

- **Go**: Available via community contributions
- **Rust**: Available via community contributions
- **Java**: Available via community contributions

---

## Conclusion

This API reference provides comprehensive documentation for all Hermes AI Assistant platform endpoints:

✅ **Complete API Coverage**: All endpoints documented
✅ **Request/Response Examples**: Clear examples for each endpoint
✅ **Error Handling**: Comprehensive error codes and responses
✅ **Authentication**: Full auth flow documentation
✅ **Rate Limiting**: Clear limits and headers
✅ **Webhooks**: Real-time event notifications
✅ **Versioning**: API versioning strategy

The API follows REST best practices and provides a consistent, predictable interface for all operations. For additional support, refer to the [Complete Guide](HERMES_COMPLETE_GUIDE.md) or contact our support team.