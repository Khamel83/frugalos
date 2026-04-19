# Hermes AI Assistant - Integration Guide

## Table of Contents

1. [Quick Integration](#quick-integration)
2. [SDK Integration](#sdk-integration)
3. [API Integration](#api-integration)
4. [Third-Party Integrations](#third-party-integrations)
5. [Configuration](#configuration)
6. [Examples and Use Cases](#examples-and-use-cases)
7. [Testing](#testing)
8. [Troubleshooting](#troubleshooting)

---

## Quick Integration

### 5-Minute Quick Start

1. **Install Dependencies**
```bash
pip install hermes-ai-assistant
```

2. **Set API Keys**
```bash
export OPENAI_API_KEY=your_openai_key
export ANTHROPIC_API_KEY=your_anthropic_key
export REDIS_URL=redis://localhost:6379
```

3. **First API Call**
```python
from hermes import HermesClient

client = HermesClient()

response = client.models.completions.create(
    prompt="Explain quantum computing in simple terms",
    task_type="text_generation",
    max_tokens=300
)

print(response.content)
```

### Environment Setup

**Docker Compose (Recommended)**
```yaml
# docker-compose.yml
version: '3.8'
services:
  hermes-api:
    image: hermes:latest
    ports:
      - "8000:8000"
    environment:
      - OPENAI_API_KEY=${OPENAI_API_KEY}
      - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}
      - REDIS_URL=redis://redis:6379
    depends_on:
      - redis

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    command: redis-server --appendonly yes
```

```bash
# Start the platform
docker-compose up -d

# Test integration
curl -X POST http://localhost:8000/api/models/completions \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Hello, world!", "task_type": "chat_completion", "max_tokens": 100}'
```

---

## SDK Integration

### Python SDK

### Installation
```bash
pip install hermes-sdk
```

### Basic Usage
```python
from hermes_sdk import HermesClient

# Initialize client
client = HermesClient(
    api_key="your_api_key",
    base_url="https://api.hermes.ai/v1"
)

# Create conversation
conversation = client.conversations.create(
    system_prompt="You are a helpful AI assistant.",
    strategy="hybrid"
)

# Add messages
conversation.add_message("user", "What's the capital of France?")
response = conversation.add_message("assistant", "The capital of France is Paris.")

# Get optimized context
context = conversation.get_context()
print(f"Context tokens: {context.total_tokens}")
```

### Advanced Features
```python
# Multi-model execution with routing
response = client.models.completions.create(
    prompt="Write a Python function to sort a list",
    task_type="code_generation",
    complexity="moderate",
    budget_cents=0.05,  # $0.05 max cost
    latency_requirement_ms=2000,
    enable_fallback=True
)

# Check which model was used
print(f"Used model: {response.model_id}")
print(f"Cost: ${response.cost:.4f}")
```

### Error Handling
```python
try:
    response = client.models.completions.create(
        prompt="Your prompt here",
        max_tokens=1000
    )
except HermesError as e:
    print(f"Error: {e.error_code}: {e.message}")
    print(f"Request ID: {e.request_id}")
except Exception as e:
    print(f"Unexpected error: {e}")
```

### Configuration
```python
from hermes_sdk import HermesConfig

config = HermesConfig(
    api_key="your_api_key",
    timeout=30,
    max_retries=3,
    default_model="gpt-3.5-turbo",
    max_tokens=4096,
    enable_caching=True,
    cache_ttl=300
)

client = HermesClient(config=config)
```

### Conversation Management
```python
# Create conversation with specific strategy
conversation = client.conversations.create(
    strategy="hierarchical_summary",
    max_tokens=8000,
    auto_summarize_every=50
)

# Add messages
conversation.add_message("user", "Start of conversation...")
conversation.add_message("assistant", "Response 1...")
# After 50 messages, auto-summarization occurs

# Get conversation insights
insights = conversation.get_insights()
print(f"Top topics: {insights.top_topics}")
print(f"Memory count: {insights.total_memories}")
```

### Memory and Search
```python
# Search conversation memories
memories = conversation.search_memories(
    query="What programming languages were discussed?",
    max_results=10,
    min_relevance=0.6
)

for memory in memories:
    print(f"Memory: {memory.content}")
    print(f"Relevance: {memory.relevance_score:.2f}")
```

### Benchmarking
```python
# Run comparative benchmark
benchmark = client.benchmarking.comparison(
    model_ids=["gpt-3.5-turbo", "claude-3-haiku"],
    test_scenarios=["text_generation", "code_generation"]
)

print(f"Quality ranking: {benchmark.rankings['quality']}")
print(f"Cost ranking: {benchmark.rankings['cost_efficiency']}")
```

### Monitoring
```python
# Get platform health
health = client.health.check()
print(f"Platform status: {health.status}")
print(f"Components: {health.components}")

# Get statistics
stats = client.get_statistics(hours=24)
print(f"Total requests: {stats['total_requests']}")
print(f"Success rate: {stats['success_rate']:.1f}%")
print(f"Average cost: ${stats['avg_cost_per_request']:.4f}")
```

---

## API Integration

### RESTful API Example

#### Model Execution
```python
import requests
import json

# API configuration
BASE_URL = "https://api.hermes.ai/v1"
HEADERS = {
    "Authorization": "Bearer your_api_key",
    "Content-Type": "application/json"
}

# Execute completion
def create_completion(prompt, task_type="text_generation"):
    url = f"{BASE_URL}/models/completions"
    data = {
        "prompt": prompt,
        "task_type": task_type,
        "max_tokens": 500,
        "temperature": 0.7,
        "complexity": "moderate"
    }

    response = requests.post(url, json=data, headers=HEADERS)
    return response.json()

# Usage
response = create_completion(
    "Explain the benefits of AI in healthcare",
    task_type="text_generation"
)
print(response['content'])
```

#### Conversation Management
```python
# Create conversation
def create_conversation():
    url = f"{BASE_URL}/conversations"
    data = {
        "system_prompt": "You are a helpful healthcare assistant.",
        "strategy": "hybrid"
    }

    response = requests.post(url, json=data, headers=HEADERS)
    return response.json()

# Add message
def add_message(conversation_id, role, content):
    url = f"{BASE_URL}/conversations/{conversation_id}/messages"
    data = {
        "role": role,
        "content": content
    }

    response = requests.post(url, json=data, headers=HEADERS)
    return response.json()

# Usage
conversation = create_conversation()
message = add_message(conversation['conversation_id'], "user", "Hello!")
```

### Webhook Integration

#### Setting Up Webhooks
```python
import json
import hmac
import hashlib
from flask import Flask, request

app = Flask(__name__)

# Webhook endpoint
@app.route('/webhooks/hermes', methods=['POST'])
def hermes_webhook():
    # Verify webhook signature
    signature = request.headers.get('X-Hermes-Signature')
    payload = request.get_data()

    if not verify_webhook_signature(payload, signature, webhook_secret):
        return {"status": "invalid_signature"}, 401

    # Process webhook event
    event = json.loads(payload)
    print(f"Received event: {event['event']}")

    # Handle different event types
    if event['event'] == 'model.completed':
        handle_model_completed(event['data'])
    elif event['event'] == 'error.occurred':
        handle_error_occurred(event['data'])

    return {"status": "received"}, 200

def verify_webhook_signature(payload, signature, secret):
    expected_signature = hmac.new(
        secret.encode('utf-8'),
        payload,
        hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected_signature, signature)

def handle_model_completed(data):
    model_id = data['model_id']
    latency = data['latency_ms']
    cost = data['cost']
    print(f"Model {model_id} completed in {latency}ms, cost: ${cost:.4f}")

def handle_error_occurred(data):
    error_code = data['error_code']
    error_message = data['error_message']
    print(f"Error {error_code}: {error_message}")
```

---

## Third-Party Integrations

### Slack Integration

#### Bot Token Setup
```python
import slack_sdk
from slack_sdk import WebClient
from hermes_sdk import HermesClient

# Initialize clients
slack_client = WebClient(token="xoxb-your-slack-bot-token")
hermes_client = HermesClient()

@app.route('/slack/events', methods=['POST'])
def slack_events():
    # Handle Slack events
    data = request.json
    if data['type'] == 'url_verification':
        return data['challenge']

    elif data['type'] == 'message' and data['text']:
        message = data['event']['text']
        channel = data['event']['channel']

        # Get Hermes response
        hermes_response = hermes_client.models.completions.create(
            prompt=message,
            task_type="chat_completion",
            max_tokens=300
        )

        # Send response to Slack
        slack_client.chat_postMessage(
            channel=channel,
            text=hermes_response['content']
        )

    return {"status": "ok"}
```

### Discord Integration

#### Discord Bot Setup
```python
import discord
from discord.ext import commands
from hermes_sdk import HermesClient

intents = discord.Intents.default()

# Initialize clients
hermes_client = HermesClient()

@bot.event
async def on_ready():
    print(f'Bot is ready and connected!')

@bot.command()
async def ask(ctx, *, question: str):
    """Ask the AI assistant a question"""
    try:
        # Get Hermes response
        response = hermes_client.models.completions.create(
            prompt=question,
            task_type="chat_completion",
            max_tokens=500
        )

        await ctx.send(f"🤖: {response['content']}")

    except Exception as e:
        await ctx.send(f"❌ Error: {str(e)}")

@bot.command()
async def model_info(ctx):
    """Get current model information"""
    info = hermes_client.models.registry.list()

    model_list = []
    for model in info['models']:
        model_list.append(f"• {model['name']} ({model['provider']})")

    await ctx.send("🤖 **Available Models:**\n" + "\n".join(model_list))
```

### Microsoft Teams Integration

```python
from msal import ConfidentialClientApplication
from msal_serialization import Client
from hermes_sdk import HermesClient

# Azure AD authentication
app = ConfidentialClientApplication(
    client_id="your_client_id",
    client_credential="your_client_secret",
    authority="https://login.microsoftonline.com/common"
)

@app.route('/api/teams/auth')
def teams_auth():
    # Handle OAuth flow
    return app.get_authorization_url()

@app.route('/api/teams/ask')
async def ask_teams():
    # Process Teams message
    try:
        # Get Hermes response
        response = hermes_client.models.completions.create(
            prompt=request.json.get('message'),
            task_type="chat_completion",
            max_tokens=500
        )

        return {
            "type": "message",
            "text": response['content']
        }

    except Exception as e:
        return {
            "type": "error",
            "text": f"Error: {str(e)}"
        }
```

### Google Workspace Integration

```python
import google.auth.transport.requests
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from googleapiclient.discovery import build
from hermes_sdk import HermesClient

# OAuth2 flow setup
SCOPES = ['https://www.googleapis.com/auth/docs']
CLIENT_SECRETS_FILE = 'client_secrets.json'
REDIRECT_URI = 'https://your-app.com/callback'

flow = Flow.from_client_secrets_file(
    "client_secrets.json",
    scopes=SCOPES,
    redirect_uri=REDIRECT_URI
)

credentials = flow.run_local_server(port=8000)

# Google Workspace API
SCOPES = ['https://www.googleapis.com/auth/documents']
creds = Credentials.from_authorized_user_info(info)
docs_service = build('docs', 'v1', credentials=creds, SCOPES)

# Google Docs integration
def create_google_docs_document(content, title):
    document = {
        'title': title,
        'content': content,
        'mimeType': 'text/plain'
    }

    try:
        result = docs_service.documents().create(body=document)
        return f"Document created: {result['id']}"
    except Exception as e:
        return f"Error creating document: {e}"
```

---

## Configuration

### Environment Variables

```bash
# Required
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
REDIS_URL=redis://localhost:6379

# Database
DATABASE_URL=postgresql://localhost/hermes

# Optional
COHERE_API_KEY=...
AZURE_OPENAI_API_KEY=...
GOOGLE_PALM_API_KEY=...

# Performance
CACHE_L1_MAX_SIZE=1000
ENABLE_AUTO_SCALING=true
PROMETHEUS_ENABLED=true

# Security
MFA_REQUIRED=false
ENABLE_AUDIT_LOGGING=true
SESSION_TIMEOUT=3600

# Monitoring
LOG_LEVEL=INFO
METRICS_PORT=9090
```

### Configuration Files

#### Application Config
```python
# config.py
from pydantic import BaseModel
from typing import Optional

class Config(BaseModel):
    openai_api_key: str
    anthropic_api_key: str
    redis_url: str
    database_url: str

    # Optional
    cohere_api_key: Optional[str] = None
    azure_openai_api_key: Optional[str] = None
    google_palm_api_key: Optional[str] = None

    # Performance
    cache_l1_max_size: int = 1000
    cache_l2_ttl: int = 300
    enable_auto_scaling: bool = True

    # Security
    mfa_required: bool = False
    enable_audit_logging: bool = True
    session_timeout: int = 3600

    # Logging
    log_level: str = "INFO"
    metrics_enabled: bool = True

class ProductionConfig(Config):
    log_level: str = "WARNING"
    enable_debug: bool = False
    performance_monitoring: bool = True
    security_monitoring: bool = True

class DevelopmentConfig(Config):
    log_level: str = "DEBUG"
    enable_debug: bool = True
    performance_monitoring: bool = False
    security_monitoring: bool = False
```

### Docker Configuration

#### Docker Compose
```yaml
version: '3.8'

services:
  hermes:
    image: hermes:latest
    ports:
      - "8000:8000"
    environment:
      - OPENAI_API_KEY=${OPENAI_API_KEY}
      - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}
      - REDIS_URL=redis://redis:6379
      - DATABASE_URL=postgresql://postgres:5432/hermes
      - LOG_LEVEL=INFO
    depends_on:
      - redis
      - postgres
    restart: unless-stopped

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
    environment:
      - POSTGRES_DB=hermes
      - POSTGRES_USER=postgres
      - POSTGRES_PASSWORD=postgres
    volumes:
      - postgres_data:/var/lib/postgresql/data
    restart: unless-stopped

  prometheus:
    image: prom/prometheus:latest
    ports:
      - "9090:9090"
    volumes:
      - prometheus_data:/prometheus
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'
      - '--storage.tsdb.path=/prometheus'
    restart: unless-stopped

  grafana:
    image: grafana/grafana:latest
    ports:
      - "3000:3000"
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=admin
    volumes:
      - grafana_data:/var/lib/grafana
      - ./monitoring/grafana:/etc/grafana
    restart: unless-stopped

volumes:
  redis_data:
  postgres_data:
  prometheus_data:
  grafana_data:
```

---

## Examples and Use Cases

### Customer Support Chatbot

```python
from hermes_sdk import HermesClient
from flask import Flask, request, jsonify

app = Flask(__name__)
client = HermesClient()

@app.route('/api/support/chat', methods=['POST'])
def support_chat():
    data = request.json
    customer_id = data.get('customer_id')
    message = data.get('message')

    # Get customer context
    conversation = client.conversations.get_or_create(
        f"support_{customer_id}",
        system_prompt="You are a helpful customer support agent.",
        strategy="hybrid"
    )

    # Get relevant customer information
    customer_data = get_customer_data(customer_id)
    context_info = f"Customer: {customer_data['name'] (Plan: {customer_data['plan']}, Since: {customer_data['created_at']})"

    # Get customer interaction history
    recent_conversations = get_recent_conversations(customer_id)
    context_summary = summarize_conversations(recent_conversations)

    # Enhanced prompt with context
    enhanced_prompt = f"""
Customer Context: {context_info}
Recent Issues: {context_summary}
Current Issue: {message}

Please provide helpful assistance.
    """

    # Get response
    response = conversation.add_message("user", enhanced_prompt)
    assistant_response = conversation.add_message("assistant")

    # Save conversation
    conversation.save()

    return jsonify({
        "response": assistant_response.content,
        "conversation_id": conversation.id,
        "metadata": {
            "customer_id": customer_id,
            "context_used": len(context_info) > 0,
            "history_used": len(context_summary) > 0
        }
    })
```

### Code Assistant

```python
from hermes_sdk import HermesClient

client = HermesClient()

def generate_code_snippet(task, language="python"):
    # Select appropriate model for coding
    model_preferences = {
        "python": ["qwen2.5-coder:7b", "llama3.1:8b-instruct"],
        "javascript": ["gpt-4", "claude-3-sonnet-20240229"],
        "java": ["gpt-4", "claude-3-sonnet-20240229"],
        "sql": ["gpt-4", "claude-3-opus-20240229"]
    }

    models = model_preferences.get(language, ["gpt-3.5-turbo"])
    preferred_provider = "ollama" if language in ["python", "sql"] else None

    response = client.models.completions.create(
        prompt=f"Write a {language} function to {task}",
        task_type="code_generation",
        max_tokens=500,
        complexity="moderate",
        preferred_provider=preferred_provider,
        enable_fallback=True
    )

    return response.content

# Usage
python_code = generate_code_snippet("sort a list in ascending order", "python")
print(python_code)
```

### Research Assistant

```python
from hermes_sdk import HermesClient
import re

class ResearchAssistant:
    def __init__(self):
        self.client = HermesClient()
        self.research_history = []

    def search_papers(self, query, max_results=10):
        """Search for academic papers"""
        response = self.client.models.completions.create(
            prompt=f"Find academic papers about: {query}. "
                   f"Provide titles, authors, and brief summaries. "
                   f"Limit to {max_results} results.",
            task_type="text_generation",
            max_tokens=1000,
            complexity="complex"
        )

        papers = self._parse_papers(response.content)
        self.research_history.append({
            "query": query,
            "results": papers,
            "timestamp": datetime.utcnow()
        })

        return papers

    def generate_summary(self, paper_titles):
        """Generate research summary"""
        titles_text = "\n".join([f"- {title}" for title in paper_titles])

        response = self.client.models.completions.create(
            prompt=f"Research Summary:\n\n{titles_text}\n\n"
                   f"Provide a concise summary of these papers, highlighting "
                   f"key findings and relationships between them.",
            task_type="reasoning",
            max_tokens=500,
            complexity="expert"
        )

        return response.content

    def _parse_papers(self, content):
        """Parse paper information from response"""
        papers = []
        lines = content.split('\n')

        current_paper = None
        for line in lines:
            if line.startswith("Title:"):
                current_paper = {"title": line[7:].strip()}
            elif line.startswith("Authors:"):
                if current_paper:
                    current_paper["authors"] = line[9:].strip()
            elif line.startswith("Summary:"):
                if current_paper:
                    current_paper["summary"] = line[9:].strip()
                    papers.append(current_paper)
                    current_paper = None

        return papers

# Usage
research = ResearchAssistant()
papers = research.search_papers("machine learning interpretability")
summary = research.generate_summary([p["title"] for p in papers])
print(summary)
```

### Educational Content Generator

```python
from hermes_sdk import HermesClient

class ContentGenerator:
    def __init__(self):
        self.client = GenerateClient()

    def generate_explanation(self, topic, target_audience="beginner", length="medium"):
        """Generate educational content"""
        audience_guidance = {
            "beginner": "Use simple language, avoid jargon, include examples",
            "intermediate": "Use technical terms with explanations",
            "advanced": "Use expert terminology with deep analysis"
        }

        guidance = audience_guidance.get(target_audience, "Use clear language")

        response = self.client.models.completions.create(
            prompt=f"Create educational content about: {topic}\n\n"
                   f"Target audience: {target_audience}\n"
                   f"Length: {length}\n"
                   f"Guidance: {guidance}\n\n"
                   f"Include examples where appropriate.",
            task_type="text_generation",
            max_tokens=1500,
            complexity="moderate"
        )

        return response.content

    def generate_quiz(self, topic, num_questions=5):
        """Generate quiz questions"""
        response = self.client.models.competions.create(
            prompt=f"Create {num_questions} quiz questions about: {topic}\n\n"
                   "Make questions multiple choice with 4 options.\n"
                   "Include the correct answer at the end.",
            task_type="reasoning",
            max_tokens=1000,
            complexity="moderate"
        )

        return self._parse_quiz(response.content)

    def _parse_quiz(self, content):
        """Parse quiz from response"""
        questions = []
        lines = content.split('\n')

        for line in lines:
            if line.strip().isdigit() + '.':
                question = {"question": "", "options": [], "answer": "", "explanation": ""}
                current_question = question
                questions.append(current_question)
            elif line.strip().startswith("1."):
                current_question["options"].append(line.strip())
            elif line.strip().startswith("Correct answer:"):
                current_question["answer"] = line.strip()[16:]
            elif line.strip().startswith("Explanation:"):
                current_question["explanation"] = line.strip()[13:]

        return questions

# Usage
generator = ContentGenerator()
content = generator.generate_explanation("neural networks", "beginner", "short")
quiz = generator.generate_quiz("Python fundamentals", 3)
```

---

## Testing

### Unit Testing

```python
import unittest
from hermes_sdk import HermesClient, HermesError
from unittest.mock import Mock, patch

class TestHermesClient(unittest.TestCase):
    def setUp(self):
        self.client = HermesClient(
            api_key="test_key",
            base_url="http://localhost:8000"
        )

    @patch('hermes_sdk.HermesClient._make_request')
    def test_create_completion(self, mock_request):
        mock_request.return_value = {
            "content": "Test response",
            "model_id": "test-model",
            "tokens": {"input": 10, "output": 20, "total": 30},
            "cost": 0.003,
            "success": True
        }

        response = self.client.models.completions.create("Test prompt")

        self.assertEqual(response.content, "Test response")
        self.assertEqual(response.model_id, "test-model")
        self.assertEqual(response.tokens['total'], 30)

    def test_error_handling(self):
        with patch('hermes_sdk.HermesClient._make_request') as mock_request:
            mock_request.side_effect = Exception("Network error")

            with self.assertRaises(HermesError):
                self.client.models.completions.create("Test prompt")

### Integration Testing

```python
import requests
import pytest
from threading import Thread
import time

class TestHermesAPI:
    BASE_URL = "http://localhost:8000"
    API_KEY = "test_key"

    def test_conversation_flow(self):
        # Create conversation
        response = requests.post(
            f"{self.BASE_URL}/conversations",
            json={"system_prompt": "Test system prompt"},
            headers={"Authorization": f"Bearer {self.API_KEY}"}
        )
        conversation_id = response.json()["conversation_id"]

        # Add messages
        response = requests.post(
            f"{self.BASE_URL}/conversations/{conversation_id}/messages",
            json={
                "role": "user",
                "content": "Test message 1"
            },
            headers={"Authorization": f"Bearer {self.API_KEY}"}
        )

        # Get context
        response = requests.get(
            f"{self.BASE_URL}/conversations/{conversation_id}/context",
            headers={"Authorization": f"Bearer {self.API_KEY}"}
        )

        assert response.status_code == 200
        assert "messages" in response.json()
        assert response.json()["total_tokens"] > 0

    def test_model_completion_with_fallback(self):
        # Test with fallback enabled
        response = requests.post(
            f"{self.BASE_URL}/models/completions",
            json={
                "prompt": "Test prompt for fallback",
                "enable_fallback": True
            },
            headers={"API Key": f"Bearer {self.API_KEY}"}
        )

        assert response.status_code == 200
        assert "success" in response.json()
        assert "fallback_used" in response.json()

if __name__ == "__main__":
    test = TestHermesAPI()
    test.test_conversation_flow()
    test.test_model_completion_with_fallback()
    print("All integration tests passed!")
```

### Load Testing

```python
import asyncio
import aiohttp
import time
import statistics
from concurrent.futures import ThreadPoolExecutor
import matplotlib.pyplot as plt

class LoadTester:
    def __init__(self, base_url, api_key):
        self.base_url = base_url
        self.api_key = api_key
        self.results = []

    async def make_request(self, prompt):
        start_time = time.time()

        async with aiohttp.ClientSession() as session:
            response = await session.post(
                f"{self.base_url}/models/completions",
                json={
                    "prompt": prompt,
                    "task_type": "chat_completion",
                    "max_tokens": 100
                },
                headers={
                    "Authorization": f"Bearer {self.api_key}"
                }
            )
            end_time = time.time()

            latency_ms = (end_time - start_time) * 1000
            self.results.append({
                "prompt_length": len(prompt),
                "latency_ms": latency_ms,
                "success": response.status_code == 200
            })

        return response.json()

    async def run_load_test(self, num_requests, concurrency=10):
        with ThreadPoolExecutor(max_workers=concurrency) as executor:
            tasks = []

            for i in range(num_requests):
                task = executor.submit(
                    asyncio.run,
                    self.make_request,
                    f"Test request {i}"
                )
                tasks.append(task)

            # Wait for all tasks to complete
            for task in tasks:
                task.result()

    def analyze_results(self):
        if not self.results:
            return

        latencies = [r['latency_ms'] for r in self.results]
        success_rate = sum(1 for r in self.results if r['success']) / len(self.results)

        print(f"Load Test Results:")
        print(f"Total requests: {len(self.results)}")
        print(f"Success rate: {success_rate:.1%}")
        print(f"Average latency: {statistics.mean(latencies):.1f}ms")
        self.create_latency_plot()

    def create_latency_plot(self):
        if not self.results:
            return

        latencies = [r['latency_ms'] for r in self.results]

        plt.figure(figsize=(12, 6))
        plt.subplot(1, 2, 1)
        plt.hist(latencies, bins=50, alpha=0.7, edgecolor='black')
        plt.title("Response Time Distribution")
        plt.xlabel("Latency (ms)")
        plt.ylabel("Frequency")

        plt.subplot(1, 2, 2)
        plt.plot(
            range(len(latencies)),
            sorted(latencies),
            alpha=0.8,
            color='blue',
            linewidth=2
        )
        plt.title("Response Time Trend")
        plt.xlabel("Request Number")
        plt.ylabel("Latency (ms)")

        plt.tight_layout()
        plt.savefig("load_test_results.png", dpi=300, bbox_inches=(12, 6))
        plt.show()

# Usage
async def main():
    tester = LoadTester(
        base_url="http://localhost:8000",
        api_key="test_key"
    )

    # Run load test
    await tester.run_load_test(num_requests=100, concurrency=10)
    tester.analyze_results()

if __name__ == "__main__":
    asyncio.run(main())
```

---

## Troubleshooting

### Common Issues

#### Connection Errors
```python
# Check network connectivity
import requests

def test_api_connection():
    try:
        response = requests.get(
            "https://api.hermes.ai/health",
            timeout=10
        )
        print(f"API Status: {response.status_code}")
        return True
    except requests.exceptions.RequestException as e:
        print(f"Connection Error: {e}")
        return False

# Check Redis connection
def test_redis_connection():
    import redis

    try:
        client = redis.Redis(host='localhost', port=6379, db=0)
        client.ping()
        print("Redis Status: Connected")
        return True
    except Exception as e:
        print(f"Redis Error: {e}")
        return False

# Run checks
print("Testing connections...")
api_ok = test_api_connection()
redis_ok = test_redis_connection()

if api_ok and redis_ok:
    print("✅ All connections successful")
else:
    print("❌ Connection issues found")
```

#### Performance Issues

```python
def diagnose_performance():
    import psutil

    # Check system resources
    cpu_percent = psutil.cpu_percent(interval=1)
    memory_percent = psutil.virtual_memory().percent
    disk_percent = psutil.disk_usage('/').percent

    print("System Resources:")
    print(f"  CPU: {cpu_percent:.1f}%")
    print(f" Memory: {memory_percent:.1f}%")
    print(f"  Disk: {disk_percent:.1f}%")

    # Check cache performance
    import redis
    client = redis.Redis()
    info = client.info()

    used_memory = info['used_memory']
    max_memory = info['maxmemory']
    memory_usage = (used_memory / max_memory) * 100

    print(f"\nCache Performance:")
    print(f"  Memory Usage: {memory_usage:.1f}%")
    print(f"  Connected Clients: {info['connected_clients']}")

    if cpu_percent > 80:
        print("⚠️  High CPU usage detected")
    if memory_percent > 85:
        print("⚠️  High memory usage detected")
    if disk_percent > 90:
        print("⚠️  High disk usage detected")

    # Check API performance
    import time
    start_time = time.time()
    response = requests.get("https://api.hem
    api_latency = (time.time() - start_time) * 1000

    print(f"\nAPI Performance:")
    print(f"  API Latency: {api_latency:.1f}ms")

    if api_latency > 1000:
        print("⚠️  High API latency detected")
```

### Memory Issues

```python
import gc
import tracemalloc
import time

def memory_analysis():
    print("Memory Analysis:")
    print(f"  Current process memory: {psutil.Process().memory_info().rss / 1024 / 1024:.1f} MB")

    # Get memory usage
    snapshot = tracemalloc.take_snapshot()

    # Find top memory consumers
    stats = snapshot.statistics('lineno')
    top_consumers = sorted(stats.items(), key=lambda x: x[1], reverse=True)[:10]

    print("\nTop Memory Consumers:")
    for filename, size in top_consumers:
        print(f"  {filename}: {size / 1024:.1f} KB")

    # Check for memory leaks
    gc.collect()
    after_gc = psutil.Process().memory_info().rss / 1024 / 1024
    before_gc = snapshot.total
    memory_freed = before_gc - after_gc

    print(f"\nMemory GC Results:")
    print(f"  Memory freed: {memory_freed / 1024:.1f} MB")

    # Recommendations
    if after_gc > 100:
        print("⚠️  High memory usage after GC - possible memory leak")
        print("  Consider reviewing code for memory leaks")
        print("  Use memory profiler to identify sources")

if __name__ == "__main__":
    memory_analysis()
```

### Debug Mode

```python
import logging
from hermes_sdk import HermesClient

# Enable debug logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Create debug client
client = HermesClient()

# Enable debug mode
client.config.debug = True
client.config.enable_tracing = True

# Enable verbose logging
logging.getLogger('hermes_sdk').setLevel(logging.DEBUG)

# Test with detailed logging
response = client.models.competions.create(
    prompt="Debug test",
    max_tokens=100
)

print(f"Response: {response.content}")
print(f"Debug info available in logs")
```

---

## Conclusion

This integration guide provides comprehensive guidance for integrating the Hermes AI Assistant platform with various systems and applications:

✅ **Quick Integration**: Get started in 5 minutes
✅ **SDK Integration**: Python SDK with examples
✅ **API Integration**: RESTful API examples
✅ **Third-Party**: Slack, Discord, Teams integrations
✅ **Configuration**: Environment setup and configuration
✅ **Examples**: Real-world use cases
✅ **Testing**: Unit, integration, and load testing
✅ **Troubleshooting**: Common issues and solutions

The Hermes AI Assistant platform is designed to be easily integrated into existing systems while providing powerful AI capabilities. The comprehensive documentation and SDKs make integration straightforward for developers of all experience levels.

**For additional support**, refer to the complete documentation suite:
- [Complete Platform Guide](HERMES_COMPLETE_GUIDE.md)
- [Architecture Overview](ARCHITECTURE_OVERVIEW.md)
- [Deployment Guide](DEPLOYMENT_GUIDE.md)
- [API Reference](API_REFERENCE.md)
- [Project Summary](PROJECT_SUMMARY.md)

The platform is ready for immediate integration and can be deployed in various environments from local development to global production. 🚀