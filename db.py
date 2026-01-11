# db.py
import sqlite3
import datetime

conn = sqlite3.connect('vpn_bot.db', check_same_thread=False)
cursor = conn.cursor()

# Создание таблиц, если не существуют
cursor.execute('''
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY,
    username TEXT
)
''')

cursor.execute('''
CREATE TABLE IF NOT EXISTS keys (
    user_id INTEGER,
    uuid TEXT UNIQUE,
    sid TEXT,
    start_date DATETIME,
    end_date DATETIME,
    FOREIGN KEY (user_id) REFERENCES users(id)
)
''')

cursor.execute('''
CREATE TABLE IF NOT EXISTS payments (
    user_id INTEGER,
    plan_key TEXT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    status TEXT DEFAULT 'pending',
    FOREIGN KEY (user_id) REFERENCES users(id)
)
''')

conn.commit()

def add_user(uid, username):
    cursor.execute("INSERT OR IGNORE INTO users (id, username) VALUES (?, ?)", (uid, username))
    conn.commit()

def add_key(user_id, u_uuid, sid, days):
    start_date = datetime.datetime.now()
    end_date = start_date + datetime.timedelta(days=days)
    cursor.execute("INSERT INTO keys (user_id, uuid, sid, start_date, end_date) VALUES (?, ?, ?, ?, ?)",
                   (user_id, u_uuid, sid, start_date, end_date))
    conn.commit()

def get_keys(user_id):
    cursor.execute("SELECT * FROM keys WHERE user_id = ? AND end_date > DATETIME('now')", (user_id,))
    return cursor.fetchall()

def get_keys_with_expiry(user_id):
    cursor.execute("SELECT uuid, end_date FROM keys WHERE user_id = ? AND end_date > DATETIME('now')", (user_id,))
    return cursor.fetchall()

def get_all_expired_keys():
    cursor.execute("SELECT user_id, uuid FROM keys WHERE end_date < DATETIME('now')")
    return cursor.fetchall()

def delete_key_by_uuid(u_uuid):
    cursor.execute("DELETE FROM keys WHERE uuid = ?", (u_uuid,))
    conn.commit()

def add_payment(user_id, plan_key):
    cursor.execute("INSERT INTO payments (user_id, plan_key) VALUES (?, ?)", (user_id, plan_key))
    conn.commit()

def get_last_pending_plan(user_id):
    cursor.execute("SELECT plan_key FROM payments WHERE user_id = ? AND status = 'pending' ORDER BY timestamp DESC LIMIT 1", (user_id,))
    row = cursor.fetchone()
    if row:
        cursor.execute("UPDATE payments SET status = 'approved' WHERE user_id = ? AND plan_key = ? AND status = 'pending'",
                       (user_id, row[0]))
        conn.commit()
        return row[0]
    return None
