"""
====================================================================
Smart Civic Guardian - SQLite to Supabase PostgreSQL Migrator
Migrates all existing records from local SQLite (civic_guardian.db)
to Supabase PostgreSQL without data loss.
====================================================================
Usage:
    set DATABASE_URL=postgresql://postgres:[PASSWORD]@[HOST]:5432/postgres
    python database/migrate_to_supabase.py
"""

import os
import sqlite3
import sys

try:
    import psycopg2
    import psycopg2.extras
except ImportError:
    print("Please install psycopg2: pip install psycopg2-binary")
    sys.exit(1)

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "civic_guardian.db")
DATABASE_URL = os.environ.get("DATABASE_URL")

if not DATABASE_URL:
    print("ERROR: DATABASE_URL environment variable is required.")
    print("Example: postgresql://postgres:password@db.xxx.supabase.co:5432/postgres")
    sys.exit(1)

if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = "postgresql://" + DATABASE_URL[len("postgres://"):]

print("Connecting to local SQLite database...")
sqlite_conn = sqlite3.connect(DB_PATH)
sqlite_conn.row_factory = sqlite3.Row

print("Connecting to Supabase PostgreSQL database...")
pg_conn = psycopg2.connect(DATABASE_URL)
pg_cur = pg_conn.cursor()

TABLES = [
    ("users", ["id", "name", "email", "phone", "password_hash", "role", "age", "description", "created_at"]),
    ("authorities", ["id", "user_id", "department", "designation"]),
    ("complaints", [
        "id", "user_id", "category", "ai_detected_category", "ai_confidence",
        "description", "photo_path", "latitude", "longitude", "location_name",
        "priority", "status", "duplicate_of", "duplicate_group", "support_count",
        "assigned_to", "resolution_notes", "resolved_photo_path", "created_at",
        "updated_at", "resolved_at"
    ]),
    ("notifications", ["id", "user_id", "complaint_id", "message", "is_read", "created_at"]),
    ("feedback", ["id", "complaint_id", "user_id", "rating", "comment", "created_at"]),
    ("password_resets", ["id", "user_id", "token", "expires_at", "used"]),
    ("contact_messages", ["id", "user_id", "name", "email", "department", "message", "reply_text", "replied_at", "submitted_at"]),
]

for table, cols in TABLES:
    rows = sqlite_conn.execute(f"SELECT * FROM {table}").fetchall()
    print(f"Migrating table '{table}': {len(rows)} records found...")
    for row in rows:
        row_dict = dict(row)
        col_names = [c for c in cols if c in row_dict]
        placeholders = ", ".join(["%s"] * len(col_names))
        col_str = ", ".join(col_names)
        vals = [row_dict[c] for c in col_names]

        sql = f"INSERT INTO {table} ({col_str}) VALUES ({placeholders}) ON CONFLICT (id) DO NOTHING"
        pg_cur.execute(sql, vals)
    pg_conn.commit()

# Reset serial sequences for PostgreSQL
for table, _ in TABLES:
    try:
        pg_cur.execute(f"SELECT setval(pg_get_serial_sequence('{table}', 'id'), COALESCE(MAX(id), 1)) FROM {table};")
        pg_conn.commit()
    except Exception:
        pg_conn.rollback()

print("All tables and records migrated successfully to Supabase PostgreSQL!")
sqlite_conn.close()
pg_conn.close()

