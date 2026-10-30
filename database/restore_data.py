import sqlite3

conn = sqlite3.connect('database/civic_guardian.db')
with open('database/backup_data.sql', 'r') as f:
    lines = f.readlines()

insert_statements = [line for line in lines if line.strip().upper().startswith('INSERT')]

cursor = conn.cursor()
for stmt in insert_statements:
    try:
        cursor.execute(stmt)
    except sqlite3.IntegrityError as e:
        print(f"Skipped (already exists): {e}")

conn.commit()
conn.close()
print("Data restored!")