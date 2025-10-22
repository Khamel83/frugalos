# FrugalOS Ollama Integration Checklist

## ✅ System Validation Status

### Core Components (All ✅)
- [x] Package installation and dependencies
- [x] CLI commands (`frugal run`, `frugal receipts`, `frugal oracle`)
- [x] Policy configuration (`frugalos/policy.yaml`)
- [x] Oracle routing table with 3 models available
- [x] Schema validation system
- [x] Consensus validation (k=3, threshold=0.67)
- [x] Receipt database (SQLite)
- [x] Budget enforcement system
- [x] Error handling and graceful degradation

### Ollama Configuration
- [x] Adapter configured for `http://localhost:11434`
- [x] Models specified: `llama3.1:8b-instruct`, `qwen2.5-coder:7b`
- [x] Connection handling (fails gracefully when Ollama unavailable)

## 🚀 Ollama Setup Instructions

### 1. Install Ollama
```bash
# macOS
brew install ollama

# Linux
curl -fsSL https://ollama.ai/install.sh | sh

# Start service
ollama serve
```

### 2. Pull Required Models
```bash
ollama pull llama3.1:8b-instruct    # T1_text model
ollama pull qwen2.5-coder:7b         # T1_code model
```

### 3. Verify Installation
```bash
# Check models
ollama list

# Test basic inference
ollama run llama3.1:8b-instruct "Say hello"

# Verify API endpoint
curl http://localhost:11434/api/tags
```

### 4. Test FrugalOS Integration
```bash
# Basic test with sample data
frugal run --project demo \
  --goal "Extract vendor and total from receipts" \
  --context samples/receipt.txt \
  --schema frugalos/schemas/invoice.json \
  --budget-cents 0

# Check results
frugal receipts --project demo
```

## 🔑 Optional Remote Setup

### OpenRouter Integration (Optional)
```bash
# Set API key for remote models
export OPENROUTER_API_KEY="your-key-here"
export FRUGAL_ALLOW_REMOTE=1

# Test with budget
frugal run --project demo \
  --goal "Extract vendor from receipt" \
  --context samples/receipt.txt \
  --schema frugalos/schemas/invoice.json \
  --budget-cents 100
```

### Available Remote Models
- `open/free-demo-1`: $0.00 (Free, P0 privacy)
- `provider/flash-mini`: $0.25/$0.25 (P1 privacy)
- `provider/strong-pro`: $3.00/$15.00 (P1 privacy)

## 🧪 Validation Tests

### Pre-Ollama Tests (All ✅)
- [x] Package imports: `python3 -c "import frugalos; print(frugalos.__version__)"`
- [x] CLI help: `frugal --help`
- [x] Oracle routing: `frugal oracle --show`
- [x] Receipts database: `frugal receipts --project demo`
- [x] Schema validation: Tested with invoice schema
- [x] Consensus mechanism: Tested with k=3 samples

### Post-Ollama Tests
- [ ] Ollama connectivity: `curl http://localhost:11434/api/tags`
- [ ] Model availability: `ollama list`
- [ ] End-to-end job: `frugal run --project demo --goal "test" --context samples/receipt.txt`
- [ ] Receipt generation: `frugal receipts --project demo`
- [ ] Budget enforcement: Try with `--budget-cents 0`
- [ ] Remote escalation: Try with `--budget-cents 100` and API key

## 📊 Current Configuration

### Policy Settings
```yaml
models:
  T1_text: {provider: ollama, name: "llama3.1:8b-instruct", temp: 0.2}
  T1_code: {provider: ollama, name: "qwen2.5-coder:7b", temp: 0.1}
  T2_default: {provider: openrouter, name: "provider/flash-mini", temp: 0.2}

routing:
  k_samples: 3
  consensus_threshold: 0.67
  max_retries_T1: 1
  require_schema_valid: true

budgets:
  default_project_cents: 0    # Suit Mode (local-only)
  min_remote_cent: 1          # Minimum for remote escalation
```

### Privacy Levels
- **P0**: Full privacy (local models)
- **P1**: Shared privacy (some remote models)
- **P2**: No privacy guarantees

## ✨ Next Steps

1. **Immediate**: Install Ollama and pull models
2. **Optional**: Configure OpenRouter for remote fallback
3. **Testing**: Run end-to-end validation tests
4. **Production**: Consider budget limits and monitoring

---

**Status**: ✅ Ready for Ollama implementation
**Last Updated**: $(date)