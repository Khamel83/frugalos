from __future__ import annotations
import sqlite3, time, json
from pathlib import Path

DB = Path("out/receipts.sqlite")
DB.parent.mkdir(parents=True, exist_ok=True)

def _ensure():
    con = sqlite3.connect(DB)
    con.execute("""CREATE TABLE IF NOT EXISTS receipts(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts INTEGER, project TEXT, job_id TEXT, cost_cents INTEGER, latency_s REAL,
        tier TEXT, model_path TEXT, why TEXT
    )""")
    con.commit()
    return con

class Receipts:
    def __init__(self, project: str):
        self.project = project
        self.con = _ensure()

    def save(self, job_id: str, cost_cents: int, latency_s: float, tier: str, model_path: str, why: str):
        self.con.execute("INSERT INTO receipts(ts,project,job_id,cost_cents,latency_s,tier,model_path,why) VALUES(?,?,?,?,?,?,?,?)",
                         (int(time.time()), self.project, job_id, cost_cents, float(latency_s), tier, model_path, why))
        self.con.commit()

    def last(self):
        cur = self.con.execute("SELECT ts,project,job_id,cost_cents,latency_s,tier,model_path,why FROM receipts ORDER BY id DESC LIMIT 1")
        row = cur.fetchone()
        if not row: return {}
        keys = ["when","project","job_id","cost_cents","latency_s","tier","model_path","why"]
        d = dict(zip(keys, row))
        d["when"] = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(d["when"]))
        return d

    def tail(self, n: int=50):
        cur = self.con.execute("SELECT ts,job_id,cost_cents,latency_s,tier,model_path,why FROM receipts WHERE project=? ORDER BY id DESC LIMIT ?",
                               (self.project, n))
        rows = []
        for row in cur.fetchall():
            d = {"when": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(row[0])),
                 "job_id": row[1], "cost_cents": row[2], "latency_s": row[3], "tier": row[4],
                 "model_path": row[5], "why": row[6]}
            rows.append(d)
        return rows
