# db.py
import sqlite3
import datetime

# Подключаемся к базе (check_same_thread=False для работы в многопоточной среде)
conn = sqlite3.connect('vpn_bot.db', check_same_thread=False)
cursor = conn.cursor()

# Создаём таблицы, если их нет
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
    start_date TEXT,   -- храним как ISO строку
    end_date TEXT,
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
    """Добавляем ключ с датами в формате ISO строки"""
    start_date = datetime.datetime.now().isoformat()
    end_date = (datetime.datetime.now() + datetime.timedelta(days=days)).isoformat()
    
    cursor.execute("""
        INSERT INTO keys (user_id, uuid, sid, start_date, end_date)
        VALUES (?, ?, ?, ?, ?)
    """, (user_id, u_uuid, sid, start_date, end_date))
    conn.commit()

def get_keys(user_id):
    """Возвращает активные ключи с датами уже в виде datetime"""
    cursor.execute("""
        SELECT * FROM keys 
        WHERE user_id = ? 
        AND end_date > DATETIME('now')
    """, (user_id,))
    
    rows = cursor.fetchall()
    converted = []
    
    for row in rows:
        row_list = list(row)
        try:
            # Преобразуем строки дат в datetime (индексы 3 и 4)
            row_list[3] = datetime.datetime.fromisoformat(row_list[3])
            row_list[4] = datetime.datetime.fromisoformat(row_list[4])
        except (ValueError, TypeError) as e:
            print(f"Ошибка преобразования дат для ключа {row[1]}: {e}")
            continue  # пропускаем битую запись
        
        converted.append(tuple(row_list))
    
    return converted

def get_keys_with_expiry(user_id):
    """Для старого метода — uuid + end_date как datetime"""
    cursor.execute("""
        SELECT uuid, end_date FROM keys 
        WHERE user_id = ? 
        AND end_date > DATETIME('now')
    """, (user_id,))
    
    rows = cursor.fetchall()
    result = []
    for uuid_val, end_date_str in rows:
        try:
            end_date = datetime.datetime.fromisoformat(end_date_str)
            result.append((uuid_val, end_date))
        except ValueError:
            print(f"Ошибка даты для uuid {uuid_val}")
    return result

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
    cursor.execute("""
        SELECT plan_key FROM payments 
        WHERE user_id = ? 
        AND status = 'pending' 
        ORDER BY timestamp DESC 
        LIMIT 1
    """, (user_id,))
    
    row = cursor.fetchone()
    if row:
        cursor.execute("""
            UPDATE payments 
            SET status = 'approved' 
            WHERE user_id = ? 
            AND plan_key = ? 
            AND status = 'pending'
        """, (user_id, row[0]))
        conn.commit()
        return row[0]
    return None
