# db.py
import sqlite3
from datetime import datetime, timedelta

conn = sqlite3.connect("vpn.db", check_same_thread=False)
cursor = conn.cursor()

# Создание таблицы ключей
cursor.execute("""
CREATE TABLE IF NOT EXISTS keys (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    telegram_id INTEGER,
    uuid TEXT,
    short_id TEXT,
    plan TEXT,
    start_date TEXT,
    end_date TEXT,
    referral_code TEXT
)
""")
conn.commit()

def add_key(telegram_id, uuid, short_id, plan, days, referral_code=None):
    start = datetime.utcnow()
    end = start + timedelta(days=days)
    cursor.execute("""
    INSERT INTO keys (telegram_id, uuid, short_id, plan, start_date, end_date, referral_code)
    VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (telegram_id, uuid, short_id, plan, start.isoformat(), end.isoformat(), referral_code))
    conn.commit()

def get_active_keys(telegram_id):
    now = datetime.utcnow().isoformat()
    cursor.execute("SELECT * FROM keys WHERE telegram_id=? AND end_date>?", (telegram_id, now))
    return cursor.fetchall()

def extend_key(uuid, extra_days):
    cursor.execute("SELECT end_date FROM keys WHERE uuid=?", (uuid,))
    row = cursor.fetchone()
    if row:
        end = datetime.fromisoformat(row[0]) + timedelta(days=extra_days)
        cursor.execute("UPDATE keys SET end_date=? WHERE uuid=?", (end.isoformat(), uuid))
        conn.commit()

def cleanup_expired_keys():
    now = datetime.utcnow().isoformat()
    cursor.execute("SELECT id, uuid FROM keys WHERE end_date<?", (now,))
    rows = cursor.fetchall()
    for key_id, uuid in rows:
        # TODO: удалить пользователя с Xray API, когда будет токен
        cursor.execute("DELETE FROM keys WHERE id=?", (key_id,))
        print(f"[INFO] Удалён ключ {uuid}")
    conn.commit()
