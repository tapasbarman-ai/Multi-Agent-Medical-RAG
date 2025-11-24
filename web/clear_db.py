import sqlite3
import os

DB_PATH = 'web/chat_history.db'

if os.path.exists(DB_PATH):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute('DELETE FROM messages')
    cursor.execute('DELETE FROM chats')

    conn.commit()
    conn.close()

    print("✅ Database cleared successfully!")
else:
    print(f"❌ Database not found at {DB_PATH}")