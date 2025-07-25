import sqlite3

conn = sqlite3.connect('chat.db')
conn.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL
    )
''')
conn.execute('''
    CREATE TABLE IF NOT EXISTS messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT NOT NULL,
        msg TEXT NOT NULL,
        timestamp TEXT NOT NULL
    )
''')
conn.commit()
conn.close()
print("Database initialized.")
