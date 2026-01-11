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
    "settings": "⚙️"
}

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
            f"&sni={SNI}&fp={FP}&pbk={PBK}&sid={SID}&spx=%2F#MAGAMIX_VPN")

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

def get_main_menu():
    """Главное меню"""
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton(f"{EMOJI['buy']} Купить VPN", callback_data="buy"),
        InlineKeyboardButton(f"{EMOJI['key']} Мои ключи", callback_data="my_keys")
    )
    kb.add(InlineKeyboardButton(f"{EMOJI['support']} Тех. поддержка", url="https://t.me/nejnayatp3"))
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

# --- Обработка команд ---
@bot.message_handler(commands=['start'])
def start_handler(message):
    user_id = message.from_user.id
    db.add_user(user_id, message.from_user.username)
    
    user_keys = db.get_keys(user_id)
    
    if not user_keys:  # Первый раз — триал
        u_uuid = str(uuid.uuid4())
        email = f"trial_{user_id}_{int(time.time())}"
        
        if add_user_to_xray(u_uuid, email, 3):
            db.add_key(user_id, u_uuid, SID, 3)
            text = (
                f"{EMOJI['crown']} *Добро пожаловать в MAGAMIX VPN* {EMOJI['fire']}\n\n"
                f"{EMOJI['star']} *Вам выдан БЕСПЛАТНЫЙ пробный период на 3 дня!*\n"
                f"{EMOJI['key']} Ключ доступен в разделе «Мои ключи»\n\n"
                f"{EMOJI['rocket']} *Преимущества нашего VPN:*\n"
                f"• {EMOJI['speed']} Высокая скорость\n"
                f"• {EMOJI['shield']} Защита данных\n"
                f"• {EMOJI['global']} Доступ к любому контенту\n"
                f"• {EMOJI['settings']} Простая настройка\n\n"
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
        if not keys:
            text = f"{EMOJI['key']} *У вас нет активных ключей* {EMOJI['cross']}"
            kb = get_back_button("main")
            bot.edit_message_text(text, uid, call.message.id, 
                                 reply_markup=kb, parse_mode="Markdown")
            return

        # Создаем клавиатуру с ключами
        kb = InlineKeyboardMarkup(row_width=1)
        
        for idx, row in enumerate(keys, 1):
            u_uuid = row[1]
            end_date = row[4]
            
            end_date_aware = MOSCOW_TZ.localize(end_date)
            now_aware = datetime.datetime.now(MOSCOW_TZ)
            delta = end_date_aware - now_aware
            
            if delta.total_seconds() <= 0:
                continue
            
            days = delta.days
            remaining = f"{days} дн." if days >= 1 else f"{int(delta.total_seconds() // 3600)} ч."
            
            # Создаем красивый текст для кнопки
            button_text = f"{EMOJI['key']} Ключ #{idx} ({remaining})"
            kb.add(InlineKeyboardButton(button_text, callback_data=f"show_key_{u_uuid}"))
        
        kb.add(InlineKeyboardButton(f"{EMOJI['back']} Назад", callback_data="back_main"))
        kb.add(InlineKeyboardButton(f"{EMOJI['home']} В главное меню", callback_data="main"))
        
        text = (
            f"{EMOJI['key']} *Ваши активные ключи*\n\n"
            f"{EMOJI['info']} Выберите ключ для просмотра:"
        )
        
        bot.edit_message_text(text, uid, call.message.id, 
                             reply_markup=kb, parse_mode="Markdown")
    
    elif call.data.startswith("show_key_"):
        u_uuid = call.data.replace("show_key_", "")
        db.cursor.execute("SELECT end_date FROM keys WHERE uuid=? AND user_id=?", (u_uuid, uid))
        row = db.cursor.fetchone()
        if not row:
            bot.answer_callback_query(call.id, "Ключ не найден")
            return

        end_date_str = str(row[0])
        end_date = datetime.datetime.fromisoformat(end_date_str)
        remaining = get_remaining_time_str(end_date)
        link = generate_vless_link(u_uuid)
        
        # Форматируем дату окончания
        end_date_formatted = end_date.replace(tzinfo=MOSCOW_TZ).strftime('%d.%m.%Y в %H:%M') + ' МСК'

        text = (
            f"{EMOJI['key']} *Детали ключа*\n\n"
            f"{EMOJI['time']} *Осталось:* **{remaining}**\n"
            f"{EMOJI['calendar']} *Действует до:* {end_date_formatted}\n\n"
            f"{EMOJI['link']} *Ссылка подключения:*\n"
            f"`{link}`\n\n"
            f"{EMOJI['info']} *Инструкция по настройке:*\n"
            f"1. Скачайте приложение *Happ Plus* или *Hiddify*\n"
            f"2. Нажмите «+» → «Импорт из буфера обмена»\n"
            f"3. Скопируйте ссылку выше и вставьте в приложение\n"
            f"4. Активируйте подключение и наслаждайтесь! {EMOJI['rocket']}"
        )
        
        bot.edit_message_text(text, uid, call.message.id, 
                             reply_markup=get_instructions_menu(u_uuid), 
                             parse_mode="Markdown")
    
    elif call.data.startswith("copy_"):
        u_uuid = call.data.replace("copy_", "")
        link = generate_vless_link(u_uuid)
        bot.answer_callback_query(call.id, "✅ Ключ скопирован! Вставьте в приложение", show_alert=True)
    
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
            f"{EMOJI['key']} *Как начать пользоваться:*\n"
            f"1. Купите подписку в разделе «Купить VPN»\n"
            f"2. Получите ключ в «Мои ключи»\n"
            f"3. Настройте приложение за 2 минуты\n"
            f"4. Наслаждайтесь свободным интернетом!\n\n"
            f"{EMOJI['support']} *Техническая поддержка:* @nejnayatp3"
        )
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton(f"{EMOJI['buy']} Купить VPN", callback_data="buy"))
        kb.add(InlineKeyboardButton(f"{EMOJI['key']} Мои ключи", callback_data="my_keys"))
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
                                f"{EMOJI['buy']} Приобретите новый ключ в разделе «Купить VPN»",
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
    bot.infinity_polling()
