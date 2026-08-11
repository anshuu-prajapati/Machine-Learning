"""
migrate_db.py — One-time fix: adds missing columns to existing clip_downloads table
Run once:  python migrate_db.py
"""
import sqlite3
from pathlib import Path

DB_PATH = str(Path(__file__).with_name("clip_downloads.db"))

NEW_COLUMNS = [
    ("s3_key",      "TEXT"),
    ("preview_url", "TEXT"),
]

conn = sqlite3.connect(DB_PATH)
cur  = conn.execute("PRAGMA table_info(clip_downloads)")
existing = {row[1] for row in cur.fetchall()}

for col, col_type in NEW_COLUMNS:
    if col not in existing:
        conn.execute(f"ALTER TABLE clip_downloads ADD COLUMN {col} {col_type}")
        print(f"  ✅ Added column: {col}")
    else:
        print(f"  ✓  Already exists: {col}")

conn.commit()
conn.close()
print("\nDone — DB is up to date.")