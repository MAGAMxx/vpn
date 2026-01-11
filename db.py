import sqlite3
import datetime

conn = sqlite3.connect("vpn.db", check_same_thread=False)
cursor = conn.cursor()

# Таблицы
cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    telegram_id INTEGER PRIMARY KEY,
    username TEXT,
    referrer_id INTEGER,
    first_joined TIMESTAMP
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS keys (
    telegram_id INTEGER,
    uuid TEXT,
    short_id TEXT,
    start_date TIMESTAMP,
    end_date TIMESTAMP
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS payments (
    telegram_id INTEGER,
    plan TEXT,
    status TEXT
)
""")
conn.commit()

# ===== Пользователи =====
def add_user(telegram_id, username, referrer_id=None):
    cursor.execute("INSERT OR IGNORE INTO users VALUES (?, ?, ?, ?)",
                   (telegram_id, username, referrer_id, datetime.datetime.now()))
    conn.commit()

def get_user(telegram_id):
    cursor.execute("SELECT * FROM users WHERE telegram_id=?", (telegram_id,))
    return cursor.fetchone()

# ===== Ключи =====
def add_key(telegram_id, uuid, short_id, days):
    start = datetime.datetime.now()
    end = start + datetime.timedelta(days=days)
    cursor.execute("INSERT INTO keys VALUES (?, ?, ?, ?, ?)",
                   (telegram_id, uuid, short_id, start, end))
    conn.commit()

def get_keys(telegram_id):
    cursor.execute("SELECT * FROM keys WHERE telegram_id=?", (telegram_id,))
    return cursor.fetchall()

def extend_key(telegram_id, days):
    cursor.execute("SELECT end_date FROM keys WHERE telegram_id=? ORDER BY end_date DESC LIMIT 1", (telegram_id,))
    row = cursor.fetchone()
    if row:
        end_date = datetime.datetime.fromisoformat(row[0])
        new_end = end_date + datetime.timedelta(days=days)
        cursor.execute("UPDATE keys SET end_date=? WHERE telegram_id=? AND end_date=?", (new_end, telegram_id, row[0]))
        conn.commit()
        return True
    return False

def delete_expired_keys():
    now = datetime.datetime.now()
    cursor.execute("DELETE FROM keys WHERE end_date<?", (now,))
    conn.commit()

# ===== Платежи =====
def add_payment(telegram_id, plan):
    cursor.execute("INSERT INTO payments VALUES (?, ?, ?)", (telegram_id, plan, "pending"))
    conn.commit()

def set_payment_status(telegram_id, plan, status):
    cursor.execute("UPDATE payments SET status=? WHERE telegram_id=? AND plan=?", (status, telegram_id, plan))
    conn.commit()
