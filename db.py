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
    username TEXT,
    referrer_id INTEGER DEFAULT NULL,
    registration_date TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (referrer_id) REFERENCES users(id)
)
''')

cursor.execute('''
CREATE TABLE IF NOT EXISTS keys (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    uuid TEXT UNIQUE,
    sid TEXT,
    days INTEGER,       
    end_date DATETIME,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    sub_id TEXT,
    is_active INTEGER DEFAULT 1,  -- ← Добавлена колонка is_active
    start_date DATETIME DEFAULT CURRENT_TIMESTAMP,  -- ← Добавлена колонка start_date
    FOREIGN KEY (user_id) REFERENCES users(id)
)
''')

# Добавляем отсутствующие колонки, если их нет
try:
    cursor.execute("ALTER TABLE keys ADD COLUMN is_active INTEGER DEFAULT 1")
except sqlite3.OperationalError:
    pass  # Колонка уже существует

try:
    cursor.execute("ALTER TABLE keys ADD COLUMN start_date DATETIME DEFAULT CURRENT_TIMESTAMP")
except sqlite3.OperationalError:
    pass  # Колонка уже существует

cursor.execute('''
CREATE TABLE IF NOT EXISTS payments (
    user_id INTEGER,
    plan_key TEXT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    status TEXT DEFAULT 'pending',
    FOREIGN KEY (user_id) REFERENCES users(id)
)
''')

cursor.execute('''
CREATE TABLE IF NOT EXISTS referrals (
    referrer_id INTEGER,
    referred_id INTEGER UNIQUE,
    reward_given INTEGER DEFAULT 0,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (referrer_id, referred_id),
    FOREIGN KEY (referrer_id) REFERENCES users(id),
    FOREIGN KEY (referred_id) REFERENCES users(id)
)
''')

cursor.execute('''
CREATE TABLE IF NOT EXISTS referral_rewards (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    referral_id INTEGER,
    days_added INTEGER,
    reward_date TEXT,
    FOREIGN KEY (user_id) REFERENCES users(id)
)
''')

conn.commit()

def add_user(uid, username, referrer_id=None):
    cursor.execute("""
        INSERT OR IGNORE INTO users (id, username, referrer_id)
        VALUES (?, ?, ?)
    """, (uid, username, referrer_id))
   
    if cursor.rowcount > 0 and referrer_id:
        cursor.execute("""
            INSERT OR IGNORE INTO referrals (referrer_id, referred_id)
            VALUES (?, ?)
        """, (referrer_id, uid))
   
    conn.commit()
    return cursor.rowcount > 0

def add_key(user_id, u_uuid, sid, days):
    """Добавляет ключ в базу"""
    try:
        start_date = datetime.datetime.now()
        end_date = datetime.datetime.now() + datetime.timedelta(days=days)
        
        # Деактивируем старые ключи
        cursor.execute("""
            UPDATE keys SET is_active = 0
            WHERE user_id = ?
        """, (user_id,))
        
        # Добавляем новый ключ
        cursor.execute("""
            INSERT INTO keys (user_id, uuid, sid, days, start_date, end_date, is_active)
            VALUES (?, ?, ?, ?, ?, ?, 1)
        """, (user_id, u_uuid, sid, days, start_date, end_date))
        
        conn.commit()
        return cursor.lastrowid
    except Exception as e:
        print(f"[DB ERROR] Ошибка при добавлении ключа: {e}")
        return None

def get_active_key(user_id):
    """Возвращает активный ключ пользователя"""
    cursor.execute("""
        SELECT id, uuid, sid, days, end_date, created_at, sub_id, start_date, is_active
        FROM keys 
        WHERE user_id=? 
        AND is_active = 1
        AND end_date > datetime('now') 
        ORDER BY end_date DESC 
        LIMIT 1
    """, (user_id,))
    
    row = cursor.fetchone()
    if not row:
        return None
    
    # Преобразуем даты
    row_list = list(row)
    try:
        # Преобразуем end_date
        if row_list[4] and isinstance(row_list[4], str):
            row_list[4] = datetime.datetime.fromisoformat(row_list[4].replace('Z', '+00:00'))
        # Преобразуем created_at
        if row_list[5] and isinstance(row_list[5], str):
            row_list[5] = datetime.datetime.fromisoformat(row_list[5].replace('Z', '+00:00'))
        # Преобразуем start_date
        if row_list[7] and isinstance(row_list[7], str):
            row_list[7] = datetime.datetime.fromisoformat(row_list[7].replace('Z', '+00:00'))
    except Exception as e:
        print(f"[DB ERROR] Ошибка преобразования дат: {e}")
    
    return tuple(row_list)

def get_keys(user_id):
    """Возвращает все ключи пользователя"""
    cursor.execute("""
        SELECT * FROM keys
        WHERE user_id = ?
        ORDER BY start_date DESC
    """, (user_id,))
    
    rows = cursor.fetchall()
    converted = []
    
    for row in rows:
        row_list = list(row)
        try:
            # Преобразуем даты
            for i in [4, 6, 8]:  # end_date, created_at, start_date
                if row_list[i] and isinstance(row_list[i], str):
                    row_list[i] = datetime.datetime.fromisoformat(row_list[i].replace('Z', '+00:00'))
        except Exception as e:
            print(f"[DB ERROR] Ошибка преобразования дат: {e}")
        
        converted.append(tuple(row_list))
    
    return converted

def extend_key_days(user_id, days_to_add):
    """Продлевает ключ на указанное количество дней"""
    cursor.execute("""
        SELECT uuid, end_date FROM keys
        WHERE user_id = ?
        AND is_active = 1
        AND end_date > DATETIME('now')
        LIMIT 1
    """, (user_id,))
    
    row = cursor.fetchone()
    if not row:
        return False
    
    uuid_val, end_date_str = row
    try:
        if isinstance(end_date_str, str):
            end_date = datetime.datetime.fromisoformat(end_date_str.replace('Z', '+00:00'))
        else:
            end_date = end_date_str
            
        new_end_date = end_date + datetime.timedelta(days=days_to_add)
        
        cursor.execute("""
            UPDATE keys
            SET end_date = ?, days = days + ?
            WHERE uuid = ? AND user_id = ? AND is_active = 1
        """, (new_end_date, days_to_add, uuid_val, user_id))
        
        conn.commit()
        return True
    except Exception as e:
        print(f"[DB ERROR] Ошибка при продлении ключа: {e}")
        return False

def create_key_if_none(user_id, u_uuid, sid, days):
    """Создает новый ключ, если у пользователя нет активного"""
    active_key = get_active_key(user_id)
    if not active_key:
        return add_key(user_id, u_uuid, sid, days)
    return False  # Ключ уже есть

def add_referral_reward(referrer_id, referred_id, days_added):
    """Добавляет запись о награде за реферала"""
    try:
        cursor.execute("""
            INSERT INTO referral_rewards (user_id, referral_id, days_added, reward_date)
            VALUES (?, ?, ?, ?)
        """, (referrer_id, referred_id, days_added, datetime.datetime.now().isoformat()))
        
        cursor.execute("""
            UPDATE referrals
            SET reward_given = 1
            WHERE referrer_id = ? AND referred_id = ?
        """, (referrer_id, referred_id))
        
        conn.commit()
        return True
    except Exception as e:
        print(f"[DB ERROR] Ошибка при добавлении награды: {e}")
        return False

def get_referrals_count(user_id):
    """Получает количество рефералов пользователя"""
    cursor.execute("""
        SELECT COUNT(*) FROM referrals 
        WHERE referrer_id = ? AND reward_given = 1
    """, (user_id,))
    return cursor.fetchone()[0]

def get_referrals_stats(user_id):
    """Получает статистику рефералов"""
    cursor.execute("""
        SELECT
            COUNT(*) as total,
            SUM(CASE WHEN reward_given = 1 THEN 1 ELSE 0 END) as rewarded
        FROM referrals
        WHERE referrer_id = ?
    """, (user_id,))
    
    row = cursor.fetchone()
    return {
        'total': row[0] if row else 0,
        'rewarded': row[1] if row and row[1] else 0
    }

def get_user_info(user_id):
    """Получает информацию о пользователе"""
    cursor.execute("""
        SELECT id, username, referrer_id, registration_date 
        FROM users WHERE id = ?
    """, (user_id,))
    
    row = cursor.fetchone()
    if not row:
        return None
    
    # Получаем статистику рефералов
    ref_stats = get_referrals_stats(user_id)
    
    # Получаем активный ключ
    active_key = get_active_key(user_id)
    
    return {
        'id': row[0],
        'username': row[1],
        'referrer_id': row[2],
        'registration_date': row[3],
        'referrals_total': ref_stats['total'],
        'referrals_rewarded': ref_stats['rewarded'],
        'has_active_key': active_key is not None
    }

def get_all_expired_keys():
    """Возвращает все просроченные ключи"""
    cursor.execute("SELECT user_id, uuid FROM keys WHERE end_date < DATETIME('now')")
    return cursor.fetchall()

def delete_key_by_uuid(u_uuid):
    """Удаляет ключ по UUID"""
    cursor.execute("DELETE FROM keys WHERE uuid = ?", (u_uuid,))
    conn.commit()
    return cursor.rowcount > 0

def add_payment(user_id, plan_key):
    """Добавляет запись о платеже"""
    cursor.execute("INSERT INTO payments (user_id, plan_key) VALUES (?, ?)", (user_id, plan_key))
    conn.commit()
    return True

def get_last_pending_plan(user_id):
    """Получает последний ожидающий план оплаты"""
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

def update_key_subid(u_uuid, sub_id):
    """Сохраняет sub_id для ключа"""
    cursor.execute("""
        UPDATE keys SET sub_id = ? WHERE uuid = ?
    """, (sub_id, u_uuid))
    conn.commit()
    return True

def get_key_subid(u_uuid):
    """Возвращает sub_id по uuid ключа"""
    cursor.execute("SELECT sub_id FROM keys WHERE uuid = ?", (u_uuid,))
    row = cursor.fetchone()
    return row[0] if row else None

def get_key_by_subid(sub_id):
    """Возвращает ключ по sub_id"""
    cursor.execute("SELECT * FROM keys WHERE sub_id = ?", (sub_id,))
    return cursor.fetchone()

def get_key_data_for_subscription(sub_id):
    """Получает данные ключа для подписки"""
    cursor.execute("""
        SELECT uuid, days, end_date, user_id 
        FROM keys WHERE sub_id = ?
    """, (sub_id,))
    
    row = cursor.fetchone()
    if not row:
        return None
    
    return {
        'uuid': row[0],
        'days': row[1],
        'end_date': row[2],
        'user_id': row[3]
    }

# Закрытие соединения при завершении
import atexit
@atexit.register
def close_connection():
    conn.close()
