# db.py
import sqlite3
import datetime

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
    user_id INTEGER,
    uuid TEXT UNIQUE,
    sid TEXT,
    start_date TEXT,
    end_date TEXT,
    is_active INTEGER DEFAULT 1,
    email TEXT,  # ДОБАВЛЕНО ПОЛЕ EMAIL
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
    user_id INTEGER,
    referral_id INTEGER,
    days_added INTEGER,
    reward_date TEXT,
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (referral_id) REFERENCES referrals(id)
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

def add_key(user_id, u_uuid, sid, days, email):  # ИЗМЕНЕНО: добавлен email
    """Добавляем ключ с датами в формате ISO строки"""
    start_date = datetime.datetime.now().isoformat()
    end_date = (datetime.datetime.now() + datetime.timedelta(days=days)).isoformat()
    
    # Деактивируем старые ключи
    cursor.execute("""
        UPDATE keys SET is_active = 0 
        WHERE user_id = ? AND is_active = 1
    """, (user_id,))
    
    cursor.execute("""
        INSERT INTO keys (user_id, uuid, sid, start_date, end_date, is_active, email)
        VALUES (?, ?, ?, ?, ?, 1, ?)
    """, (user_id, u_uuid, sid, start_date, end_date, email))
    
    conn.commit()
    return cursor.lastrowid

def get_active_key(user_id):
    """Получаем активный ключ пользователя"""
    cursor.execute("""
        SELECT * FROM keys 
        WHERE user_id = ? 
        AND is_active = 1
        AND end_date > DATETIME('now')
        LIMIT 1
    """, (user_id,))
    
    row = cursor.fetchone()
    if not row:
        return None
    
    # Преобразуем даты
    row_list = list(row)
    try:
        row_list[3] = datetime.datetime.fromisoformat(row_list[3])
        row_list[4] = datetime.datetime.fromisoformat(row_list[4])
    except (ValueError, TypeError) as e:
        print(f"Ошибка преобразования дат: {e}")
        return None
    
    return tuple(row_list)

def get_keys(user_id):
    """Возвращает все ключи пользователя (не только активные)"""
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
            row_list[3] = datetime.datetime.fromisoformat(row_list[3])
            row_list[4] = datetime.datetime.fromisoformat(row_list[4])
        except (ValueError, TypeError) as e:
            print(f"Ошибка преобразования дат: {e}")
            continue
        
        converted.append(tuple(row_list))
    
    return converted

def extend_key_days(user_id, days_to_add):
    """Продлевает активный ключ на указанное количество дней"""
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
        end_date = datetime.datetime.fromisoformat(end_date_str)
        new_end_date = end_date + datetime.timedelta(days=days_to_add)
        new_end_date_str = new_end_date.isoformat()
        
        cursor.execute("""
            UPDATE keys 
            SET end_date = ? 
            WHERE uuid = ? AND user_id = ?
        """, (new_end_date_str, uuid_val, user_id))
        
        conn.commit()
        return True
    except (ValueError, TypeError) as e:
        print(f"Ошибка при продлении ключа: {e}")
        return False

def create_key_if_none(user_id, u_uuid, sid, days):
    """Создает новый ключ, если у пользователя нет активного"""
    active_key = get_active_key(user_id)
    if not active_key:
        # Нужно передать email тоже, но его нет в этой функции
        # Создаем базовый email
        email = f"user_{user_id}_{u_uuid[:8]}"
        return add_key(user_id, u_uuid, sid, days, email)
    return False  # Ключ уже есть

def add_referral_reward(referrer_id, referred_id, days_added):
    """Добавляет запись о награде за реферала"""
    cursor.execute("""
        INSERT INTO referral_rewards (user_id, referral_id, days_added, reward_date)
        VALUES (?, ?, ?, ?)
    """, (referrer_id, referred_id, days_added, datetime.datetime.now().isoformat()))
    
    # Отмечаем, что награда выдана
    cursor.execute("""
        UPDATE referrals 
        SET reward_given = 1 
        WHERE referrer_id = ? AND referred_id = ?
    """, (referrer_id, referred_id))
    
    conn.commit()

def get_referrals_count(user_id):
    """Получает количество рефералов пользователя"""
    cursor.execute("""
        SELECT COUNT(*) FROM referrals 
        WHERE referrer_id = ? AND reward_given = 1
    """, (user_id,))
    return cursor.fetchone()[0]

def get_referrals_stats(user_id):
    """Получает статистику по рефералам"""
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

def get_all_expired_keys():
    cursor.execute("SELECT user_id, uuid, email FROM keys WHERE end_date < DATETIME('now')")
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
