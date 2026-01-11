import sqlite3
from datetime import datetime, timedelta

conn = sqlite3.connect("vpn.db", check_same_thread=False)
cursor = conn.cursor()

# Пользователи
cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    telegram_id INTEGER PRIMARY KEY,
    ref_code TEXT UNIQUE,
    referred_by TEXT,
    created_at TEXT
)
""")

# Ключи
cursor.execute("""
CREATE TABLE IF NOT EXISTS keys (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    telegram_id INTEGER,
    uuid TEXT,
    short_id TEXT,
    end_date TEXT
)
""")
conn.commit()


def create_user(tg_id, referred_by=None):
    ref_code = f"R{tg_id}"
    cursor.execute(
        "INSERT OR IGNORE INTO users VALUES (?,?,?,?)",
        (tg_id, ref_code, referred_by, datetime.utcnow().isoformat())
    )
    conn.commit()
    return ref_code


def get_user_by_ref(ref_code):
    cursor.execute("SELECT telegram_id FROM users WHERE ref_code=?", (ref_code,))
    row = cursor.fetchone()
    return row[0] if row else None


def add_key(tg_id, uuid, short_id, days):
    end = datetime.utcnow() + timedelta(days=days)
    cursor.execute(
        "INSERT INTO keys (telegram_id, uuid, short_id, end_date) VALUES (?,?,?,?)",
        (tg_id, uuid, short_id, end.isoformat())
    )
    conn.commit()


def extend_key(tg_id, days):
    cursor.execute(
        "SELECT id, end_date FROM keys WHERE telegram_id=? ORDER BY end_date DESC LIMIT 1",
        (tg_id,)
    )
    row = cursor.fetchone()
    if not row:
        return False

    key_id, old_end = row
    new_end = datetime.fromisoformat(old_end) + timedelta(days=days)

    cursor.execute(
        "UPDATE keys SET end_date=? WHERE id=?",
        (new_end.isoformat(), key_id)
    )
    conn.commit()
    return True


def get_key(tg_id):
    cursor.execute(
        "SELECT uuid, short_id, end_date FROM keys WHERE telegram_id=? ORDER BY end_date DESC LIMIT 1",
        (tg_id,)
    )
    return cursor.fetchone()
