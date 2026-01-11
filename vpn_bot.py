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
from config import *
import base64

requests.packages.urllib3.disable_warnings()
bot = telebot.TeleBot(BOT_TOKEN)
session = requests.Session()

MOSCOW_TZ = pytz.timezone('Europe/Moscow')

EMOJI = {
    "home": "🏠", "back": "↩️", "key": "🔑", "buy": "💳", "support": "🆘",
    "time": "⏰", "link": "🔗", "copy": "📋", "check": "✅", "cross": "❌",
    "info": "ℹ️", "rocket": "🚀", "crown": "👑", "shield": "🛡️", "wifi": "📡",
    "lock": "🔒", "unlock": "🔓", "star": "⭐", "fire": "🔥", "money": "💰",
    "card": "💎", "phone": "📱", "bank": "🏦", "download": "📥", "upload": "📤",
    "speed": "⚡", "global": "🌐", "settings": "⚙️", "friends": "👥", "gift": "🎁",
    "invite": "📨", "stats": "📊", "trophy": "🏆", "medal": "🏅", "party": "🎉",
    "diamond": "💎", "traffic": "📈", "chart": "📉", "battery": "🔋", "calendar": "📅",
    "pro": "🚀", "vip": "👑", "flash": "⚡", "earth": "🌍", "cloud": "☁️",
    "security": "🛡️", "qrcode": "📱", "refresh": "🔄", "alert": "🚨"
}

REFERRAL_REWARD_DAYS = 5

def xui_login():
    try:
        login_url = f"{PANEL_URL}/{PANEL_PATH}/login"
        r = session.post(login_url, 
                        data={"username": PANEL_USER, "password": PANEL_PASS}, 
                        verify=False, 
                        timeout=10)
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
                "totalGB": 99999,  # Безлимитный трафик
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
            print(f"[ADD CLIENT] Пользователь {email} добавлен, дней: {days}")
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

def get_client_traffic_stats(email):
    """Получение статистики трафика из панели 3X-UI"""
    if not xui_login():
        return None, None, None
    
    try:
        # Получаем статистику клиента
        stats_url = f"{PANEL_URL}/{PANEL_PATH}/panel/api/inbounds/clientStats/{email}"
        r = session.get(stats_url, verify=False, timeout=10)
        
        if r.status_code == 200:
            stats_data = r.json()
            if stats_data.get("success"):
                obj = stats_data.get("obj", {})
                
                # Пытаемся получить трафик
                if "up" in obj and "down" in obj:
                    up_bytes = obj["up"]
                    down_bytes = obj["down"]
                    
                    # Конвертируем в ГБ
                    up_gb = up_bytes / (1024 ** 3)
                    down_gb = down_bytes / (1024 ** 3)
                    total_gb = up_gb + down_gb
                    
                    return up_gb, down_gb, total_gb
                
                elif "total" in obj:
                    total_bytes = obj["total"]
                    total_gb = total_bytes / (1024 ** 3)
                    return None, None, total_gb
        
        # Пробуем другой эндпоинт
        traffics_url = f"{PANEL_URL}/{PANEL_PATH}/panel/api/inbounds/getClientTraffics/{email}"
        r = session.get(traffics_url, verify=False, timeout=10)
        
        if r.status_code == 200:
            traffics_data = r.json()
            if traffics_data.get("success"):
                obj = traffics_data.get("obj", {})
                if "up" in obj and "down" in obj:
                    up_bytes = obj["up"]
                    down_bytes = obj["down"]
                    up_gb = up_bytes / (1024 ** 3)
                    down_gb = down_bytes / (1024 ** 3)
                    total_gb = up_gb + down_gb
                    return up_gb, down_gb, total_gb
        
        return None, None, None
        
    except Exception as e:
        print(f"[GET TRAFFIC STATS ERROR] {e}")
        return None, None, None

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

def generate_vless_link(uuid_str):
    """Базовая генерация VLESS ссылки"""
    return (f"vless://{uuid_str}@{SERVER_IP}:{SERVER_PORT}?type=tcp&encryption=none&security=reality"
            f"&sni={SNI}&fp={FP}&pbk={PBK}&sid={SID}&spx=%2F&flow=xtls-rprx-vision"
            f"#MAGAMIX%20VPN%20{EMOJI['fire']}")

def generate_beautiful_vless_link(user_id):
    """Генерация ссылки с красивым профилем для HAPP+"""
    active_key = db.get_active_key(user_id)
    if not active_key:
        return None
    
    uuid_str = active_key[1]
    email = active_key[6]
    
    # Получаем статистику трафика
    up_gb, down_gb, total_gb = get_client_traffic_stats(email)
    
    # Рассчитываем оставшиеся дни
    end_date = active_key[4]
    end_date_aware = MOSCOW_TZ.localize(end_date)
    now_aware = datetime.datetime.now(MOSCOW_TZ)
    delta = end_date_aware - now_aware
    
    if delta.total_seconds() <= 0:
        return None
    
    remaining_days = delta.days
    remaining_hours = int(delta.total_seconds() // 3600)
    
    if remaining_days >= 1:
        remaining_time = f"{remaining_days} дн."
    elif remaining_hours > 0:
        remaining_time = f"{remaining_hours} ч."
    else:
        remaining_time = "Менее часа"
    
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
    
    # Создаем красивый заголовок как в примере
    # Формат: Молния ВПН | Дата | Статус | Трафик | Истекает
    current_date = datetime.datetime.now(MOSCOW_TZ).strftime('%d.%m.%Y %H:%M')
    
    # Вычисляем оставшиеся дни до истечения
    expiry_date_str = end_date.replace(tzinfo=MOSCOW_TZ).strftime('%d.%m.%Y')
    
    # Создаем профиль как в примере
    profile_name = (
        f"🔥 MAGAMIX VPN\n"
        f"{current_date} | 🇳🇱 Нидерланды\n\n"
        f"{traffic_used} / ∞ GB\n"
        f"Истекает: {expiry_date_str}\n\n"
        f"+{REFERRAL_REWARD_DAYS} дней за друга! @{bot.get_me().username}"
    )
    
    # Кодируем для URL
    import urllib.parse
    encoded_name = urllib.parse.quote(profile_name)
    
    return (f"vless://{uuid_str}@{SERVER_IP}:{SERVER_PORT}?"
            f"type=tcp&encryption=none&security=reality"
            f"&sni={SNI}&fp={FP}&pbk={PBK}&sid={SID}&spx=%2F&flow=xtls-rprx-vision"
            f"#{encoded_name}")

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
    return f"https://t.me/{bot.get_me().username}?start=ref{user_id}"

def give_referral_reward(referrer_id, referred_id):
    try:
        # Проверяем, не выдавалась ли уже награда
        db.cursor.execute("""
            SELECT reward_given FROM referrals 
            WHERE referrer_id = ? AND referred_id = ?
        """, (referrer_id, referred_id))
        
        row = db.cursor.fetchone()
        if row and row[0] == 1:
            return False
        
        active_key = db.get_active_key(referrer_id)
        
        if active_key:
            success = db.extend_key_days(referrer_id, REFERRAL_REWARD_DAYS)
            if success:
                db.add_referral_reward(referrer_id, referred_id, REFERRAL_REWARD_DAYS)
                try:
                    bot.send_message(
                        referrer_id,
                        f"{EMOJI['party']} *Бонус за друга!*\n\n"
                        f"{EMOJI['gift']} Ваш ключ продлен на *+{REFERRAL_REWARD_DAYS} дней*!\n"
                        f"{EMOJI['friends']} Ваш друг успешно зарегистрировался.\n\n"
                        f"{EMOJI['trophy']} Приглашайте больше друзей!",
                        parse_mode="Markdown"
                    )
                except:
                    pass
                return True
        else:
            u_uuid = str(uuid.uuid4())
            email = f"ref_{referrer_id}_{int(time.time())}"
            
            if add_user_to_xray(u_uuid, email, REFERRAL_REWARD_DAYS):
                db.add_key(referrer_id, u_uuid, SID, REFERRAL_REWARD_DAYS, email)
                db.add_referral_reward(referrer_id, referred_id, REFERRAL_REWARD_DAYS)
                
                try:
                    bot.send_message(
                        referrer_id,
                        f"{EMOJI['party']} *Бонус за друга!*\n\n"
                        f"{EMOJI['gift']} Вам выдан ключ на *{REFERRAL_REWARD_DAYS} дней*!\n"
                        f"{EMOJI['key']} Ключ в разделе «Мои ключи»\n\n"
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
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton(f"{EMOJI['back']} Назад", callback_data=f"back_{to}"))
    return kb

def get_buy_menu():
    kb = InlineKeyboardMarkup()
    for k, v in PRICES.items():
        kb.add(InlineKeyboardButton(
            f"{EMOJI['card']} {v['name']} — {v['price']}₽", 
            callback_data=f"plan_{k}"
        ))
    kb.add(InlineKeyboardButton(f"{EMOJI['back']} Назад", callback_data="back_main"))
    return kb

@bot.message_handler(commands=['start'])
def start_handler(message):
    user_id = message.from_user.id
    username = message.from_user.username
    
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
    
    if is_new_user and referrer_id:
        success = give_referral_reward(referrer_id, user_id)
        if not success:
            print(f"Не удалось выдать награду рефереру {referrer_id}")
    
    active_key = db.get_active_key(user_id)
    
    if not active_key:
        u_uuid = str(uuid.uuid4())
        email = f"trial_{user_id}_{int(time.time())}"
        
        if add_user_to_xray(u_uuid, email, 3):
            db.add_key(user_id, u_uuid, SID, 3, email)
            text = (
                f"{EMOJI['crown']} *Добро пожаловать в MAGAMIX VPN* {EMOJI['fire']}\n\n"
                f"{EMOJI['star']} *БЕСПЛАТНЫЙ пробный период на 3 дня!*\n"
                f"{EMOJI['key']} Ключ в разделе «Мои ключи»\n\n"
                f"{EMOJI['gift']} *Реферальная программа:*\n"
                f"• Пригласи друга → получи +{REFERRAL_REWARD_DAYS} дней\n"
                f"• Безлимитный трафик {EMOJI['flash']}\n"
                f"• Максимальная скорость {EMOJI['speed']}\n\n"
                f"{EMOJI['info']} *Выберите действие:*"
            )
        else:
            text = (
                f"{EMOJI['crown']} *Добро пожаловать в MAGAMIX VPN* {EMOJI['fire']}\n\n"
                f"{EMOJI['cross']} *Не удалось выдать пробный период*\n"
                f"{EMOJI['support']} Поддержка: @nejnayatp3\n\n"
                f"{EMOJI['info']} *Выберите действие:*"
            )
    else:
        text = (
            f"{EMOJI['crown']} *С возвращением в MAGAMIX VPN!* {EMOJI['fire']}\n\n"
            f"{EMOJI['rocket']} *Ваш VPN активен!*\n"
            f"{EMOJI['gift']} *Приглашайте друзей за бонусы!*\n\n"
            f"{EMOJI['info']} *Выберите действие:*"
        )
    
    bot.send_message(user_id, text, reply_markup=get_main_menu(), parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: True)
def query_handler(call):
    uid = call.from_user.id
    
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
            f"{EMOJI['money']} *Выберите тариф* {EMOJI['card']}\n\n"
            f"{EMOJI['info']} *Все тарифы включают:*\n"
            f"• {EMOJI['speed']} Максимальная скорость\n"
            f"• {EMOJI['shield']} Полная защита\n"
            f"• {EMOJI['global']} Неограниченный трафик\n"
            f"• {EMOJI['settings']} Поддержка 24/7\n"
        )
        bot.edit_message_text(text, uid, call.message.id, 
                             reply_markup=get_buy_menu(), parse_mode="Markdown")
    
    elif call.data.startswith("plan_"):
        plan_key = call.data.replace("plan_", "")
        data = PRICES[plan_key]
        db.add_payment(uid, plan_key)
        
        text = (
            f"{EMOJI['card']} *Оплата: {data['name']}*\n\n"
            f"{EMOJI['money']} *Сумма:* {data['price']}₽\n"
            f"{EMOJI['bank']} *Банк:* {PAY_BANK}\n"
            f"{EMOJI['phone']} *Номер:* `{PAY_PHONE}`\n\n"
            f"{EMOJI['info']} *Инструкция:*\n"
            f"1. Переведите {data['price']}₽ на номер\n"
            f"2. Сохраните чек\n"
            f"3. Отправьте скриншот сюда\n\n"
            f"{EMOJI['check']} После проверки получите ключ!"
        )
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton(f"{EMOJI['back']} Назад к тарифам", callback_data="buy"))
        kb.add(InlineKeyboardButton(f"{EMOJI['home']} В главное меню", callback_data="main"))
        
        bot.edit_message_text(text, uid, call.message.id, 
                             reply_markup=kb, parse_mode="Markdown")
    
    elif call.data == "my_keys":
        active_key = db.get_active_key(uid)
        
        if not active_key:
            text = f"{EMOJI['key']} *Нет активных ключей* {EMOJI['cross']}"
            kb = InlineKeyboardMarkup()
            kb.add(InlineKeyboardButton(f"{EMOJI['buy']} Купить VPN", callback_data="buy"))
            kb.add(InlineKeyboardButton(f"{EMOJI['back']} Назад", callback_data="back_main"))
            bot.edit_message_text(text, uid, call.message.id, 
                                 reply_markup=kb, parse_mode="Markdown")
            return

        u_uuid = active_key[1]
        email = active_key[6]
        end_date = active_key[4]
        
        # Получаем статистику трафика
        up_gb, down_gb, total_gb = get_client_traffic_stats(email)
        
        end_date_aware = MOSCOW_TZ.localize(end_date)
        now_aware = datetime.datetime.now(MOSCOW_TZ)
        delta = end_date_aware - now_aware
        
        if delta.total_seconds() <= 0:
            text = f"{EMOJI['key']} *Ключ истек* {EMOJI['cross']}"
            kb = InlineKeyboardMarkup()
            kb.add(InlineKeyboardButton(f"{EMOJI['buy']} Купить VPN", callback_data="buy"))
            kb.add(InlineKeyboardButton(f"{EMOJI['back']} Назад", callback_data="back_main"))
            bot.edit_message_text(text, uid, call.message.id, 
                                 reply_markup=kb, parse_mode="Markdown")
            return
        
        days = delta.days
        remaining = f"{days} дн." if days >= 1 else f"{int(delta.total_seconds() // 3600)} ч."
        
        # Форматируем трафик
        traffic_text = ""
        if total_gb is not None:
            if total_gb < 1:
                traffic_text = f"{total_gb*1024:.1f} MB"
            elif total_gb < 1024:
                traffic_text = f"{total_gb:.1f} GB"
            else:
                traffic_text = f"{total_gb/1024:.1f} TB"
        else:
            traffic_text = "0 GB"
        
        text = (
            f"{EMOJI['key']} *Ваш активный ключ*\n\n"
            f"{EMOJI['time']} *Осталось:* **{remaining}**\n"
            f"{EMOJI['traffic']} *Использовано:* **{traffic_text}**\n"
            f"{EMOJI['time']} *Действует до:* {end_date.replace(tzinfo=MOSCOW_TZ).strftime('%d.%m.%Y в %H:%M')} МСК\n\n"
            f"{EMOJI['info']} *Что дальше?*"
        )
        
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton(
            f"{EMOJI['rocket']} Получить ссылку с профилем", 
            callback_data=f"show_key_{u_uuid}"
        ))
        kb.add(InlineKeyboardButton(
            f"{EMOJI['refresh']} Обновить статистику", 
            callback_data="refresh_stats"
        ))
        kb.add(InlineKeyboardButton(f"{EMOJI['back']} Назад", callback_data="back_main"))
        
        bot.edit_message_text(text, uid, call.message.id, 
                             reply_markup=kb, parse_mode="Markdown")
    
    elif call.data == "refresh_stats":
        # Просто обновляем сообщение с ключами
        active_key = db.get_active_key(uid)
        
        if active_key:
            u_uuid = active_key[1]
            email = active_key[6]
            end_date = active_key[4]
            
            up_gb, down_gb, total_gb = get_client_traffic_stats(email)
            
            end_date_aware = MOSCOW_TZ.localize(end_date)
            now_aware = datetime.datetime.now(MOSCOW_TZ)
            delta = end_date_aware - now_aware
            
            if delta.total_seconds() <= 0:
                text = f"{EMOJI['key']} *Ключ истек* {EMOJI['cross']}"
            else:
                days = delta.days
                remaining = f"{days} дн." if days >= 1 else f"{int(delta.total_seconds() // 3600)} ч."
                
                traffic_text = ""
                if total_gb is not None:
                    if total_gb < 1:
                        traffic_text = f"{total_gb*1024:.1f} MB"
                    elif total_gb < 1024:
                        traffic_text = f"{total_gb:.1f} GB"
                    else:
                        traffic_text = f"{total_gb/1024:.1f} TB"
                else:
                    traffic_text = "0 GB"
                
                text = (
                    f"{EMOJI['key']} *Ваш активный ключ* {EMOJI['refresh']}\n\n"
                    f"{EMOJI['time']} *Осталось:* **{remaining}**\n"
                    f"{EMOJI['traffic']} *Использовано:* **{traffic_text}**\n"
                    f"{EMOJI['calendar']} *До:* {end_date.replace(tzinfo=MOSCOW_TZ).strftime('%d.%m.%Y %H:%M')} МСК\n\n"
                    f"{EMOJI['check']} *Статистика обновлена!*"
                )
            
            kb = InlineKeyboardMarkup()
            kb.add(InlineKeyboardButton(
                f"{EMOJI['rocket']} Получить ссылку с профилем", 
                callback_data=f"show_key_{u_uuid}"
            ))
            kb.add(InlineKeyboardButton(
                f"{EMOJI['refresh']} Обновить статистику", 
                callback_data="refresh_stats"
            ))
            kb.add(InlineKeyboardButton(f"{EMOJI['back']} Назад", callback_data="back_main"))
            
            bot.edit_message_text(text, uid, call.message.id, 
                                 reply_markup=kb, parse_mode="Markdown")
        else:
            bot.answer_callback_query(call.id, "Нет активного ключа", show_alert=True)
    
    elif call.data.startswith("show_key_"):
        u_uuid = call.data.replace("show_key_", "")
        db.cursor.execute("SELECT end_date, email FROM keys WHERE uuid=? AND user_id=?", (u_uuid, uid))
        row = db.cursor.fetchone()
        if not row:
            bot.answer_callback_query(call.id, "Ключ не найден")
            return

        end_date_str, email = row
        end_date = datetime.datetime.fromisoformat(end_date_str)
        
        # Получаем статистику трафика
        up_gb, down_gb, total_gb = get_client_traffic_stats(email)
        
        # Генерируем красивую ссылку
        beautiful_link = generate_beautiful_vless_link(uid)
        if not beautiful_link:
            beautiful_link = generate_vless_link(u_uuid)
        
        # Форматируем информацию для отображения
        expiry_date = end_date.replace(tzinfo=MOSCOW_TZ).strftime('%d.%m.%Y')
        
        # Показываем как будет выглядеть профиль
        if total_gb is not None:
            if total_gb < 1:
                traffic_display = f"{total_gb*1024:.1f} MB"
            elif total_gb < 1024:
                traffic_display = f"{total_gb:.1f} GB"
            else:
                traffic_display = f"{total_gb/1024:.1f} TB"
        else:
            traffic_display = "0 GB"
        
        current_time = datetime.datetime.now(MOSCOW_TZ).strftime('%d.%m.%Y %H:%M')
        
        profile_preview = (
            f"🔥 MAGAMIX VPN\n"
            f"{current_time} | 🇳🇱 Нидерланды\n\n"
            f"{traffic_display} / ∞ GB\n"
            f"Истекает: {expiry_date}\n\n"
            f"+{REFERRAL_REWARD_DAYS} дней за друга! @{bot.get_me().username}"
        )

        text = (
            f"{EMOJI['key']} *Ваш ключ с красивым профилем*\n\n"
            f"{EMOJI['info']} *В HAPP+ будет отображаться:*\n"
            f"────────────────\n"
            f"`{profile_preview}`\n"
            f"────────────────\n\n"
            f"{EMOJI['link']} *Ссылка подключения:*\n"
            f"`{beautiful_link}`\n\n"
            f"{EMOJI['info']} *Инструкция:*\n"
            f"1. Скопируйте ссылку выше\n"
            f"2. Откройте HAPP+ / Hiddify\n"
            f"3. Нажмите «+» → «Импорт из буфера»\n"
            f"4. Наслаждайтесь VPN! {EMOJI['rocket']}"
        )
        
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton(
            f"{EMOJI['copy']} Скопировать ключ", 
            callback_data=f"copy_{u_uuid}"
        ))
        kb.add(InlineKeyboardButton(f"{EMOJI['back']} Назад в Мои ключи", callback_data="my_keys"))
        kb.add(InlineKeyboardButton(f"{EMOJI['home']} В главное меню", callback_data="main"))
        
        bot.edit_message_text(text, uid, call.message.id, 
                             reply_markup=kb, parse_mode="Markdown")
    
    elif call.data.startswith("copy_"):
        if call.data.startswith("copy_ref_"):
            user_id = int(call.data.replace("copy_ref_", ""))
            ref_link = generate_referral_link(user_id)
            bot.answer_callback_query(call.id, 
                f"✅ Ссылка скопирована!\n\n{ref_link}", 
                show_alert=True
            )
        else:
            beautiful_link = generate_beautiful_vless_link(uid)
            if not beautiful_link:
                u_uuid = call.data.replace("copy_", "")
                beautiful_link = generate_vless_link(u_uuid)
            
            # Показываем полную ссылку в алерте
            bot.answer_callback_query(call.id, 
                f"✅ Ключ скопирован!\n\n{beautiful_link[:100]}...", 
                show_alert=True
            )
    
    elif call.data == "referral":
        ref_link = generate_referral_link(uid)
        ref_stats = db.get_referrals_stats(uid)
        
        kb = InlineKeyboardMarkup(row_width=1)
        kb.add(InlineKeyboardButton(
            f"{EMOJI['invite']} Скопировать ссылку", 
            callback_data=f"copy_ref_{uid}"
        ))
        kb.add(InlineKeyboardButton(
            f"{EMOJI['stats']} Моя статистика", 
            callback_data="ref_stats"
        ))
        kb.add(InlineKeyboardButton(f"{EMOJI['back']} Назад", callback_data="back_main"))
        
        text = (
            f"{EMOJI['friends']} *Пригласите друга — получите бонус!* {EMOJI['gift']}\n\n"
            f"{EMOJI['trophy']} *Как это работает:*\n"
            f"1. Отправьте другу вашу ссылку\n"
            f"2. Друг должен нажать на ссылку\n"
            f"3. Вы получаете *+{REFERRAL_REWARD_DAYS} дней VPN*\n\n"
            f"{EMOJI['info']} *Условия:*\n"
            f"• Есть ключ → продлится на {REFERRAL_REWARD_DAYS} дней\n"
            f"• Нет ключа → создастся новый на {REFERRAL_REWARD_DAYS} дней\n"
            f"• Бонус за каждого нового друга\n\n"
            f"{EMOJI['stats']} *Статистика:*\n"
            f"• Приглашено: *{ref_stats['total']}*\n"
            f"• Бонусов: *{ref_stats['rewarded']}*\n"
            f"• Дней бонусов: *{ref_stats['rewarded'] * REFERRAL_REWARD_DAYS}*\n\n"
            f"{EMOJI['link']} *Ваша ссылка:*\n"
            f"`{ref_link}`\n\n"
            f"{EMOJI['party']} Приглашайте друзей!"
        )
        
        bot.edit_message_text(text, uid, call.message.id, 
                             reply_markup=kb, parse_mode="Markdown")
    
    elif call.data == "ref_stats":
        ref_stats = db.get_referrals_stats(uid)
        
        text = (
            f"{EMOJI['stats']} *Ваша реферальная статистика*\n\n"
            f"{EMOJI['friends']} *Всего приглашено:* {ref_stats['total']}\n"
            f"{EMOJI['check']} *Получено бонусов:* {ref_stats['rewarded']}\n"
            f"{EMOJI['gift']} *Дней бонусов:* {ref_stats['rewarded'] * REFERRAL_REWARD_DAYS}\n\n"
            f"{EMOJI['trophy']} *Приглашайте больше друзей!*\n"
            f"Каждый друг = +{REFERRAL_REWARD_DAYS} дней VPN\n\n"
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
            f"{EMOJI['rocket']} *Лучший VPN для вашей безопасности!*\n\n"
            f"{EMOJI['speed']} *Преимущества:*\n"
            f"• Максимальная скорость\n"
            f"• Полная анонимность\n"
            f"• Защита от слежки\n"
            f"• Доступ к сайтам\n"
            f"• Безлимитный трафик\n"
            f"• Поддержка 24/7\n\n"
            f"{EMOJI['gift']} *Реферальная программа:*\n"
            f"• Пригласи друга → +{REFERRAL_REWARD_DAYS} дней\n"
            f"• Нет ключа? Создастся новый\n"
            f"• Есть ключ? Продлится\n\n"
            f"{EMOJI['key']} *Как начать:*\n"
            f"1. Купите подписку\n"
            f"2. Получите ключ\n"
            f"3. Настройте приложение\n"
            f"4. Наслаждайтесь!\n\n"
            f"{EMOJI['support']} *Поддержка:* @nejnayatp3"
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
            db.add_key(target_id, u_uuid, SID, days, email)
            link = generate_beautiful_vless_link(target_id)
            if not link:
                link = generate_vless_link(u_uuid)
            
            success_text = (
                f"{EMOJI['check']} *Оплата подтверждена!*\n\n"
                f"{EMOJI['key']} *Ваш ключ на {days} дней:*\n"
                f"`{link}`\n\n"
                f"{EMOJI['info']} *Инструкция:*\n"
                f"1. Скопируйте ссылку\n"
                f"2. Откройте HAPP+ / Hiddify\n"
                f"3. Нажмите «+» → «Импорт из буфера»\n"
                f"4. Наслаждайтесь VPN! {EMOJI['rocket']}"
            )
            
            bot.send_message(target_id, success_text, parse_mode="Markdown")
            
            admin_text = f"{EMOJI['check']} Ключ выдан пользователю {target_id}"
            bot.edit_message_text(admin_text, ADMIN_ID, call.message.id)
        else:
            bot.send_message(ADMIN_ID, f"{EMOJI['cross']} Ошибка API 3X-UI")

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

def auto_delete_loop():
    while True:
        try:
            expired = db.get_all_expired_keys()
            for user_id, u_uuid, email in expired:
                deleted = delete_user_from_xray(email)
                if deleted:
                    db.delete_key_by_uuid(u_uuid)
                    try:
                        bot.send_message(user_id, 
                            f"{EMOJI['cross']} *Ключ истек*\n\n"
                            f"{EMOJI['info']} Ключ удален.\n"
                            f"{EMOJI['buy']} Купите новый ключ\n"
                            f"{EMOJI['friends']} Или пригласите друга!",
                            parse_mode="Markdown"
                        )
                    except:
                        pass
        except Exception as e:
            print(f"[CLEANUP ERROR] {e}")
        time.sleep(1800)

threading.Thread(target=auto_delete_loop, daemon=True).start()

if __name__ == "__main__":
    # Тестовая ссылка
    test_uuid = str(uuid.uuid4())
    test_link = f"vless://{test_uuid}@{SERVER_IP}:{SERVER_PORT}?type=tcp&encryption=none&security=reality&sni={SNI}&fp={FP}&pbk={PBK}&sid={SID}&spx=%2F&flow=xtls-rprx-vision#Test"
    print(f"{EMOJI['rocket']} Тестовая ссылка: {test_link[:100]}...")
    
    print(f"{EMOJI['rocket']} Бот запущен!")
    print(f"{EMOJI['fire']} MAGAMIX VPN готов к работе!")
    bot.infinity_polling()
