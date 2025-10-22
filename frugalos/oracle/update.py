from __future__ import annotations
import json, time
from pathlib import Path

ORACLE_PATH = Path(__file__).parent / "routing_table.json"

def load_routing_table() -> dict:
    if ORACLE_PATH.exists():
        return json.loads(ORACLE_PATH.read_text())
    # default minimal table
    return {"updated_at": int(time.time()), "models": [{
        "id":"provider/flash-mini", "price_in":0.25, "price_out":0.25, "privacy":"P1", "viability":{"extract":8,"summarize":7,"code":6}
    }]}

def update_oracle_if_needed(force: bool=False):
    # Placeholder: in real impl, fetch OpenRouter model list and free promos daily; write to ORACLE_PATH
    if force or not ORACLE_PATH.exists():
        tbl = load_routing_table()
        ORACLE_PATH.write_text(json.dumps(tbl, indent=2))
