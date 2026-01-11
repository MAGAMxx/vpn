# db.py
import sqlite3
from datetime import datetime, timedelta

DB_FILE = "vpn.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS keys (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id INTEGER,
            uuid TEXT,
            sid TEXT,
            plan TEXT,
            start_date TEXT,
            end_date TEXT
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS referrals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            referrer_id INTEGER,
            referred_id INTEGER,
            created_at TEXT
        )
    """)
    conn.commit()
    conn.close()

init_db()

def add_key(telegram_id, uuid, sid, plan, days):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    start = datetime.utcnow()
    end = start + timedelta(days=days)
    c.execute("INSERT INTO keys (telegram_id, uuid, sid, plan, start_date, end_date) VALUES (?, ?, ?, ?, ?, ?)",
              (telegram_id, uuid, sid, plan, start.isoformat(), end.isoformat()))
    conn.commit()
    conn.close()

def get_active_keys(telegram_id):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    now = datetime.utcnow().isoformat()
    c.execute("SELECT * FROM keys WHERE telegram_id=? AND end_date>?", (telegram_id, now))
    rows = c.fetchall()
    conn.close()
    return rows

def extend_key(telegram_id, days):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    now = datetime.utcnow().isoformat()
    # Берем первый активный ключ
    c.execute("SELECT id, end_date FROM keys WHERE telegram_id=? AND end_date>?", (telegram_id, now))
    row = c.fetchone()
    if row:
        key_id, old_end = row
        old_end_dt = datetime.fromisoformat(old_end)
        new_end = old_end_dt + timedelta(days=days)
        c.execute("UPDATE keys SET end_date=? WHERE id=?", (new_end.isoformat(), key_id))
        conn.commit()
        conn.close()
        return True
    conn.close()
    return False

def add_referral(referrer_id, referred_id):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("INSERT INTO referrals (referrer_id, referred_id, created_at) VALUES (?, ?, ?)",
              (referrer_id, referred_id, datetime.utcnow().isoformat()))
    conn.commit()
    conn.close()

def check_referral(ref_code):
    try:
        telegram_id = int(ref_code.replace("REF-", ""))
        return telegram_id
    except:
        return None

def cleanup_expired_keys():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    now = datetime.utcnow().isoformat()
    c.execute("DELETE FROM keys WHERE end_date<?", (now,))
    conn.commit()
    conn.close()
