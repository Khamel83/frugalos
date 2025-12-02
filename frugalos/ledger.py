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
        tier TEXT, model_path TEXT, why TEXT, template_version TEXT DEFAULT '1.0',
        validation_errors TEXT, consensus_votes TEXT
    )""")

    # Create optimization tables
    con.execute("""CREATE TABLE IF NOT EXISTS prompt_templates (
        version TEXT PRIMARY KEY,
        created_at INTEGER DEFAULT (strftime('%s', 'now')),
        template_json TEXT NOT NULL,
        parent_version TEXT,
        improvement_reason TEXT,
        is_active INTEGER DEFAULT 0,
        performance_metrics TEXT
    )""")

    con.execute("""CREATE TABLE IF NOT EXISTS prompt_examples (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        job_id TEXT NOT NULL,
        project TEXT NOT NULL,
        input_goal TEXT,
        input_context TEXT,
        output_json TEXT,
        schema_path TEXT,
        quality_score REAL,
        consensus_agreement REAL,
        created_at INTEGER DEFAULT (strftime('%s', 'now')),
        used_count INTEGER DEFAULT 0
    )""")

    # Create indexes for performance
    con.execute("CREATE INDEX IF NOT EXISTS idx_receipts_template_version ON receipts(template_version)")
    con.execute("CREATE INDEX IF NOT EXISTS idx_receipts_project_ts ON receipts(project, ts)")
    con.execute("CREATE INDEX IF NOT EXISTS idx_examples_project ON prompt_examples(project)")
    con.execute("CREATE INDEX IF NOT EXISTS idx_examples_quality ON prompt_examples(quality_score)")

    con.commit()
    return con

class Receipts:
    def __init__(self, project: str):
        self.project = project
        self.con = _ensure()

    def save(self, job_id: str, cost_cents: int, latency_s: float, tier: str, model_path: str, why: str,
              template_version: str = "1.0", validation_errors: str = "", consensus_votes: str = ""):
        self.con.execute("""INSERT INTO receipts(ts,project,job_id,cost_cents,latency_s,tier,model_path,why,template_version,validation_errors,consensus_votes)
                           VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
                         (int(time.time()), self.project, job_id, cost_cents, float(latency_s), tier, model_path, why,
                          template_version, validation_errors, consensus_votes))
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

    def save_successful_example(self, job_id: str, goal: str, context: str, output: str,
                                 schema_path: str = "", quality_score: float = 0.0,
                                 consensus_agreement: float = 0.0):
        """Save a successful job as a few-shot example.

        Args:
            job_id: Job identifier
            goal: Input goal
            context: Input context
            output: Output JSON
            schema_path: Path to schema used
            quality_score: Quality assessment score
            consensus_agreement: Consensus agreement score
        """
        self.con.execute("""INSERT INTO prompt_examples(job_id,project,input_goal,input_context,output_json,schema_path,quality_score,consensus_agreement)
                           VALUES(?,?,?,?,?,?,?,?,?)""",
                         (job_id, self.project, goal, context, output, schema_path, quality_score, consensus_agreement))
        self.con.commit()

    def get_best_examples(self, max_examples: int = 3, min_quality: float = 0.8, days_old: int = 7):
        """Get best examples for few-shot learning.

        Args:
            max_examples: Maximum number of examples to return
            min_quality: Minimum quality threshold
            days_old: Maximum age of examples in days

        Returns:
            List of example dictionaries
        """
        cutoff_time = int(time.time()) - (days_old * 24 * 3600)
        cur = self.con.execute("""SELECT input_goal, input_context, output_json, quality_score
                                  FROM prompt_examples
                                  WHERE project=? AND quality_score>=? AND created_at>?
                                  ORDER BY quality_score DESC, used_count ASC
                                  LIMIT ?""",
                               (self.project, min_quality, cutoff_time, max_examples))

        examples = []
        for row in cur.fetchall():
            examples.append({
                "input": row[0],  # goal
                "context": row[1],
                "output": row[2]
            })
        return examples

    def get_failure_patterns(self, hours: int = 24):
        """Analyze recent failure patterns for optimization.

        Args:
            hours: Number of hours to look back

        Returns:
            Dictionary with failure statistics
        """
        cutoff_time = int(time.time()) - (hours * 3600)
        cur = self.con.execute("""SELECT template_version, why, validation_errors, COUNT(*)
                                  FROM receipts
                                  WHERE project=? AND ts>? AND (why LIKE '%limit%' OR why LIKE '%retry_ok%')
                                  GROUP BY template_version, why, validation_errors
                                  ORDER BY COUNT(*) DESC""",
                               (self.project, cutoff_time))

        patterns = {}
        for row in cur.fetchall():
            template_ver, why, validation_errors, count = row
            if template_ver not in patterns:
                patterns[template_ver] = {}
            patterns[template_ver][why] = {
                "validation_errors": validation_errors,
                "count": count
            }

        return patterns
