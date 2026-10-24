"""One-time migration for Day 29: rejection reason and review time.

Run from the backend folder with the venv active:
    python migrate_day29.py

It is safe to run twice. It also moves old "[Rejected: ...]" text out of the
purpose field into the new rejection_reason column.
"""
import re
import sqlite3

conn = sqlite3.connect("portal.db")
cols = {row[1] for row in conn.execute("PRAGMA table_info(resource_requests)")}

if "rejection_reason" not in cols:
    conn.execute("ALTER TABLE resource_requests ADD COLUMN rejection_reason TEXT")
    print("added rejection_reason")
if "reviewed_at" not in cols:
    conn.execute("ALTER TABLE resource_requests ADD COLUMN reviewed_at DATETIME")
    print("added reviewed_at")

pattern = re.compile(r"\s*\[Rejected:\s*(.*?)\s*\]\s*$", re.S)
moved = 0
for rid, purpose in conn.execute(
    "SELECT id, purpose FROM resource_requests WHERE purpose LIKE '%[Rejected:%'"
).fetchall():
    m = pattern.search(purpose or "")
    if not m:
        continue
    clean = pattern.sub("", purpose).strip() or None
    conn.execute(
        "UPDATE resource_requests SET purpose = ?, rejection_reason = ? WHERE id = ?",
        (clean, m.group(1), rid),
    )
    moved += 1

conn.commit()
print(f"done, {moved} old rejection note(s) moved")