# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

### Installation and Setup
```bash
# Install dependencies in development mode
pip install -e .

# Install external dependency: Ollama (required for local models)
brew install ollama
ollama pull llama3.1:8b-instruct
ollama pull qwen2.5-coder:7b
```

### Testing and Validation
```bash
# Basic package import test (from CI)
python -m pip install -e .
python - <<'PY'
import importlib; import frugalos
print("OK", frugalos.__version__)
PY

# Run CLI commands for testing
frugal run --project demo --goal "Extract vendor and total from receipts" --context samples/receipt.txt --schema frugalos/schemas/invoice.json --budget-cents 0
frugal receipts --project demo
frugal oracle --show
```

### Building and Distribution
```bash
# Build package (setuptools)
python -m build
```

## Architecture Overview

FrugalOS is a **local-first budgeted job runner** for LLM tasks with a tiered routing system:

### Core Components

**CLI Entry Point** (`frugalos/cli.py:67`):
- `frugal run` - Execute jobs with budget constraints and validation
- `frugal receipts` - Display project job history and costs
- `frugal oracle` - Manage routing tables and model availability

**Job Runner** (`frugalos/runner.py:21`):
- Implements k-sample consensus validation (3 samples by default)
- Schema validation using jsonschema
- Local-first approach: T1 (Ollama) → T2 (remote, if allowed)
- Automatic retry with context compression

**Configuration System** (`frugalos/policy.yaml:1`):
- Models: T1_text (llama3.1:8b-instruct), T1_code (qwen2.5-coder:7b), T2_default (OpenRouter)
- Routing: consensus_threshold=0.67, k_samples=3
- Privacy levels P0-P2, budget controls

**Data Persistence** (`frugalos/ledger.py:18`):
- SQLite-based receipt tracking (`out/receipts.sqlite`)
- Project-based cost and latency monitoring
- Job history with tier/model path metadata

### Key Design Patterns

**Budget Enforcement**:
- Default Suit Mode ($0) with local-only execution
- Remote escalation only when `FRUGAL_ALLOW_REMOTE=1` and budget > 0
- Oracle system for model pricing and availability

**Validation Pipeline**:
1. Schema validation (JSON schema compliance)
2. Consensus validation (majority vote across k samples)
3. Privacy level enforcement
4. Cost constraint checking

**Local-First Routing**:
- T1: Local Ollama models (free, private)
- T2: Remote models (paid, based on oracle pricing)
- Fallback and retry logic with graceful degradation

### External Dependencies

- **Ollama**: Required for local model inference
- **SQLite**: For receipt and job history storage
- **JSON Schema**: For output validation
- **Typer/Rich**: CLI framework and formatted output

### File Structure Conventions

- Jobs output to `out/{project}/{job_id}/`
- Receipts stored in SQLite database
- Configuration in `frugalos/policy.yaml`
- Model adapters in `frugalos/local/` and `frugalos/oracle/`
- Validators in `frugalos/validators/`

### Environment Variables

- `FRUGAL_ALLOW_REMOTE=1`: Enable remote model escalation
- All other configuration via `policy.yaml` file