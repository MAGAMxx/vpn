import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import datetime
import uuid
import requests
import json
import time
import threading
import pytz
import db
import base64
from config import *

requests.packages.urllib3.disable_warnings()
bot = telebot.TeleBot(BOT_TOKEN)
session = requests.Session()

# Московский часовой пояс
MOSCOW_TZ = pytz.timezone('Europe/Moscow')

# Emoji для оформления
EMOJI = {
    "home": "🏠",
    "back": "↩️",
    "key": "🔑",
    "buy": "💳",
    "support": "🆘",
    "time": "⏰",
    "link": "🔗",
    "copy": "📋",
    "check": "✅",
    "cross": "❌",
    "info": "ℹ️",
    "rocket": "🚀",
    "crown": "👑",
    "shield": "🛡️",
    "wifi": "📡",
    "lock": "🔒",
    "unlock": "🔓",
    "star": "⭐",
    "fire": "🔥",
    "money": "💰",
    "card": "💎",
    "phone": "📱",
    "bank": "🏦",
    "download": "📥",
    "upload": "📤",
    "speed": "⚡",
    "global": "🌐",
    "settings": "⚙️",
    "friends": "👥",
    "gift": "🎁",
    "invite": "📨",
    "stats": "📊",
    "trophy": "🏆",
    "medal": "🏅",
    "party": "🎉",
    "diamond": "💎"
}

# Реферальная система
REFERRAL_REWARD_DAYS = 5  # +5 дней за каждого друга

# --- Взаимодействие с 3X-UI ---
def xui_login():
    try:
        login_url = f"{PANEL_URL}/{PANEL_PATH}/login"
        r = session.post(login_url, data={"username": PANEL_USER, "password": PANEL_PASS}, verify=False, timeout=10)
        return r.status_code == 200
    except Exception as e:
        print(f"[LOGIN ERROR] {e}")
        return False

def add_user_to_xray(user_uuid, email, days):
    if not xui_login():
        print("[ADD CLIENT] Не удалось авторизоваться")
        return False
    
    expiry_time = int((time.time() + (days * 86400)) * 1000)
    
    payload = {
        "id": INBOUND_ID,
        "settings": json.dumps({
            "clients": [{
                "id": user_uuid,
                "alterId": 0,
                "email": email,
                "limitIp": 2,
                "totalGB": 0,
                "expiryTime": expiry_time,
                "enable": True,
                "tgId": "",
                "subId": ""
            }]
        })
    }
    
    try:
        url = f"{PANEL_URL}/{PANEL_PATH}/panel/api/inbounds/addClient"
        r = session.post(url, json=payload, verify=False, timeout=15)
        response_data = r.json()
        if response_data.get("success"):
            return True
        else:
            msg = response_data.get("msg", "")
            if "Duplicate email" in msg:
                print(f"[ADD CLIENT] Пропуск: дубликат email {email}")
                return True
            print(f"[ADD CLIENT] Ошибка панели: {msg}")
            return False
    except Exception as e:
        print(f"[ADD CLIENT ERROR] {e}")
        return False

def update_user_in_xray(email, new_days):
    """Обновляет срок действия пользователя в Xray"""
    if not xui_login():
        return False
    
    try:
        # Сначала получаем текущие настройки пользователя
        url = f"{PANEL_URL}/{PANEL_PATH}/panel/api/inbounds/get/{INBOUND_ID}"
        r = session.get(url, verify=False, timeout=10)
        data = r.json()
        
        if not data.get("success"):
            return False
        
        settings = json.loads(data["obj"]["settings"])
        clients = settings.get("clients", [])
        
        # Находим нужного клиента
        for client in clients:
            if client.get("email") == email:
                # Обновляем expiryTime
                expiry_time = int((time.time() + (new_days * 86400)) * 1000)
                client["expiryTime"] = expiry_time
                break
        
        # Обновляем настройки
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
    return (f"vless://{u_uuid}@{SERVER_IP}:{SERVER_PORT}?type=tcp&encryption=none&security=reality"
            f"&sni={SNI}&fp={FP}&pbk={PBK}&sid={SID}&spx=%2F#🔥НИДЕРЛАНДЫ 🇳🇱")

def generate_happ_plus_link(user_id):
    """Специально для HAPP+ с кастомным интерфейсом"""
    active_key = db.get_active_key(user_id)
    if not active_key:
        return None
    
    uuid_str = active_key[1]
    email = active_key[6]
    
    # Получаем статистику
    up_gb, down_gb, total_gb = get_client_traffic_stats(email)
    end_date = active_key[4]
    
    # Форматируем данные
    expiry_date = end_date.replace(tzinfo=MOSCOW_TZ).strftime('%d.%m.%Y')
    current_date = datetime.datetime.now(MOSCOW_TZ).strftime('%d.%m.%Y %H:%M')
    
    # Форматируем трафик
    if total_gb is not None:
        if total_gb < 1:
            traffic_used = f"{total_gb*1024:.1f} MB"
        elif total_gb < 1024:
            traffic_used = f"{total_gb:.1f} GB"
        else:
            traffic_used = f"{total_gb/1024:.1f} TB"
    else:
        traffic_used = "0 GB"
    
    # Создаем кастомный интерфейс для HAPP+
    subscription_info = {
        "version": 2,
        "title": "🔥 MAGAMIX VPN",
        "subtitle": "Premium Netherlands Server",
        "icon": "https://img.icons8.com/color/96/000000/vpn.png",
        "header": {
            "title": "MAGAMIX VPN",
            "subtitle": "🇳🇱 Netherlands | Premium",
            "icon": "https://img.icons8.com/color/96/000000/netherlands.png"
        },
        "servers": [{
            "name": "🇳🇱 Netherlands | Premium",
            "type": "vless",
            "address": SERVER_IP,
            "port": SERVER_PORT,
            "id": uuid_str,
            "security": "reality",
            "flow": "xtls-rprx-vision",
            "sni": SNI,
            "fingerprint": FP,
            "publicKey": PBK,
            "shortId": SID,
            "status": "🟢 Online",
            "ping": "25ms",
            "load": "15%"
        }],
        "user": {
            "id": str(user_id),
            "expiry": expiry_date,
            "remaining": get_remaining_time_str(end_date),
            "traffic": {
                "used": traffic_used,
                "total": "∞ GB",
                "percentage": 0
            }
        },
        "referral": {
            "enabled": True,
            "code": f"ref{user_id}",
            "reward": f"+{REFERRAL_REWARD_DAYS} дней",
            "message": f"Пригласи друга и получи +{REFERRAL_REWARD_DAYS} дней!"
        },
        "ui": {
            "theme": "dark",
            "primaryColor": "#FF6B35",
            "backgroundColor": "#0F172A",
            "cardColor": "#1E293B",
            "textColor": "#F8FAFC",
            "showStats": True,
            "showTrafficChart": True,
            "compactMode": False
        },
        "meta": {
            "provider": "MAGAMIX VPN",
            "website": "https://t.me/" + str(bot.get_me().username),
            "support": "@nejnayatp3",
            "version": "1.0"
        }
    }
    
    # Конвертируем в base64
    subscription_json = json.dumps(subscription_info, ensure_ascii=False, indent=2)
    subscription_base64 = base64.b64encode(subscription_json.encode()).decode()
    
    # Генерируем ссылку
    base_link = (f"vless://{uuid_str}@{SERVER_IP}:{SERVER_PORT}?"
                 f"security=reality&encryption=none&type=tcp&"
                 f"sni={SNI}&fp={FP}&pbk={PBK}&sid={SID}&"
                 f"flow=xtls-rprx-vision")
    
    # Добавляем subscriptionUserInfo если поддерживается
    if len(subscription_base64) + len(base_link) < 2000:  # Telegram limit
        link = f"{base_link}&subscriptionUserInfo={subscription_base64}#🔥 MAGAMIX VPN"
    else:
        # Если слишком длинная, используем простую версию
        link = f"{base_link}#🔥 MAGAMIX VPN | 🇳🇱 | {expiry_date}"
    
    return link

def generate_vless_link(uuid_str):
    """Базовая генерация VLESS ссылки (на всякий случай)"""
    return (f"vless://{uuid_str}@{SERVER_IP}:{SERVER_PORT}?"
            f"security=reality&encryption=none&type=tcp&"
            f"sni={SNI}&fp={FP}&pbk={PBK}&sid={SID}&"
            f"flow=xtls-rprx-vision"
            f"#🔥 MAGAMIX VPN")


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
    """Генерирует реферальную ссылку"""
    return f"https://t.me/{bot.get_me().username}?start=ref{user_id}"

def give_referral_reward(referrer_id, referred_id):
    """Выдает награду за реферала"""
    try:
        # Проверяем, не выдавалась ли уже награда
        db.cursor.execute("""
            SELECT reward_given FROM referrals 
            WHERE referrer_id = ? AND referred_id = ?
        """, (referrer_id, referred_id))
        
        row = db.cursor.fetchone()
        if row and row[0] == 1:
            return False  # Награда уже выдана
        
        # Получаем активный ключ реферера
        active_key = db.get_active_key(referrer_id)
        
        if active_key:
            # Продлеваем существующий ключ на 5 дней
            success = db.extend_key_days(referrer_id, REFERRAL_REWARD_DAYS)
            if success:
                # Обновляем в Xray
                uuid_val = active_key[1]
                email = f"user_{referrer_id}_{uuid_val[:8]}"
                
                # Получаем новую дату окончания
                new_end_date = active_key[4] + datetime.timedelta(days=REFERRAL_REWARD_DAYS)
                days_until_new_end = (new_end_date - datetime.datetime.now()).days
                
                if days_until_new_end > 0:
                    update_user_in_xray(email, days_until_new_end)
                
                # Записываем награду в БД
                db.add_referral_reward(referrer_id, referred_id, REFERRAL_REWARD_DAYS)
                
                # Отправляем уведомление рефереру
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
            # Создаем новый ключ на 5 дней
            u_uuid = str(uuid.uuid4())
            email = f"ref_{referrer_id}_{int(time.time())}"
            
            if add_user_to_xray(u_uuid, email, REFERRAL_REWARD_DAYS):
                db.add_key(referrer_id, u_uuid, SID, REFERRAL_REWARD_DAYS)
                db.add_referral_reward(referrer_id, referred_id, REFERRAL_REWARD_DAYS)
                
                # Отправляем уведомление рефереру
                try:
                    bot.send_message(
                        referrer_id,
                        f"{EMOJI['party']} *Бонус за друга!*\n\n"
                        f"{EMOJI['gift']} Вам выдан новый ключ на *{REFERRAL_REWARD_DAYS} дней*!\n"
                        f"{EMOJI['friends']} Ваш друг успешно зарегистрировался по вашей ссылке.\n"
                        f"{EMOJI['key']} Ключ доступен в разделе «Мои ключи»\n\n"
                        f"{EMOJI['trophy']} Приглашайте больше друзей и получайте бонусы!",
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
        InlineKeyboardButton(f"{EMOJI['key']} Мои ключи", callback_data="my_keys")
    )
    kb.add(
        InlineKeyboardButton(f"{EMOJI['friends']} Пригласить друга", callback_data="referral"),
        InlineKeyboardButton(f"{EMOJI['support']} Поддержка", url="https://t.me/nejnayatp3")
    )
    kb.add(InlineKeyboardButton(f"{EMOJI['info']} Информация", callback_data="info"))
    return kb

def get_back_button(to="main"):
    """Кнопка назад"""
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton(f"{EMOJI['back']} Назад", callback_data=f"back_{to}"))
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
            f"{EMOJI['copy']} Скопировать ключ", 
            callback_data=f"copy_{uuid_key}"
        ))
    kb.add(InlineKeyboardButton(f"{EMOJI['back']} Назад в Мои ключи", callback_data="my_keys"))
    kb.add(InlineKeyboardButton(f"{EMOJI['home']} В главное меню", callback_data="main"))
    return kb

def get_referral_menu(user_id):
    """Меню реферальной системы"""
    kb = InlineKeyboardMarkup(row_width=1)
    
    # Генерируем реферальную ссылку
    ref_link = generate_referral_link(user_id)
    
    # Получаем статистику
    ref_stats = db.get_referrals_stats(user_id)
    
    kb.add(InlineKeyboardButton(
        f"{EMOJI['invite']} Скопировать ссылку", 
        callback_data=f"copy_ref_{user_id}"
    ))
    
    kb.add(InlineKeyboardButton(
        f"{EMOJI['stats']} Моя статистика", 
        callback_data="ref_stats"
    ))
    
    kb.add(InlineKeyboardButton(f"{EMOJI['back']} Назад", callback_data="back_main"))
    kb.add(InlineKeyboardButton(f"{EMOJI['home']} В главное меню", callback_data="main"))
    
    return kb, ref_link, ref_stats

# --- Обработка команд ---
@bot.message_handler(commands=['start'])
def start_handler(message):
    user_id = message.from_user.id
    username = message.from_user.username
    
    # Проверяем, есть ли реферальный код в команде
    referrer_id = None
    if len(message.text.split()) > 1:
        ref_code = message.text.split()[1]
        if ref_code.startswith('ref'):
            try:
                referrer_id = int(ref_code[3:])  # Убираем 'ref' в начале
                # Проверяем, что реферер существует и это не сам пользователь
                if referrer_id == user_id:
                    referrer_id = None
            except:
                referrer_id = None
    
    # Регистрируем пользователя
    is_new_user = db.add_user(user_id, username, referrer_id)
    
    if is_new_user and referrer_id:
        # Если это новый пользователь и есть реферер, выдаем награду
        success = give_referral_reward(referrer_id, user_id)
        if not success:
            print(f"Не удалось выдать награду рефереру {referrer_id}")
    
    user_keys = db.get_keys(user_id)
    active_key = db.get_active_key(user_id)
    
    if not active_key:  # Первый раз — триал
        u_uuid = str(uuid.uuid4())
        email = f"trial_{user_id}_{int(time.time())}"
        
        if add_user_to_xray(u_uuid, email, 3):
            db.add_key(user_id, u_uuid, SID, 3)
            text = (
                f"{EMOJI['crown']} *Добро пожаловать в MAGAMIX VPN* {EMOJI['fire']}\n\n"
                f"{EMOJI['star']} *Вам выдан БЕСПЛАТНЫЙ пробный период на 3 дня!*\n"
                f"{EMOJI['key']} Ключ доступен в разделе «Мои ключи»\n\n"
                f"{EMOJI['gift']} *Бонусная программа:*\n"
                f"• Пригласите друга → получите +{REFERRAL_REWARD_DAYS} дней\n"
                f"• Нет ключа? Создастся новый на {REFERRAL_REWARD_DAYS} дней\n"
                f"• Есть ключ? Он продлится на {REFERRAL_REWARD_DAYS} дней\n\n"
                f"{EMOJI['info']} *Выберите действие ниже:*"
            )
        else:
            text = (
                f"{EMOJI['crown']} *Добро пожаловать в MAGAMIX VPN* {EMOJI['fire']}\n\n"
                f"{EMOJI['cross']} *Не удалось выдать пробный период*\n"
                f"{EMOJI['support']} Свяжитесь с поддержкой: @nejnayatp3\n\n"
                f"{EMOJI['info']} *Выберите действие ниже:*"
            )
    else:
        text = (
            f"{EMOJI['crown']} *С возвращением в MAGAMIX VPN!* {EMOJI['fire']}\n\n"
            f"{EMOJI['rocket']} *Ваш VPN активен и готов к работе!*\n"
            f"{EMOJI['gift']} *Не забывайте про реферальную программу!*\n"
            f"Приглашайте друзей и получайте бонусы {EMOJI['diamond']}\n\n"
            f"{EMOJI['info']} *Выберите действие ниже:*"
        )
    
    bot.send_message(user_id, text, reply_markup=get_main_menu(), parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: True)
def query_handler(call):
    uid = call.from_user.id
    
    # Обработка кнопки "Назад"
    if call.data.startswith("back_"):
        target = call.data.replace("back_", "")
        if target == "main":
            text = (
                f"{EMOJI['crown']} *Главное меню MAGAMIX VPN* {EMOJI['fire']}\n\n"
                f"{EMOJI['info']} *Выберите действие:*"
            )
            bot.edit_message_text(text, uid, call.message.id, 
                                 reply_markup=get_main_menu(), parse_mode="Markdown")
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
        db.add_payment(uid, plan_key)
        
        text = (
            f"{EMOJI['card']} *Оплата тарифа: {data['name']}*\n\n"
            f"{EMOJI['money']} *Сумма к оплате:* {data['price']}₽\n"
            f"{EMOJI['bank']} *Банк для перевода:* {PAY_BANK}\n"
            f"{EMOJI['phone']} *Номер для перевода:* `{PAY_PHONE}`\n\n"
            f"{EMOJI['info']} *Инструкция:*\n"
            f"1. Переведите {data['price']}₽ на указанный номер\n"
            f"2. Сохраните чек об оплате\n"
            f"3. Отправьте скриншот чека в этот чат\n\n"
            f"{EMOJI['check']} После проверки ключ будет выдан автоматически!"
        )
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton(f"{EMOJI['back']} Назад к тарифам", callback_data="buy"))
        kb.add(InlineKeyboardButton(f"{EMOJI['home']} В главное меню", callback_data="main"))
        
        bot.edit_message_text(text, uid, call.message.id, 
                             reply_markup=kb, parse_mode="Markdown")
    
    elif call.data == "my_keys":
        keys = db.get_keys(uid)
        active_key = db.get_active_key(uid)
        
        if not active_key:
            text = f"{EMOJI['key']} *У вас нет активных ключей* {EMOJI['cross']}"
            kb = InlineKeyboardMarkup()
            kb.add(InlineKeyboardButton(f"{EMOJI['buy']} Купить VPN", callback_data="buy"))
            kb.add(InlineKeyboardButton(f"{EMOJI['back']} Назад", callback_data="back_main"))
            bot.edit_message_text(text, uid, call.message.id, 
                                 reply_markup=kb, parse_mode="Markdown")
            return

        # Показываем только активный ключ
        u_uuid = active_key[1]
        end_date = active_key[4]
        
        end_date_aware = MOSCOW_TZ.localize(end_date)
        now_aware = datetime.datetime.now(MOSCOW_TZ)
        delta = end_date_aware - now_aware
        
        if delta.total_seconds() <= 0:
            text = f"{EMOJI['key']} *Ваш ключ истек* {EMOJI['cross']}"
            kb = InlineKeyboardMarkup()
            kb.add(InlineKeyboardButton(f"{EMOJI['buy']} Купить VPN", callback_data="buy"))
            kb.add(InlineKeyboardButton(f"{EMOJI['back']} Назад", callback_data="back_main"))
            bot.edit_message_text(text, uid, call.message.id, 
                                 reply_markup=kb, parse_mode="Markdown")
            return
        
        days = delta.days
        remaining = f"{days} дн." if days >= 1 else f"{int(delta.total_seconds() // 3600)} ч."
        
        text = (
            f"{EMOJI['key']} *Ваш активный ключ*\n\n"
            f"{EMOJI['time']} *Осталось:* **{remaining}**\n"
            f" *Действует до:* {end_date.replace(tzinfo=MOSCOW_TZ).strftime('%d.%m.%Y в %H:%M')} МСК\n\n"
            f"{EMOJI['info']} *Что дальше?*"
        )
        
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton(
            f"{EMOJI['copy']} Получить ссылку подключения", 
            callback_data=f"show_key_{u_uuid}"
        ))
        kb.add(InlineKeyboardButton(f"{EMOJI['back']} Назад", callback_data="back_main"))
        kb.add(InlineKeyboardButton(f"{EMOJI['home']} В главное меню", callback_data="main"))
        
        bot.edit_message_text(text, uid, call.message.id, 
                             reply_markup=kb, parse_mode="Markdown")
    
        elif call.data.startswith("show_key_"):
        u_uuid = call.data.replace("show_key_", "")
        db.cursor.execute("SELECT end_date, email FROM keys WHERE uuid=? AND user_id=?", (u_uuid, uid))
        row = db.cursor.fetchone()
        if not row:
            bot.answer_callback_query(call.id, "Ключ не найден")
            return

        end_date_str, email = row
        end_date = datetime.datetime.fromisoformat(end_date_str)
        remaining = get_remaining_time_str(end_date)
        
        # Получаем статистику трафика
        up_gb, down_gb, total_gb = get_client_traffic_stats(email)
        
        # Генерируем ссылку для HAPP+ с красивым профилем
        link = generate_happ_plus_link(uid)
        if not link:
            link = generate_vless_link(u_uuid)
        
        # Форматируем данные для отображения
        end_date_formatted = end_date.replace(tzinfo=MOSCOW_TZ).strftime('%d.%m.%Y в %H:%M') + ' МСК'
        
        # Показываем статистику трафика
        traffic_info = ""
        if total_gb is not None:
            if total_gb < 1:
                traffic_info = f"{total_gb*1024:.1f} MB"
            elif total_gb < 1024:
                traffic_info = f"{total_gb:.1f} GB"
            else:
                traffic_info = f"{total_gb/1024:.1f} TB"
        else:
            traffic_info = "0 GB"

        text = (
            f"{EMOJI['key']} *Детали ключа*\n\n"
            f"{EMOJI['time']} *Осталось:* **{remaining}**\n"
            f"{EMOJI['traffic']} *Использовано:* **{traffic_info}**\n"
            f"*Действует до:* {end_date_formatted}\n\n"
            f"{EMOJI['link']} *Ссылка подключения:*\n"
            f"`{link}`\n\n"
            f"{EMOJI['info']} *Инструкция по настройке:*\n"
            f"1. Скачайте приложение *Happ Plus* \n"
            f"2. Нажмите «+» → «Импорт из буфера обмена»\n"
            f"3. Скопируйте ссылку выше и вставьте в приложение\n"
            f"4. В HAPP+ вы увидите красивый интерфейс с иконкой!\n"
            f"5. Активируйте подключение и наслаждайтесь! {EMOJI['rocket']}"
        )
        
        bot.edit_message_text(text, uid, call.message.id, 
                             reply_markup=get_instructions_menu(u_uuid), 
                             parse_mode="Markdown")
    
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
            bot.answer_callback_query(call.id, "✅ Ключ скопирован! Вставьте в приложение", show_alert=True)
    
    elif call.data == "referral":
        kb, ref_link, ref_stats = get_referral_menu(uid)
        
        text = (
            f"{EMOJI['friends']} *Пригласите друга — получите бонус!* {EMOJI['gift']}\n\n"
            f"{EMOJI['trophy']} *Как это работает:*\n"
            f"1. Отправьте другу вашу реферальную ссылку\n"
            f"2. Друг должен нажать на ссылку и зарегистрироваться\n"
            f"3. Вы автоматически получаете *+{REFERRAL_REWARD_DAYS} дней VPN*\n\n"
            f"{EMOJI['info']} *Условия:*\n"
            f"• Если у вас есть активный ключ — он продлится\n"
            f"• Если ключа нет — создастся новый на {REFERRAL_REWARD_DAYS} дней\n"
            f"• Бонус начисляется за каждого нового пользователя\n\n"
            f"{EMOJI['stats']} *Ваша статистика:*\n"
            f"• Всего приглашено: *{ref_stats['total']}*\n"
            f"• Получено бонусов: *{ref_stats['rewarded']}*\n"
            f"• Всего дней бонусов: *{ref_stats['rewarded'] * REFERRAL_REWARD_DAYS}*\n\n"
            f"{EMOJI['link']} *Ваша реферальная ссылка:*\n"
            f"`{ref_link}`\n\n"
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
        kb.add(InlineKeyboardButton(f"{EMOJI['back']} Назад", callback_data="back_main"))
        
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
            f"{EMOJI['support']} *Техническая поддержка:* @nejnayatp3"
        )
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton(f"{EMOJI['buy']} Купить VPN", callback_data="buy"))
        kb.add(InlineKeyboardButton(f"{EMOJI['friends']} Пригласить друга", callback_data="referral"))
        kb.add(InlineKeyboardButton(f"{EMOJI['support']} Поддержка", url="https://t.me/nejnayatp3"))
        kb.add(InlineKeyboardButton(f"{EMOJI['back']} Назад", callback_data="back_main"))
        
        bot.edit_message_text(text, uid, call.message.id, 
                             reply_markup=kb, parse_mode="Markdown")
    
    elif call.data.startswith("adm_ok_"):
        if call.from_user.id != ADMIN_ID:
            bot.answer_callback_query(call.id, "⛔ Доступ запрещен!")
            return
            
        target_id = int(call.data.split("_")[2])
        plan_key = db.get_last_pending_plan(target_id)
        if not plan_key:
            bot.send_message(ADMIN_ID, "Нет ожидающих платежей.")
            return
        
        days = PRICES[plan_key]['days']
        u_uuid = str(uuid.uuid4())
        email = f"user_{target_id}_{int(time.time())}"
        
        if add_user_to_xray(u_uuid, email, days):
            db.add_key(target_id, u_uuid, SID, days)
            link = generate_vless_link(u_uuid)
            
            success_text = (
                f"{EMOJI['check']} *Оплата подтверждена!*\n\n"
                f"{EMOJI['key']} *Ваш ключ на {days} дней:*\n"
                f"`{link}`\n\n"
                f"{EMOJI['info']} *Инструкция:*\n"
                f"1. Скопируйте ссылку выше\n"
                f"2. Откройте Happ Plus / Hiddify\n"
                f"3. Нажмите «+» → «Импорт из буфера обмена»\n"
                f"4. Наслаждайтесь VPN! {EMOJI['rocket']}"
            )
            
            bot.send_message(target_id, success_text, parse_mode="Markdown")
            
            admin_text = f"{EMOJI['check']} Ключ выдан пользователю {target_id}"
            bot.edit_message_text(admin_text, ADMIN_ID, call.message.id)
        else:
            bot.send_message(ADMIN_ID, f"{EMOJI['cross']} Ошибка при связи с API 3X-UI")

# --- Приём чеков ---
@bot.message_handler(content_types=['photo'])
def handle_receipt(message):
    uid = message.from_user.id
    bot.send_message(uid, 
        f"{EMOJI['check']} *Чек принят!*\n\n"
        f"{EMOJI['time']} Проверка займет несколько минут.\n"
        f"{EMOJI['info']} После проверки ключ придет автоматически.",
        parse_mode="Markdown"
    )
    
    bot.forward_message(ADMIN_ID, message.chat.id, message.id)
    
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton(f"{EMOJI['check']} Подтвердить оплату", 
                               callback_data=f"adm_ok_{uid}"))
    
    bot.send_message(ADMIN_ID, 
        f"{EMOJI['money']} *Новый чек от пользователя*\n\n"
        f"ID: {uid}\n"
        f"Username: @{message.from_user.username or 'скрыт'}",
        reply_markup=kb,
        parse_mode="Markdown"
    )

# --- Очистка просроченных ---
def auto_delete_loop():
    while True:
        try:
            expired = db.get_all_expired_keys()
            for user_id, u_uuid in expired:
                db.cursor.execute("SELECT * FROM keys WHERE uuid = ?", (u_uuid,))
                row = db.cursor.fetchone()
                if row:
                    email = f"user_{user_id}_{u_uuid[:8]}"
                    
                    deleted = delete_user_from_xray(email)
                    if deleted:
                        db.delete_key_by_uuid(u_uuid)
                        try:
                            bot.send_message(user_id, 
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

threading.Thread(target=auto_delete_loop, daemon=True).start()

if __name__ == "__main__":
    print(f"{EMOJI['rocket']} Бот запущен в {datetime.datetime.now(MOSCOW_TZ).strftime('%Y-%m-%d %H:%M:%S %Z')}")
    print(f"{EMOJI['crown']} MAGAMIX VPN готов к работе!")
    print(f"{EMOJI['gift']} Реферальная система активна: +{REFERRAL_REWARD_DAYS} дней за друга")
    bot.infinity_polling()
