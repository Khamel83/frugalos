# FrugalOS

Local-first **budgeted job runner** for LLM tasks. **Suit Mode ($0)** by default: runs small models via Ollama,
verifies with schema/consensus, and only escalates to free/paid endpoints when allowed.

## Quick start
1) Install Python 3.11+ and Ollama. Pull a local model:
   ```bash
   brew install ollama
   ollama pull llama3.1:8b-instruct
   ```
2) Create venv & install:
   ```bash
   python -m venv .venv && source .venv/bin/activate
   pip install -e .
   ```
3) Run Suit Mode ($0):
   ```bash
   frugal run --project demo --goal "Extract vendor and total from receipts"      --context samples/receipt.txt --schema frugalos/schemas/invoice.json --budget-cents 0
   ```
4) Show receipts:
   ```bash
   frugal receipts --project demo
   ```

## Notes
- Remote routing (OpenRouter) is stubbed; enable by setting `FRUGAL_ALLOW_REMOTE=1` and implementing adapters.
- Daily/Weekly oracles are included as placeholders; you can wire API calls later.
