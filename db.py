import sqlite3
import datetime

# Подключение к базе данных
# check_same_thread=False нужен для работы sqlite в разных потоках (фоновая очистка + бот)
conn = sqlite3.connect("vpn.db", check_same_thread=False)
cursor = conn.cursor()

def init_db():
    """Инициализация таблиц при первом запуске"""
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
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        telegram_id INTEGER,
        plan TEXT,
        status TEXT,
        created_at TIMESTAMP
    )
    """)
    conn.commit()

# Вызываем инициализацию сразу
init_db()

# ===== Пользователи =====
def add_user(telegram_id, username, referrer_id=None):
    cursor.execute("INSERT OR IGNORE INTO users VALUES (?, ?, ?, ?)",
                   (telegram_id, username, referrer_id, datetime.datetime.now()))
    conn.commit()

def get_user(telegram_id):
    cursor.execute("SELECT * FROM users WHERE telegram_id=?", (telegram_id,))
    return cursor.fetchone()

# ===== Ключи =====
def add_key(telegram_id, uuid_val, short_id, days):
    start = datetime.datetime.now()
    end = start + datetime.timedelta(days=days)
    cursor.execute("INSERT INTO keys VALUES (?, ?, ?, ?, ?)",
                   (telegram_id, uuid_val, short_id, start, end))
    conn.commit()

def get_keys(telegram_id):
    """Возвращает список uuid активных ключей пользователя"""
    cursor.execute("SELECT uuid FROM keys WHERE telegram_id=? AND end_date > ?", 
                   (telegram_id, datetime.datetime.now()))
    rows = cursor.fetchall()
    return [row[0] for row in rows]

def get_all_expired_keys():
    """Возвращает список (telegram_id, uuid) для тех, чей срок истек"""
    now = datetime.datetime.now()
    cursor.execute("SELECT telegram_id, uuid FROM keys WHERE end_date < ?", (now,))
    return cursor.fetchall()

def delete_key_by_uuid(uuid_val):
    """Полное удаление ключа из базы"""
    cursor.execute("DELETE FROM keys WHERE uuid=?", (uuid_val,))
    conn.commit()

def extend_key(telegram_id, days):
    """Продление существующего ключа (если он есть)"""
    cursor.execute("SELECT end_date, uuid FROM keys WHERE telegram_id=? ORDER BY end_date DESC LIMIT 1", (telegram_id,))
    row = cursor.fetchone()
    if row:
        current_end = datetime.datetime.fromisoformat(str(row[0]))
        # Если ключ уже истек, продлеваем от текущего момента, если нет - добавляем к остатку
        base_date = max(current_end, datetime.datetime.now())
        new_end = base_date + datetime.timedelta(days=days)
        cursor.execute("UPDATE keys SET end_date=? WHERE uuid=?", (new_end, row[1]))
        conn.commit()
        return True
    return False

# ===== Платежи =====
def add_payment(telegram_id, plan):
    """Запись о намерении совершить платеж"""
    cursor.execute("INSERT INTO payments (telegram_id, plan, status, created_at) VALUES (?, ?, ?, ?)", 
                   (telegram_id, plan, "pending", datetime.datetime.now()))
    conn.commit()

def get_last_pending_plan(telegram_id):
    """Получает название тарифа из последнего неоплаченного счета"""
    cursor.execute("SELECT plan FROM payments WHERE telegram_id=? AND status='pending' ORDER BY id DESC LIMIT 1", (telegram_id,))
    row = cursor.fetchone()
    return row[0] if row else "1m"

def set_payment_status(telegram_id, plan, status):
    """Обновляет статус платежа"""
    cursor.execute("UPDATE payments SET status=? WHERE telegram_id=? AND plan=? AND status='pending'", 
                   (status, telegram_id, plan))
    conn.commit()
