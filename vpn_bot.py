import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import datetime
import uuid
import requests
import json
import time
import threading
import pytz
import secrets  # Добавлен импорт для secrets.token_hex
import db
from config import *
requests.packages.urllib3.disable_warnings()

bot = telebot.TeleBot(BOT_TOKEN)
session = requests.Session()

# Московский часовой пояс
MOSCOW_TZ = pytz.timezone('Europe/Moscow')

# Настройки для Happ + Render
RENDER_URL = "https://magamix.onrender.com" # ← измени, если subdomain другой
SUB_PATH = "/sub/"

# Emoji для оформления
EMOJI = {
    "home": "🏠", "back": "↩️", "key": "🔑", "buy": "💳", "support": "🆘",
    "time": "⏰", "link": "🔗", "copy": "📋", "check": "✅", "cross": "❌",
    "info": "ℹ️", "rocket": "🚀", "crown": "👑", "shield": "🛡️", "wifi": "📡",
    "lock": "🔒", "unlock": "🔓", "star": "⭐", "fire": "🔥", "money": "💰",
    "card": "💎", "phone": "📱", "bank": "🏦", "download": "📥", "upload": "📤",
    "speed": "⚡", "global": "🌐", "settings": "⚙️", "friends": "👥", "gift": "🎁",
    "invite": "📨", "stats": "📊", "trophy": "🏆", "medal": "🏅", "party": "🎉",
    "diamond": "💎"
}

# Реферальная система
REFERRAL_REWARD_DAYS = 5 # +5 дней за каждого друга

# --- Взаимодействие с 3X-UI ---
def xui_login():
    try:
        login_url = f"{PANEL_URL}/{PANEL_PATH}/login"
        r = session.post(login_url, data={"username": PANEL_USER, "password": PANEL_PASS}, verify=False, timeout=10)
        return r.status_code == 200
    except Exception as e:
        print(f"[LOGIN ERROR] {e}")
        return False

def generate_subscription_link(sub_id):
    return f"https://31.130.131.214:{SUB_PORT}{SUB_PATH}{sub_id}"

def add_user_to_xray(user_uuid, email, days):
    if not xui_login():
        print("[ADD CLIENT] Не удалось авторизоваться")
        return None
    
    expiry_time = int((time.time() + (days * 86400)) * 1000)
    
    # Генерируем короткий subId как в панели (8–16 символов hex)
    sub_id = secrets.token_hex(8) # пример: w794j35f1udoambp
    payload = {
        "id": INBOUND_ID,
        "settings": json.dumps({
            "clients": [{
                "id": user_uuid,
                "alterId": 0,
                "email": f"🇳🇱 НИДЕРЛАНДЫ⚡MAGAMIX VPN {email}",
                "limitIp": 2,
                "totalGB": 0,
                "expiryTime": expiry_time,
                "enable": True,
                "tgId": "",
                "subId": sub_id, 
                "remark": "Нидерланды 🇳🇱"
            }]
        })
    }
    
    try:
        url = f"{PANEL_URL}/{PANEL_PATH}/panel/api/inbounds/addClient"
        r = session.post(url, json=payload, verify=False, timeout=15)
        response_data = r.json()
        if response_data.get("success"):
            print(f"[SUCCESS] Ключ создан с subId: {sub_id}")
            return sub_id # ← возвращаем sub_id
        else:
            msg = response_data.get("msg", "")
            print(f"[ADD CLIENT] Ошибка панели: {msg}")
            return None
    except Exception as e:
        print(f"[ADD CLIENT ERROR] {e}")
        return None

def update_user_in_xray(email, new_days):
    if not xui_login():
        return False
    
    try:
        url = f"{PANEL_URL}/{PANEL_PATH}/panel/api/inbounds/get/{INBOUND_ID}"
        r = session.get(url, verify=False, timeout=10)
        data = r.json()
        if not data.get("success"):
            return False
        
        settings = json.loads(data["obj"]["settings"])
        clients = settings.get("clients", [])
        
        for client in clients:
            if client.get("email") == email:
                expiry_time = int((time.time() + (new_days * 86400)) * 1000)
                client["expiryTime"] = expiry_time
                break
        
        payload = {
            "id": INBOUND_ID,
            "settings": json.dumps({"clients": clients})
        }
        
        update_url = f"{PANEL_URL}/{PANEL_PATH}/panel/api/inbounds/update/{INBOUND_ID}"
        r = session.post(update_url, json=payload, verify=False, timeout=15)
        return r.json().get("success", False)
    except Exception as e:
        print(f"[UPDATE CLIENT ERROR] {e}")
        return False

def delete_user_from_xray(email):
    if not xui_login():
        return False
    
    try:
        url = f"{PANEL_URL}/{PANEL_PATH}/panel/api/inbounds/{INBOUND_ID}/delClient/{email}"
        r = session.post(url, verify=False, timeout=10)
        return r.json().get("success", False)
    except Exception as e:
        print(f"[DEL CLIENT ERROR] {e}")
        return False

# --- Вспомогательные функции ---
def generate_vless_link(u_uuid):
    # Экранируем специальные символы для Markdown
    return (f"vless://{u_uuid}@{SERVER_IP}:{SERVER_PORT}?type=tcp&encryption=none&security=reality"
            f"&sni={SNI}&fp={FP}&pbk={PBK}&sid={SID}&spx=%2F# НИДЕРЛАНДЫ 🇳🇱 MAGAMIX")

def generate_happ_deeplink(sub_id):
    """Генерирует deeplink для Happ в формате https://magamix.onrender.com/url/?url=happ://add/..."""
    if not sub_id:
        return None
    
    # Базовый URL для подписки
    subscription_url = f"https://magamix.onrender.com/connect/{sub_id}"
    
    # Формируем полный deeplink
    deeplink = f"https://magamix.onrender.com/url/?url=happ://add/{subscription_url}"
    
    return deeplink

def get_remaining_time_str(end_date):
    end_date_aware = MOSCOW_TZ.localize(end_date)
    now_aware = datetime.datetime.now(MOSCOW_TZ)
    delta = end_date_aware - now_aware
    
    if delta.total_seconds() <= 0:
        return "истёк"
    if delta.days >= 1:
        return f"{delta.days} дн."
    
    hours = int(delta.total_seconds() // 3600) + (1 if delta.total_seconds() % 3600 > 0 else 0)
    return f"{hours} ч."

def generate_referral_link(user_id):
    return f"https://t.me/MAGAMIX_VPN_bot?start=ref{user_id}"

def give_referral_reward(referrer_id, referred_id):
    try:
        db_cursor = db.conn.cursor()
        db_cursor.execute("""
            SELECT reward_given FROM referrals
            WHERE referrer_id = ? AND referred_id = ?
        """, (referrer_id, referred_id))
        row = db_cursor.fetchone()
        
        if row and row[0] == 1:
            return False
        
        active_key = db.get_active_key(referrer_id)
        
        if active_key:
            success = db.extend_key_days(referrer_id, REFERRAL_REWARD_DAYS)
            if success:
                uuid_val = active_key[1]
                email = f"user_{referrer_id}*{uuid_val[:8]}"
                
                new_end_date = active_key[4] + datetime.timedelta(days=REFERRAL_REWARD_DAYS)
                days_until_new_end = (new_end_date - datetime.datetime.now()).days
                
                if days_until_new_end > 0:
                    update_user_in_xray(email, days_until_new_end)
                
                db.add_referral_reward(referrer_id, referred_id, REFERRAL_REWARD_DAYS)
                
                try:
                    bot.send_message(
                        referrer_id,
                        f"{EMOJI['party']} *Бонус за друга!*\n\n"
                        f"{EMOJI['gift']} Ваш активный ключ продлен на *+{REFERRAL_REWARD_DAYS} дней*!\n"
                        f"{EMOJI['friends']} Ваш друг успешно зарегистрировался по вашей ссылке.\n\n"
                        f"{EMOJI['trophy']} Приглашайте больше друзей и получайте бонусы!",
                        parse_mode="Markdown"
                    )
                except:
                    pass
                
                return True
        else:
            u_uuid = str(uuid.uuid4())
            email = f"ref*{referrer_id}*{int(time.time())}"
            
            sub_id = add_user_to_xray(u_uuid, email, REFERRAL_REWARD_DAYS)
            if sub_id:
                db.add_key(referrer_id, u_uuid, SID, REFERRAL_REWARD_DAYS)
                db.update_key_subid(u_uuid, sub_id) # ← сохраняем sub_id
                
                try:
                    bot.send_message(
                        referrer_id,
                        f"{EMOJI['party']} *Бонус за друга!*\n\n"
                        f"{EMOJI['gift']} Вам выдан новый ключ на *{REFERRAL_REWARD_DAYS} дней*!\n"
                        f"{EMOJI['friends']} Ваш друг успешно зарегистрировался.\n"
                        f"{EMOJI['key']} Ключ в «Мои ключи»\n\n"
                        f"{EMOJI['trophy']} Приглашайте больше друзей!",
                        parse_mode="Markdown"
                    )
                except:
                    pass
                
                return True
        
        return False
    except Exception as e:
        print(f"[REFERRAL REWARD ERROR] {e}")
        return False

def get_main_menu():
    """Главное меню"""
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton(f"{EMOJI['buy']} Купить VPN", callback_data="buy"),
        InlineKeyboardButton(f"{EMOJI['key']} Мой ключ", callback_data="my_key")
    )
    kb.add(
        InlineKeyboardButton(f"{EMOJI['friends']} Пригласить друга", callback_data="referral"),
        InlineKeyboardButton(f"{EMOJI['support']} Поддержка", url="https://t.me/MAGAMIX_support")
    )
    kb.add(InlineKeyboardButton(f"{EMOJI['info']} Информация", callback_data="info"))
    return kb

def get_back_button(to="main"):
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton(f"{EMOJI['back']} Назад", callback_data=f"back_{to}"))  # ← без *
    return kb

def get_buy_menu():
    """Меню покупки с кнопкой назад"""
    kb = InlineKeyboardMarkup()
    for k, v in PRICES.items():
        kb.add(InlineKeyboardButton(
            f"{EMOJI['card']} {v['name']} — {v['price']}₽",
            callback_data=f"plan_{k}"
        ))
    kb.add(InlineKeyboardButton(f"{EMOJI['back']} Назад", callback_data="back_main"))
    return kb

def get_instructions_menu(uuid_key=None):
    """Меню инструкций"""
    kb = InlineKeyboardMarkup()
    if uuid_key:
        kb.add(InlineKeyboardButton(
            #f"{EMOJI['copy']} Скопировать ключ",
            callback_data=f"copy_{uuid_key}"
        ))
    kb.add(InlineKeyboardButton(f"{EMOJI['back']} Назад в Мои ключи", callback_data="my_keys"))
    #kb.add(InlineKeyboardButton(f"{EMOJI['home']} В главное меню", callback_data="main"))
    return kb

def get_referral_menu(user_id):
    kb = InlineKeyboardMarkup(row_width=1)
    
    # Генерируем реферальную ссылку
    ref_link = generate_referral_link(user_id)
    
    # Получаем статистику
    ref_stats = db.get_referrals_stats(user_id)
    
    kb.add(InlineKeyboardButton(
        f"{EMOJI['invite']} Пригласить друга",
        callback_data=f"copy_ref_{user_id}"
    ))
    
    #kb.add(InlineKeyboardButton(
        #f"{EMOJI['stats']} Моя статистика",
        #callback_data="ref_stats"
    #))
    
    kb.add(InlineKeyboardButton(f"{EMOJI['back']} Назад", callback_data="back_main"))
    
    return kb, ref_link, ref_stats

# --- Обработка команд ---
@bot.message_handler(commands=['start'])
def start_handler(message):
    user_id = message.from_user.id
    username = message.from_user.username or "без username"
    first_name = message.from_user.first_name or ""
    last_name = message.from_user.last_name or ""
    referrer_id = None
    
    if len(message.text.split()) > 1:
        ref_code = message.text.split()[1]
        if ref_code.startswith('ref'):
            try:
                referrer_id = int(ref_code[3:])
                if referrer_id == user_id:
                    referrer_id = None
            except:
                referrer_id = None
    
    is_new_user = db.add_user(user_id, username, referrer_id)
    
    # Уведомление админу о новом пользователе
    if is_new_user:
        # Форматируем имя пользователя
        full_name = f"{first_name} {last_name}".strip() if first_name or last_name else "Не указано"
        
        # Формируем информацию о реферере
        ref_info = ""
        if referrer_id:
            try:
                referrer_user = bot.get_chat(referrer_id)
                referrer_username = f"@{referrer_user.username}" if referrer_user.username else f"ID: {referrer_id}"
                ref_info = f"\n👥 *Пригласил:* {referrer_username}"
            except:
                ref_info = f"\n👥 *Пригласил:* ID: {referrer_id}"
        
        # Отправляем уведомление админу
        admin_notification = (
            f"🎉 *НОВЫЙ ПОЛЬЗОВАТЕЛЬ!*\n\n"
            f"🆔 *ID:* `{user_id}`\n"
            f"👤 *Имя:* {full_name}\n"
            f"📱 *Username:* @{username if username else 'нет'}\n"
            f"📅 *Дата регистрации:* {datetime.datetime.now(MOSCOW_TZ).strftime('%d.%m.%Y %H:%M')} МСК"
            f"{ref_info}\n\n"
            f"📊 *Общее число пользователей:* {db.get_total_users_count()}"
        )
        
        try:
            bot.send_message(ADMIN_ID, admin_notification, parse_mode="Markdown")
        except Exception as e:
            print(f"[ADMIN NOTIFY ERROR] {e}")
    
    if is_new_user and referrer_id:
        give_referral_reward(referrer_id, user_id)
    
    active_key = db.get_active_key(user_id)
    if not active_key:
        u_uuid = str(uuid.uuid4())
        email = f"trial_{user_id}*{int(time.time())}"
        sub_id = add_user_to_xray(u_uuid, email, 3)
        if sub_id:
            db.add_key(user_id, u_uuid, SID, 3)
            db.update_key_subid(u_uuid, sub_id)
            text = (
                f"🎆*MAGAMIX VPN — твой пропуск в свободный интернет!*⚡\n\n"
                f"📱 Социальные сети и мессенджеры без блокировок\n"
                f"🌍 Полная анонимность, высокая скорость и стабильное соединение\n"
                f"🚀 Instagram, YouTube, WhatsApp — заходи где угодно!\n"
                f"😍Вам доступен бонус - 3 дня. Перейдите в (Мой ключ)"
            )
        else:
            text = f"{EMOJI['cross']} *Ошибка триала*"
    else:
        text = (
            f"🎆*MAGAMIX VPN — твой пропуск в свободный интернет!*⚡\n\n"
            f"📱 Социальные сети и мессенджеры без блокировок\n"
            f"🌍 Полная анонимность, высокая скорость и стабильное соединение\n"
            f"🚀 Instagram, YouTube, WhatsApp — заходи где угодно!"
        )
    
    bot.send_message(user_id, text, reply_markup=get_main_menu(), parse_mode="Markdown")

@bot.message_handler(commands=['stats'])
def stats_command(message):
    if message.from_user.id != ADMIN_ID:
        bot.send_message(message.chat.id, "⛔ Команда доступна только администратору")
        return
    
    # Получаем статистику через функции из db
    total_users = db.get_total_users_count()
    total_keys = db.get_total_keys_count()
    active_keys = db.get_active_keys_count()
    
    # Используем курсор из модуля db
    db_cursor = db.conn.cursor()
    
    # Считаем сумму платежей
    db_cursor.execute("""
        SELECT plan_key, COUNT(*) as count 
        FROM payments 
        WHERE status = 'confirmed' 
        GROUP BY plan_key
    """)
    
    total_sum = 0
    payments_rows = db_cursor.fetchall()
    payments_info = []
    
    for plan_key, count in payments_rows:
        if plan_key in PRICES:
            plan_total = PRICES[plan_key]['price'] * count
            total_sum += plan_total
            payments_info.append(f"  • {PRICES[plan_key]['name']}: {count} × {PRICES[plan_key]['price']}₽ = {plan_total}₽")
    
    # Получаем количество новых пользователей за последние 24 часа
    db_cursor.execute("""
        SELECT COUNT(*) FROM users 
        WHERE registration_date >= DATETIME('now', '-1 day')
    """)
    new_last_24h = db_cursor.fetchone()[0]
    
    # Формируем текст
    stats_text = (
        f"📊 *СТАТИСТИКА БОТА*\n\n"
        f"👥 *Пользователи:*\n"
        f"  • Всего: {total_users}\n"
        f"  • Новых за 24ч: {new_last_24h}\n\n"
        f"🔑 *Ключи:*\n"
        f"  • Всего создано: {total_keys}\n"
        f"  • Активных сейчас: {active_keys}\n\n"
        f"💰 *Платежи:*\n"
    )
    
    if payments_info:
        stats_text += "\n".join(payments_info) + f"\n  • *Итого:* {total_sum}₽"
    else:
        stats_text += "  • Нет подтвержденных платежей"
    
    stats_text += f"\n\n📅 *Дата:* {datetime.datetime.now(MOSCOW_TZ).strftime('%d.%m.%Y %H:%M')} МСК"
    
    bot.send_message(message.chat.id, stats_text, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: True)
def query_handler(call):
    uid = call.from_user.id
    
    # Обработка кнопки "Назад"
    if call.data.startswith("back_"):
        target = call.data.replace("back_", "")
        if target == "main":
            text = (
                f"🎆*MAGAMIX VPN — твой пропуск в свободный интернет!*⚡\n\n"
                f"📱 Социальные сети и мессенджеры без блокировок\n"
                f"🌍 Полная анонимность, высокая скорость и стабильное соединение\n"
                f"🚀 Instagram, YouTube, WhatsApp — заходи где угодно!"
            )
            bot.edit_message_text(
                text, uid, call.message.id,
                reply_markup=get_main_menu(),
                parse_mode="Markdown"
            )
        return
    
    if call.data == "main":
        text = (
            f"{EMOJI['crown']} *Главное меню MAGAMIX VPN* {EMOJI['fire']}\n\n"
            f"{EMOJI['info']} *Выберите действие:*"
        )
        bot.edit_message_text(text, uid, call.message.id,
                            reply_markup=get_main_menu(), parse_mode="Markdown")
    
    elif call.data == "buy":
        text = (
            f"{EMOJI['money']} *Выберите тарифный план* {EMOJI['card']}\n\n"
            f"{EMOJI['info']} Все тарифы включают:\n"
            f"• {EMOJI['speed']} Максимальную скорость\n"
            f"• {EMOJI['shield']} Полную защиту\n"
            f"• {EMOJI['global']} Неограниченный трафик\n"
            f"• {EMOJI['settings']} Круглосуточную поддержку\n"
        )
        bot.edit_message_text(text, uid, call.message.id,
                            reply_markup=get_buy_menu(), parse_mode="Markdown")
    
    elif call.data.startswith("plan_"):
        plan_key = call.data.replace("plan_", "")
        data = PRICES[plan_key]
        db.add_payment(uid, plan_key, data['price'])
        
        text = (
            f"{EMOJI['card']} *Оплата тарифа: {data['name']}*\n\n"
            f"{EMOJI['money']} *Сумма к оплате:* {data['price']}₽\n"
            f"{EMOJI['bank']} *Банк для перевода:* {PAY_BANK}\n"
            f"{EMOJI['phone']} *Номер для перевода:* {PAY_PHONE}\n\n"
            f"{EMOJI['info']} *Инструкция:*\n"
            f"1. Переведите {data['price']}₽ на указанный номер\n"
            f"2. Сохраните чек об оплате\n"
            f"3. Отправьте скриншот чека в этот чат\n\n"
            f"{EMOJI['check']} После проверки ключ будет выдан автоматически!"
        )
        
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton(f"{EMOJI['back']} Назад к тарифам", callback_data="buy"))
        #kb.add(InlineKeyboardButton(f"{EMOJI['home']} В главное меню", callback_data="main"))
        
        bot.edit_message_text(text, uid, call.message.id,
                            reply_markup=kb, parse_mode="Markdown")
    
    elif call.data == "my_key":
        keys = db.get_keys(uid)
        active_key = db.get_active_key(uid)
    
        if not active_key:
            text = f"{EMOJI['key']} *У вас нет активного ключа* {EMOJI['cross']}"
            kb = InlineKeyboardMarkup()
            kb.add(InlineKeyboardButton(f"{EMOJI['buy']} Купить VPN", callback_data="buy"))
            kb.add(InlineKeyboardButton(f"{EMOJI['back']} Назад", callback_data="back_main"))
            bot.edit_message_text(text, uid, call.message.id, reply_markup=kb, parse_mode="Markdown")
            return
    
        u_uuid = active_key[1]
        end_date = active_key[4]
        end_date_aware = MOSCOW_TZ.localize(end_date)
        now_aware = datetime.datetime.now(MOSCOW_TZ)
        delta = end_date_aware - now_aware
    
        if delta.total_seconds() <= 0:
            text = f"{EMOJI['key']} *Ключ истёк* {EMOJI['cross']}"
            kb = InlineKeyboardMarkup()
            kb.add(InlineKeyboardButton(f"{EMOJI['buy']} Купить VPN", callback_data="buy"))
            kb.add(InlineKeyboardButton(f"{EMOJI['back']} Назад", callback_data="back_main"))
            bot.edit_message_text(text, uid, call.message.id, reply_markup=kb, parse_mode="Markdown")
            return
    
        remaining = f"{delta.days} дн." if delta.days >= 1 else f"{int(delta.total_seconds() // 3600)} ч."
        end_date_formatted = end_date.replace(tzinfo=MOSCOW_TZ).strftime('%d.%m.%Y в %H:%M') + ' МСК'
    
        text = (
            f"🔑 *Детали ключа*\n\n"
            f"⏰ *Осталось:* **{remaining}**\n"
            f"До: {end_date_formatted}\n\n"
            f"Нажмите «Подключиться» и следуйте инструкциям ↓"
        )
    
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton("Подключиться ⚡", callback_data=f"connect_{u_uuid}"))
        kb.add(InlineKeyboardButton(f"{EMOJI['back']} Назад", callback_data="back_main"))
    
        bot.edit_message_text(text, uid, call.message.id, reply_markup=kb, parse_mode="Markdown")

    elif call.data.startswith("connect_"):
        u_uuid = call.data.replace("connect_", "")
        
        # Проверяем, что ключ существует
        db_cursor = db.conn.cursor()
        db_cursor.execute("SELECT end_date FROM keys WHERE uuid=? AND user_id=?", (u_uuid, uid))
        row = db_cursor.fetchone()
        
        if not row:
            bot.answer_callback_query(call.id, "Ключ не найден")
            return
    
        text = (
            f"Выберите ваше устройство:\n\n"
            f"Нажмите кнопку ниже — бот отправит инструкцию и ссылку"
        )
    
        kb = InlineKeyboardMarkup(row_width=2)
        kb.add(
            InlineKeyboardButton("📱 iPhone / iPad", callback_data=f"device_ios_{u_uuid}"),
            InlineKeyboardButton("🤖 Android", callback_data=f"device_android_{u_uuid}")
        )
        kb.add(InlineKeyboardButton(f"{EMOJI['back']} Назад", callback_data="my_key"))
    
        bot.edit_message_text(text, uid, call.message.id, reply_markup=kb, parse_mode="Markdown")

    elif call.data.startswith("device_ios_"):
        u_uuid = call.data.replace("device_ios_", "")
        sub_id = db.get_key_subid(u_uuid)
        if not sub_id:
            bot.answer_callback_query(call.id, "Подписка не найдена")
            return
    
        sub_link = generate_subscription_link(sub_id)
        deeplink = generate_happ_deeplink(sub_id)
    
        text = (
            f"📱 **Для iPhone / iPad**\n\n"
            f"1. Нажмите кнопку «Установить» и скачайте приложение Happ\n"
            f"2. После установки нажмите «Подключиться» — Happ откроется автоматически\n\n"
            f"Установка: https://apps.apple.com/ru/app/happ-proxy-utility-plus/id6746188973\n\n"
            f"Подключение:"
        )
    
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton("Установить", url="https://apps.apple.com/ru/app/happ-proxy-utility-plus/id6746188973"))
        kb.add(InlineKeyboardButton("Подключиться ⚡", url=deeplink))
        kb.add(InlineKeyboardButton(f"{EMOJI['back']} Назад", callback_data="my_key"))
    
        bot.edit_message_text(text, uid, call.message.id, reply_markup=kb, parse_mode="Markdown")

    elif call.data.startswith("device_android_"):
        u_uuid = call.data.replace("device_android_", "")
        sub_id = db.get_key_subid(u_uuid)
        if not sub_id:
            bot.answer_callback_query(call.id, "Подписка не найдена")
            return
    
        sub_link = generate_subscription_link(sub_id)
        deeplink = generate_happ_deeplink(sub_id)
    
        text = (
            f"🤖 **Для Android**\n\n"
            f"1. Нажмите кнопку «Установить» и скачайте приложение Happ\n"
            f"2. После установки нажмите «Подключиться» — Happ откроется автоматически\n\n"
            f"Установка: https://play.google.com/store/apps/details?id=com.happproxy&hl=ru\n\n"
            f"Подключение:"
        )
    
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton("Установить", url="https://play.google.com/store/apps/details?id=com.happproxy&hl=ru"))
        kb.add(InlineKeyboardButton("Подключиться ⚡", url=deeplink))
        kb.add(InlineKeyboardButton(f"{EMOJI['back']} Назад", callback_data="my_key"))
    
        bot.edit_message_text(text, uid, call.message.id, reply_markup=kb, parse_mode="Markdown")
    
    elif call.data.startswith("show_key_"):
        u_uuid = call.data.replace("show_key_", "")
        db_cursor = db.conn.cursor()
        db_cursor.execute("SELECT end_date FROM keys WHERE uuid=? AND user_id=?", (u_uuid, uid))
        row = db_cursor.fetchone()
    
        if not row:
            bot.answer_callback_query(call.id, "Ключ не найден")
            return
    
    
        end_date = datetime.datetime.fromisoformat(str(row[0]))
        remaining = get_remaining_time_str(end_date)
        link = generate_vless_link(u_uuid)
        end_date_formatted = end_date.replace(tzinfo=MOSCOW_TZ).strftime('%d.%m.%Y в %H:%M') + ' МСК'
        sub_id = db.get_key_subid(u_uuid) or u_uuid # fallback на uuid, если sub_id None
    
        # Используем MarkdownV2 для правильного экранирования
        text = (
            f"{EMOJI['key']} *Детали ключа*\n\n"
            f"{EMOJI['time']} *Осталось:* **{remaining}**\n"
            f"*До:* {end_date_formatted}\n\n"
            #f"{EMOJI['link']} *Обычная ссылка:*\n"
            #f"`{link}`\n\n"  # Используем код для ссылки
            f"Нажмите кнопку ниже — Happ откроется и добавит подписку автоматически!"
        )
    
        kb = InlineKeyboardMarkup()
        deeplink = generate_happ_deeplink(sub_id)
        kb.add(InlineKeyboardButton("Подключиться ⚡", url=deeplink))
        #kb.add(InlineKeyboardButton(f"{EMOJI['copy']} Скопировать ключ", callback_data=f"copy_{u_uuid}"))
        #kb.add(InlineKeyboardButton(f"{EMOJI['back']} Назад", callback_data="back_main"))
        kb.add(InlineKeyboardButton(f"{EMOJI['home']} Главное Меню", callback_data="main"))
    
        bot.edit_message_text(text, uid, call.message.id, reply_markup=kb, parse_mode="Markdown")
    
    elif call.data.startswith("copy_"):
        if call.data.startswith("copy_ref_"):
            user_id = int(call.data.replace("copy_ref_", ""))
            ref_link = generate_referral_link(user_id)
            bot.answer_callback_query(call.id,
                f"✅ Реферальная ссылка скопирована!\n\n{ref_link}",
                show_alert=True
            )
        else:
            u_uuid = call.data.replace("copy_", "")
            link = generate_vless_link(u_uuid)
            # Используем MarkdownV2 для показа ссылки
            bot.answer_callback_query(call.id, 
                f"✅ Ключ скопирован!\n\n`{link}`\n\nВставьте в приложение", 
                show_alert=True
            )
    
    elif call.data == "referral":
        kb, ref_link, ref_stats = get_referral_menu(uid)
        
        text = (
            f"{EMOJI['friends']} *Пригласите друга — получите бонус!* {EMOJI['gift']}\n\n"
            f"{EMOJI['trophy']} *Как это работает:*\n"
            f"1. Отправьте другу вашу реферальную ссылку\n"
            f"2. Друг должен нажать на ссылку и зарегистрироваться\n"
            f"3. Вы автоматически получаете *+{REFERRAL_REWARD_DAYS} дней VPN*\n\n"
            f"{EMOJI['stats']} *Ваша статистика:*\n"
            f"• Всего приглашено: *{ref_stats['total']}*\n"
            f"• Получено бонусов: *{ref_stats['rewarded']}*\n"
            f"• Всего дней бонусов: *{ref_stats['rewarded'] * REFERRAL_REWARD_DAYS}*\n\n"
            f"{EMOJI['link']} *Ваша реферальная ссылка:*\n"
            f"{ref_link}\n\n"
            f"{EMOJI['party']} Приглашайте друзей и пользуйтесь VPN бесплатно!"
        )
        
        bot.edit_message_text(text, uid, call.message.id,
                            reply_markup=kb, parse_mode="Markdown")
    
    elif call.data == "ref_stats":
        ref_stats = db.get_referrals_stats(uid)
        
        text = (
            f"{EMOJI['stats']} *Ваша реферальная статистика*\n\n"
            f"{EMOJI['friends']} *Всего приглашено друзей:* {ref_stats['total']}\n"
            f"{EMOJI['check']} *Получено бонусов:* {ref_stats['rewarded']}\n"
            f"{EMOJI['gift']} *Всего дней бонусов:* {ref_stats['rewarded'] * REFERRAL_REWARD_DAYS}\n\n"
            f"{EMOJI['trophy']} *Приглашайте больше друзей!*\n"
            f"Каждый новый друг = +{REFERRAL_REWARD_DAYS} дней VPN\n\n"
            f"{EMOJI['diamond']} Чем больше друзей, тем дольше VPN!"
        )
        
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton(f"{EMOJI['friends']} Вернуться к рефералке", callback_data="referral"))
        #kb.add(InlineKeyboardButton(f"{EMOJI['back']} Назад", callback_data="back_main"))
        
        bot.edit_message_text(text, uid, call.message.id,
                            reply_markup=kb, parse_mode="Markdown")
    
    elif call.data == "info":
        text = (
            f"{EMOJI['crown']} *MAGAMIX VPN* {EMOJI['fire']}\n\n"
            f"{EMOJI['rocket']} *Лучший VPN для вашей безопасности и свободы!*\n\n"
            f"{EMOJI['speed']} *Наши преимущества:*\n"
            f"• Максимальная скорость подключения\n"
            f"• Полная анонимность в сети\n"
            f"• Защита от слежки и хакеров\n"
            f"• Доступ к заблокированным сайтам\n"
            f"• Безлимитный трафик\n"
            f"• Поддержка 24/7\n\n"
            f"{EMOJI['gift']} *Реферальная программа:*\n"
            f"• Пригласите друга → получите +{REFERRAL_REWARD_DAYS} дней\n"
            f"• Нет ключа? Создастся новый на {REFERRAL_REWARD_DAYS} дней\n"
            f"• Есть ключ? Он продлится на {REFERRAL_REWARD_DAYS} дней\n\n"
            f"{EMOJI['key']} *Как начать пользоваться:*\n"
            f"1. Купите подписку в разделе «Купить VPN»\n"
            f"2. Получите ключ в «Мои ключи»\n"
            f"3. Настройте приложение за 2 минуты\n"
            f"4. Наслаждайтесь свободным интернетом!\n\n"
        )
        
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton(f"{EMOJI['buy']} Купить VPN", callback_data="buy"))
        kb.add(InlineKeyboardButton(f"{EMOJI['friends']} Пригласить друга", callback_data="referral"))
        kb.add(InlineKeyboardButton(f"{EMOJI['support']} Поддержка", url="https://t.me/MAGAMIX_support"))
        kb.add(InlineKeyboardButton(f"{EMOJI['back']} Назад", callback_data="back_main"))
        
        bot.edit_message_text(text, uid, call.message.id,
                            reply_markup=kb, parse_mode="Markdown")

    elif call.data.startswith("adm_decline_"):
        if call.from_user.id != ADMIN_ID:
            bot.answer_callback_query(call.id, "⛔ Доступ запрещен!")
            return
    
        target_id = int(call.data.split("_")[2])
    
    # Можно добавить логику возврата статуса в pending или уведомление пользователю
        try:
            bot.send_message(target_id, 
                f"{EMOJI['cross']} *Оплата отклонена.*\n\n"
                f"Проверьте реквизиты и отправьте новый чек.",
                parse_mode="Markdown"
            )
            bot.answer_callback_query(call.id, "Оплата отклонена")
            bot.edit_message_text("Оплата отклонена", ADMIN_ID, call.message.id)
        except Exception as e:
            print(f"Ошибка отклонения: {e}")
    
    elif call.data.startswith("adm_ok_"):
        if call.from_user.id != ADMIN_ID:
            bot.answer_callback_query(call.id, "⛔ Доступ запрещен!")
            return
    
        target_id = int(call.data.split("_")[2])  # ← исправлено: split("_")
        plan_key = db.get_last_pending_plan(target_id)
        if not plan_key:
            bot.send_message(ADMIN_ID, "Нет ожидающих платежей.")
            return
    
        days = PRICES[plan_key]['days']
        u_uuid = str(uuid.uuid4())
        email = f"user_{target_id}_{int(time.time())}"
    
        sub_id = add_user_to_xray(u_uuid, email, days)
        if sub_id:
            db.add_key(target_id, u_uuid, SID, days)
            db.update_key_subid(u_uuid, sub_id)
        
            # Ссылка-подписка (или VLESS, если хочешь)
            sub_link = generate_subscription_link(sub_id)
        
            success_text = (
                f"{EMOJI['check']} *Оплата подтверждена!*\n\n"
                f"{EMOJI['key']} *Ваш ключ на {days} дней:*\n"
                f"`{sub_link}`\n\n"
                f"{EMOJI['info']} *Инструкция:*\n"
                f"1. Откройте Happ Plus / Hiddify\n"
                f"2. Нажмите «+» → «Добавить подписку»\n"
                f"3. Вставьте ссылку выше\n"
                f"4. Наслаждайтесь VPN! {EMOJI['rocket']}"
            )
            
            bot.send_message(target_id, success_text, parse_mode="Markdown")
        
            # Уведомление админу
            admin_text = (
                f"{EMOJI['check']} *Ключ выдан!*\n"
                f"Пользователь: {target_id}\n"
                f"Тариф: {PRICES[plan_key]['name']} ({days} дней)\n"
                f"Sub ID: {sub_id}"
            )
            bot.edit_message_text(admin_text, ADMIN_ID, call.message.id)
        else:
            bot.send_message(ADMIN_ID, f"{EMOJI['cross']} Ошибка при создании ключа")

# --- Приём чеков ---
@bot.message_handler(content_types=['photo'])
def handle_receipt(message):
    uid = message.from_user.id
    username = message.from_user.username or "скрыт"
    
    # Получаем последний pending план этого пользователя
    plan_key = db.get_last_pending_plan(uid)
    if not plan_key:
        bot.send_message(uid, "У вас нет ожидающего платежа.")
        return
    
    data = PRICES[plan_key]
    price = data['price']
    name = data['name']
    days = data['days']
    
    bot.send_message(uid,
        f"{EMOJI['check']} *Чек принят!*\n\n"
        f"{EMOJI['time']} Проверка займёт несколько минут.\n"
        f"{EMOJI['info']} После проверки ключ придёт автоматически.",
        parse_mode="Markdown"
    )
    
    # Пересылаем чек админу
    bot.forward_message(ADMIN_ID, message.chat.id, message.id)
    
    # Красивое сообщение админу с полной инфой
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton(f"{EMOJI['check']} Подтвердить оплату", callback_data=f"adm_ok_{uid}"))
    kb.add(InlineKeyboardButton(f"{EMOJI['cross']} Отклонить", callback_data=f"adm_decline_{uid}"))  # ← новая кнопка, добавь обработку ниже
    
    admin_text = (
        f"{EMOJI['money']} *Новый чек от пользователя!*\n\n"
        f"👤 **Пользователь:** ID {uid} | @{username}\n"
        f"💳 **Тариф:** {name} ({days} дней)\n"
        f"💰 **Сумма:** {price}₽\n"
        f"📅 **Дата/время:** {datetime.datetime.now(MOSCOW_TZ).strftime('%d.%m.%Y %H:%M')} МСК\n"
        f"Статус: Ожидает подтверждения\n\n"
        f"Чек прикреплён выше ↓"
    )
    
    bot.send_message(ADMIN_ID, admin_text, reply_markup=kb, parse_mode="Markdown")

# --- Очистка просроченных ---
def auto_delete_loop():
    while True:
        try:
            expired = db.get_all_expired_keys()
            for user_id, u_uuid in expired:
                db_cursor = db.conn.cursor()
                db_cursor.execute("SELECT * FROM keys WHERE uuid = ?", (u_uuid,))
                row = db_cursor.fetchone()
                if row:
                    email = f"user_{user_id}_{u_uuid[:8]}"
                    

                    try:
                        bot.send_message(
                            user_id,
                            f"{EMOJI['cross']} *Срок действия ключа истек*\n\n"
                            f"{EMOJI['info']} Ключ был автоматически удален.\n"
                            f"{EMOJI['buy']} Приобретите новый ключ в разделе «Купить VPN»\n"
                            f"{EMOJI['friends']} Или пригласите друга и получите +{REFERRAL_REWARD_DAYS} дней!",
                            parse_mode="Markdown"
                        )
                    except:
                        pass
        except Exception as e:
            print(f"[CLEANUP ERROR] {e}")
        time.sleep(1800)

def calculate_total_payments():
    """Считает общую сумму платежей"""
    try:
        # Используем курсор из модуля db
        db_cursor = db.conn.cursor()
        
        db_cursor.execute("""
            SELECT plan_key, COUNT(*) as count 
            FROM payments 
            WHERE status = 'confirmed' 
            GROUP BY plan_key
        """)
        
        total = 0
        rows = db_cursor.fetchall()
        
        for plan_key, count in rows:
            if plan_key in PRICES:  # PRICES из config.py
                total += PRICES[plan_key]['price'] * count
                
        return total
    except Exception as e:
        print(f"[CALCULATE PAYMENTS ERROR] {e}")
        return 0


def notify_expiry_warning():
    while True:
        try:
            # Используем курсор из модуля db
            db_cursor = db.conn.cursor()
            
            # Получаем все активные ключи, где осталось 1–2 дня
            db_cursor.execute("""
                SELECT user_id, uuid, end_date 
                FROM keys 
                WHERE is_active = 1 
                AND end_date > DATETIME('now') 
                AND end_date <= DATETIME('now', '+2 days')
                AND end_date > DATETIME('now', '+1 day')  -- только 1–2 дня осталось
            """)
            
            rows = db_cursor.fetchall()
            
            for row in rows:
                user_id, u_uuid, end_date_str = row
                end_date = datetime.datetime.fromisoformat(end_date_str)
                remaining_days = (end_date - datetime.datetime.now()).days
                
                # Проверяем, не отправляли ли уже уведомление
                # Пока просто отправляем раз в день
                
                text = (
                    f"⚠️ *Ваш ключ скоро истечёт!*\n\n"
                    f"Осталось **{remaining_days} дней** до {end_date.strftime('%d.%m.%Y %H:%M')} МСК\n\n"
                    f"🔑 Не забудьте продлить подписку в разделе «Купить VPN»!\n"
                    f"Приглашай друзей — +{REFERRAL_REWARD_DAYS} дней бесплатно! 👥"
                )
                
                try:
                    bot.send_message(user_id, text, parse_mode="Markdown")
                    print(f"[NOTIFY] Отправлено предупреждение пользователю {user_id} (ключ {u_uuid})")
                except Exception as e:
                    print(f"[NOTIFY ERROR] Пользователь {user_id}: {e}")
        
        except Exception as e:
            print(f"[NOTIFY LOOP ERROR] {e}")
        
        time.sleep(86400)  # Проверять раз в сутки (24 часа)

threading.Thread(target=notify_expiry_warning, daemon=True).start()
threading.Thread(target=auto_delete_loop, daemon=True).start()

if __name__ == "__main__":
    print(f"{EMOJI['rocket']} Бот запущен {datetime.datetime.now(MOSCOW_TZ)}")
    print(f"{EMOJI['crown']} MAGAMIX VPN + Happ deeplink готов!")
    bot.infinity_polling()
