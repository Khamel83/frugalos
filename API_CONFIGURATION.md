# FrugalOS API Configuration Guide

## 🔐 API Key Requirements

### Local Models (Ollama) - No API Keys Required ✅
- **llama3.1:8b-instruct**: Fully local, no authentication needed
- **qwen2.5-coder:7b**: Fully local, no authentication needed
- **Host**: `http://localhost:11434` (configurable via `OLLAMA_HOST`)

### Remote Models (OpenRouter) - Optional API Key
- **Purpose**: Fallback when local models fail or budget allows
- **Required**: `OPENROUTER_API_KEY` environment variable
- **Enable**: `FRUGAL_ALLOW_REMOTE=1` environment variable

## 🛠️ Configuration Options

### Option 1: Suit Mode (Default) - No API Keys
```bash
# Default configuration - local only
export FRUGAL_ALLOW_REMOTE=0  # or don't set
# No API keys needed

# Run with 0 budget (Suit Mode)
frugal run --project demo --goal "Extract data" --context file.txt --budget-cents 0
```

### Option 2: Remote Fallback - OpenRouter API Key
```bash
# Set OpenRouter API key
export OPENROUTER_API_KEY="sk-or-v1-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"

# Enable remote escalation
export FRUGAL_ALLOW_REMOTE=1

# Run with budget > 0
frugal run --project demo --goal "Extract data" --context file.txt --budget-cents 100
```

### Option 3: Custom Ollama Host
```bash
# Custom Ollama server
export OLLAMA_HOST="http://192.168.1.100:11434"

# Use with default settings
frugal run --project demo --goal "Extract data" --context file.txt --budget-cents 0
```

## 📋 Available Remote Models

### Free Models
- **open/free-demo-1**: $0.00 input/output (Privacy: P0)
  - No cost, full privacy
  - Limited availability/capabilities

### Paid Models
- **provider/flash-mini**: $0.25/$0.25 per 1M tokens (Privacy: P1)
  - Good balance of cost and performance
  - Suitable for extraction, summarization, light coding

- **provider/strong-pro**: $3.00/$15.00 per 1M tokens (Privacy: P1)
  - High performance for complex tasks
  - Best for extraction, summarization, coding

## 🔧 Environment Variables Reference

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `OLLAMA_HOST` | No | `http://localhost:11434` | Ollama server URL |
| `OPENROUTER_API_KEY` | No* | None | OpenRouter API key for remote models |
| `FRUGAL_ALLOW_REMOTE` | No | `0` | Enable remote model escalation (`1` = yes) |

*Required only if using remote models with budget > 0

## 🚀 Quick Start Commands

### Local Only (Recommended for testing)
```bash
# 1. Install and start Ollama
brew install ollama && ollama serve

# 2. Pull models
ollama pull llama3.1:8b-instruct
ollama pull qwen2.5-coder:7b

# 3. Test FrugalOS
frugal run --project demo --goal "Extract vendor" --context samples/receipt.txt --schema frugalos/schemas/invoice.json --budget-cents 0
```

### With Remote Fallback
```bash
# 1. Set up API key
export OPENROUTER_API_KEY="your-key-here"
export FRUGAL_ALLOW_REMOTE=1

# 2. Run with budget
frugal run --project demo --goal "Extract vendor" --context samples/receipt.txt --schema frugalos/schemas/invoice.json --budget-cents 50
```

## 🔒 Security Considerations

### API Key Security
- Store API keys in environment variables, not in code
- Use `.env` files for development (add to `.gitignore`)
- Rotate keys regularly for production use
- Monitor usage on OpenRouter dashboard

### Privacy Levels
- **P0**: Full privacy (local Ollama models)
- **P1**: Shared privacy (OpenRouter models - data used for training)
- **P2**: No privacy guarantees (not currently used)

### Budget Protection
- Default: 0 cents (Suit Mode) - prevents accidental charges
- Remote escalation requires explicit budget > 0
- Minimum remote budget: 1 cent
- Always test locally first

## 📊 Cost Estimation

### Local Models
- **Cost**: $0.00 (free)
- **Hardware**: Local compute resources
- **Privacy**: 100% (no data leaves your machine)

### Remote Models (example costs)
- **Flash Mini**: ~$0.50 for 1M tokens (typical receipt extraction)
- **Strong Pro**: ~$18 for 1M tokens (complex analysis tasks)

## ✅ Validation Checklist

- [ ] Ollama installed and running: `curl http://localhost:11434/api/tags`
- [ ] Models pulled: `ollama list`
- [ ] Local test working: `frugal run --budget-cents 0`
- [ ] Optional: OpenRouter key set: `echo $OPENROUTER_API_KEY`
- [ ] Optional: Remote test working: `frugal run --budget-cents 10`

---

**Status**: ✅ FrugalOS is ready for both local-only and hybrid configurations