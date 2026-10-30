"""One-time fix: makes an older database file match what the code needs.
Run from the project folder:  python database\\add_missing_columns.py
Safe to run more than once. Your data is kept."""
import os, sqlite3

DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "civic_guardian.db")
NEEDED = {
    "users": [("age", "INTEGER"), ("description", "TEXT")],
    "contact_messages": [("department", "TEXT")],
}

conn = sqlite3.connect(DB)
for table, cols in NEEDED.items():
    have = [r[1] for r in conn.execute(f"PRAGMA table_info({table})")]
    if not have:
        print(f"Table {table} is missing - copy the full schema.sql and restart the app once.")
        continue
    for name, typ in cols:
        if name in have:
            print(f"{table}.{name} already exists")
        else:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {name} {typ}")
            print(f"Added {table}.{name}")

# contact_messages.user_id must allow empty values (visitors who are not logged in)
info = list(conn.execute("PRAGMA table_info(contact_messages)"))
uid = [r for r in info if r[1] == "user_id"]
if uid and uid[0][3] == 1:  # notnull flag
    conn.executescript("""
        ALTER TABLE contact_messages RENAME TO contact_messages_old;
        CREATE TABLE contact_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            name TEXT NOT NULL,
            email TEXT NOT NULL,
            department TEXT,
            message TEXT NOT NULL,
            reply_text TEXT,
            replied_at TIMESTAMP,
            submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );
        INSERT INTO contact_messages (id, user_id, name, email, department, message, reply_text, replied_at, submitted_at)
            SELECT id, user_id, name, email, department, message, reply_text, replied_at, submitted_at
            FROM contact_messages_old;
        DROP TABLE contact_messages_old;
    """)
    print("Rebuilt contact_messages so user_id can be empty (data kept)")
else:
    print("contact_messages.user_id already allows empty values")
conn.commit()
conn.close()
print("Done.")
