"""
Database migration script for adding prompt optimization tracking.

This script adds the new fields needed for tracking template versions,
validation errors, and consensus votes to support prompt optimization.
"""

from __future__ import annotations
import sqlite3
from pathlib import Path

DB = Path("out/receipts.sqlite")
DB.parent.mkdir(parents=True, exist_ok=True)

def migrate_receipts_db():
    """Migrate the receipts database to add prompt optimization fields."""
    con = sqlite3.connect(DB)
    cursor = con.cursor()

    # Check if template_version column exists
    cursor.execute("PRAGMA table_info(receipts)")
    columns = [row[1] for row in cursor.fetchall()]

    # Add new columns if they don't exist
    if "template_version" not in columns:
        print("Adding template_version column...")
        cursor.execute("ALTER TABLE receipts ADD COLUMN template_version TEXT DEFAULT '1.0'")

    if "validation_errors" not in columns:
        print("Adding validation_errors column...")
        cursor.execute("ALTER TABLE receipts ADD COLUMN validation_errors TEXT")

    if "consensus_votes" not in columns:
        print("Adding consensus_votes column...")
        cursor.execute("ALTER TABLE receipts ADD COLUMN consensus_votes TEXT")

    # Create new tables for prompt optimization
    print("Creating prompt_templates table...")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS prompt_templates (
            version TEXT PRIMARY KEY,
            created_at INTEGER DEFAULT (strftime('%s', 'now')),
            template_json TEXT NOT NULL,
            parent_version TEXT,
            improvement_reason TEXT,
            is_active INTEGER DEFAULT 0,
            performance_metrics TEXT
        )
    """)

    print("Creating prompt_examples table...")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS prompt_examples (
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
        )
    """)

    # Create indexes for better query performance
    print("Creating indexes...")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_receipts_template_version ON receipts(template_version)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_receipts_project_ts ON receipts(project, ts)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_examples_project ON prompt_examples(project)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_examples_quality ON prompt_examples(quality_score)")

    con.commit()
    con.close()
    print("Migration completed successfully!")

if __name__ == "__main__":
    migrate_receipts_db()