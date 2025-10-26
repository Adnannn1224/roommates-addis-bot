import sqlite3
import os

DB_PATH = '/data/roommates.db'

def init_db():
    os.makedirs('/data', exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        name TEXT, photo_path TEXT, location TEXT,
        num_roommates INTEGER, gender TEXT, religion TEXT,
        age INTEGER, budget REAL, bio TEXT,
        looking_for TEXT,
        pending_requests TEXT DEFAULT '',
        matches TEXT DEFAULT ''
    )
    ''')
    conn.commit()
    conn.close()

if __name__ == '__main__':
    init_db()
    print("DB ready at /data/roommates.db")