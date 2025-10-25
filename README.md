# Hermes - Backend-Agnostic Personal AI Assistant

Hermes is a comprehensive, production-ready AI assistant system with backend-agnostic architecture, meta-learning capabilities, and autonomous operation. Built for flexibility, reliability, and intelligent task execution.

## ✨ Features

### 🎯 Core Capabilities
- **Backend-Agnostic Architecture**: Swap between local (Ollama), remote, or any AI backend seamlessly
- **Local-First Execution**: Privacy-focused local AI processing with Ollama integration
- **Meta-Learning System**: Intelligent question generation and pattern recognition
- **Autonomous Operation**: Process ideas without manual intervention
- **Job Queue Management**: Asynchronous task processing with priority support

### 🛡️ Production-Ready Features
- **Intelligent Retry System**: Exponential backoff with circuit breakers
- **Comprehensive Error Handling**: Categorized error tracking and recovery
- **Real-Time Notifications**: Telegram integration for job and system alerts
- **System Monitoring**: CPU, memory, disk, and application metrics
- **Database Persistence**: Complete job history and audit trail

### 📊 Monitoring & Observability
- **Real-time metrics collection** (CPU, memory, disk usage)
- **Application performance tracking** (job throughput, error rates)
- **Configurable alerting** with threshold-based triggers
- **Web dashboard** with live metrics and charts
- **Comprehensive logging** with rotation and retention

## 🚀 Quick Start

### Prerequisites

- Python 3.8+
- [Ollama](https://ollama.ai) installed and running
- Local models pulled:
  ```bash
  ollama pull llama3.1:8b-instruct
  ollama pull qwen2.5-coder:7b
  ```

### Installation

```bash
# Install dependencies
pip install -e .
pip install -r requirements.txt

# Copy environment configuration
cp .env.example .env
# Edit .env with your settings

# Initialize database
python run_hermes.py --init-db
```

### Running Hermes

```bash
# Start Hermes server
python run_hermes.py

# Or with custom settings
python run_hermes.py --host 0.0.0.0 --port 5000 --debug
```

The web interface will be available at `http://localhost:5000`

## 📖 Usage

### Web Interface

1. **Submit Ideas**: Navigate to `http://localhost:5000` and submit your ideas
2. **Monitor Progress**: Check real-time job status and system metrics
3. **View Dashboard**: Access `http://localhost:5000/dashboard` for detailed metrics

### API Usage

```python
import requests

# Submit a job
response = requests.post('http://localhost:5000/api/submit', json={
    'idea': 'Write a Python script to analyze log files'
})
job_id = response.json()['job_id']

# Check job status
status = requests.get(f'http://localhost:5000/api/jobs/{job_id}')
print(status.json())

# Get system metrics
metrics = requests.get('http://localhost:5000/api/metrics')
print(metrics.json())
```

## 🏗️ Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Web Interface │    │  Job Queue       │    │ Local Execution │
│   (Flask)       │◄──►│  (Retry Logic)   │◄──►│  (Ollama)       │
└─────────────────┘    └──────────────────┘    └─────────────────┘
         │                       │                       │
         ▼                       ▼                       ▼
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Notifications │    │   Error Handler  │    │   Monitoring    │
│   (Telegram)    │    │   (Categorized)  │    │   (Metrics)     │
└─────────────────┘    └──────────────────┘    └─────────────────┘
         │                       │                       │
         └───────────────────────┼───────────────────────┘
                                 ▼
                       ┌─────────────────┐
                       │   Database      │
                       │  (SQLite)       │
                       └─────────────────┘
```

## 📊 API Endpoints

### Job Management
- `POST /api/submit` - Submit new idea
- `GET /api/jobs` - List recent jobs
- `GET /api/jobs/<id>` - Get job details
- `GET /api/jobs/<id>/events` - Stream job events (SSE)

### System Status
- `GET /api/status` - System status and components
- `GET /health` - Health check endpoint
- `GET /api/metrics` - Current system metrics
- `GET /api/metrics/history` - Historical metrics
- `GET /api/alerts` - Recent monitoring alerts

## 🧪 Testing

Run the comprehensive test suite:

```bash
python tests/test_hermes.py
```

## 📝 Configuration

Edit `hermes/config.yaml` or use environment variables (`.env.example`):

```yaml
hermes:
  port: 5000
  allow_remote: false  # Enable remote execution
  timeout: 300         # Job timeout in seconds

notifications:
  telegram:
    enabled: true
    bot_token: "YOUR_BOT_TOKEN"
    chat_id: "YOUR_CHAT_ID"

monitoring:
  collection_interval: 60
  thresholds:
    cpu:
      warning: 80.0
      critical: 95.0
```

## 📄 License

MIT License

---

**Made with ❤️ for the local-first AI community**
