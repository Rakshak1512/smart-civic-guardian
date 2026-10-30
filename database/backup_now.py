import sqlite3

conn = sqlite3.connect('database/civic_guardian.db')
with open('database/backup_data.sql', 'w') as f:
    for line in conn.iterdump():
        f.write(f'{line}\n')
conn.close()
print("Backup done!")