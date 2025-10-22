# FRUGALOS_BOOTSTRAP.md

Feed this file to your code agent (Claude Code, etc.) to scaffold the repo.

## Repo goals
- Local-first ($0) Suit Mode on Mac (Ollama).
- k-sample + schema/consensus validation.
- Project-level budget (pennies), oracles (stubbed).
- CLI: `frugal run`, `frugal receipts`, `frugal oracle`.

## Create files
- `pyproject.toml` (setuptools script entry `frugal`)
- `frugalos/` package with:
  - `cli.py`, `runner.py`, `ledger.py`
  - `local/ollama_adapter.py`
  - `validators/{schema.py,consensus.py}`
  - `oracle/{update.py,routing_table.json}`
  - `policy.yaml`, `clarifier_prompt.md`, `schemas/invoice.json`
- `README.md`, `LICENSE`, `.gitignore`, `.github/workflows/ci.yml`

## Usage
- `brew install ollama && ollama pull llama3.1:8b-instruct`
- `python -m venv .venv && source .venv/bin/activate && pip install -e .`
- `frugal run --goal "Extract vendor and total" --context samples/receipt.txt --schema frugalos/schemas/invoice.json --budget-cents 0`
