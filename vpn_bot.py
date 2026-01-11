# bot.py
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import datetime
import uuid
import requests
import json
import time
import threading
import random
import pytz  # ← добавлен для московского времени
import db
from config import *

requests.packages.urllib3.disable_warnings()
bot = telebot.TeleBot(BOT_TOKEN)
session = requests.Session()

# Московский часовой пояс
MOSCOW_TZ = pytz.timezone('Europe/Moscow')

# --- Взаимодействие с 3X-UI ---
def xui_login():
    try:
        login_url = f"{PANEL_URL}/{PANEL_PATH}/login"
        r = session.post(login_url, data={"username": PANEL_USER, "password": PANEL_PASS}, verify=False, timeout=10)
        print(f"[LOGIN] Status: {r.status_code} | Response: {r.text[:200]}...")
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
        print(f"[ADD CLIENT] Status: {r.status_code} | Response: {r.text[:300]}...")
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
        print(f"[DEL CLIENT] Status: {r.status_code} | Response: {r.text[:200]}...")
        return r.json().get("success", False)
    except Exception as e:
        print(f"[DEL CLIENT ERROR] {e}")
        return False

# --- Вспомогательные функции ---
def generate_vless_link(u_uuid):
    return (f"vless://{u_uuid}@{SERVER_IP}:{SERVER_PORT}?type=tcp&encryption=none&security=reality"
            f"&sni={SNI}&fp={FP}&pbk={PBK}&sid={SID}&spx=%2F#MAGAMIX_VPN")

def get_remaining_time_str(end_date):
    now = datetime.datetime.now(MOSCOW_TZ)
    delta = end_date - now
    if delta.total_seconds() <= 0:
        return "истёк"
    if delta.days >= 1:
        return f"{delta.days} дн."
    hours = int(delta.total_seconds() // 3600) + (1 if delta.total_seconds() % 3600 > 0 else 0)
    return f"{hours} ч."

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
                "Привет! Добро пожаловать в MAGAMIX VPN 🔥\n\n"
                "🎁 Тебе автоматически выдан бесплатный пробный период на 3 дня!\n"
                "Ключ уже доступен в разделе «Мои ключи» — просто нажми кнопку ниже.\n\n"
                "Выбери действие:"
            )
        else:
            text = (
                "Привет! Добро пожаловать в MAGAMIX VPN 🔥\n\n"
                "Не удалось выдать пробный период (возможно технические работы).\n"
                "Напиши в поддержку @nejnayatp3\n\n"
                "Выбери действие:"
            )
    else:
        text = (
            "Привет! Рад тебя видеть снова в MAGAMIX VPN 🔥\n\n"
            "Выбери действие ниже 👇"
        )

    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(InlineKeyboardButton("💳 Купить VPN", callback_data="buy"),
           InlineKeyboardButton("🔑 Мои ключи", callback_data="my_keys"))
    kb.add(InlineKeyboardButton("🆘 Тех. поддержка", url="https://t.me/nejnayatp3"))
    
    bot.send_message(user_id, text, reply_markup=kb)

@bot.callback_query_handler(func=lambda call: True)
def query_handler(call):
    uid = call.from_user.id
    
    if call.data == "buy":
        kb = InlineKeyboardMarkup()
        for k, v in PRICES.items():
            kb.add(InlineKeyboardButton(f"{v['name']} — {v['price']}₽", callback_data=f"plan_{k}"))
        bot.edit_message_text("Выберите тариф:", uid, call.message.id, reply_markup=kb)
    
    elif call.data.startswith("plan_"):
        plan_key = call.data.replace("plan_", "")
        data = PRICES[plan_key]
        db.add_payment(uid, plan_key)
        
        text = (f"💳 Оплата: {data['name']}\n"
                f"Сумма: {data['price']}₽\n"
                f"Банк: {PAY_BANK}\n"
                f"Номер: `{PAY_PHONE}`\n\n"
                "Пришлите скриншот чека.")
        bot.edit_message_text(text, uid, call.message.id, parse_mode="Markdown")
    
    elif call.data == "my_keys":
        keys = db.get_keys(uid)
        if not keys:
            bot.edit_message_text("У вас нет активных ключей.", uid, call.message.id)
            return

        kb = InlineKeyboardMarkup(row_width=1)
        msg = "🔑 **Ваши ключи:**\n\n"
        now = datetime.datetime.now(MOSCOW_TZ)

        for row in keys:
            u_uuid = row[1]
            end_date = row[4]

            delta = end_date - now
            if delta.total_seconds() <= 0:
                continue

            days = delta.days
            hours = int(delta.total_seconds() // 3600) + (1 if delta.total_seconds() % 3600 else 0)
            time_str = f"{days} дн." if days >= 1 else f"{hours} ч."

            fake_num = random.randint(100000, 999999)
            button_text = f"🔐 {fake_num} ({time_str})"  # ← без • и "осталось"
            kb.add(InlineKeyboardButton(button_text, callback_data=f"show_key_{u_uuid}"))

            msg += f"🔐 {fake_num} ({time_str})\n"  # ← чистый список без • и "осталось"

        bot.edit_message_text(msg, uid, call.message.id, parse_mode="Markdown", reply_markup=kb)
    
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

        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton("📲 Подключиться", callback_data=f"connect_{u_uuid}"))

        text = (f"🔐 Ключ\n"
                f"Осталось: **{remaining}**\n"
                f"До: {end_date.astimezone(MOSCOW_TZ).strftime('%d.%m.%Y %H:%M')} МСК\n\n"
                f"`{link}`\n\n"
                "Скопируй ссылку выше и вставь в приложение Happ Plus / Hiddify ↓")
        bot.edit_message_text(text, uid, call.message.id, parse_mode="Markdown", reply_markup=kb)
    
    elif call.data.startswith("connect_"):
        u_uuid = call.data.replace("connect_", "")
        link = generate_vless_link(u_uuid)

        app_link = "https://t.me/hiddify_next_bot/app"  # или прямая ссылка на APK

        kb = InlineKeyboardMarkup()
        # Убрана url-кнопка с vless:// — Telegram её не поддерживает

        text = ("1. Скачай приложение **Happ Plus / Hiddify**\n"
                f"   👉 {app_link}\n\n"
                "2. В приложении нажми «+» → «Импорт из буфера обмена» или «Вставить ссылку»\n"
                "3. Скопируй ключ из сообщения выше и вставь!\n\n"
                "Готово! Подключись и наслаждайся скоростью 🚀")
        bot.send_message(uid, text, reply_markup=kb, parse_mode="Markdown")
        bot.answer_callback_query(call.id, "Ключ скопирован! Вставь в приложение")

    elif call.data.startswith("adm_ok_"):
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
            bot.send_message(target_id, f"✅ Оплата подтверждена!\nКлюч на {days} дней:\n\n`{link}`\n\nСкопируй и вставь в Happ Plus!", parse_mode="Markdown")
            bot.edit_message_text(f"Выдано пользователю {target_id}", ADMIN_ID, call.message.id)
        else:
            bot.send_message(ADMIN_ID, "❌ Ошибка при связи с API 3X-UI\nПроверь консоль бота!")

# --- Приём чеков ---
@bot.message_handler(content_types=['photo'])
def handle_receipt(message):
    uid = message.from_user.id
    bot.send_message(uid, "Чек отправлен на проверку. Ожидайте.")
    bot.forward_message(ADMIN_ID, message.chat.id, message.id)
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("✅ Подтвердить", callback_data=f"adm_ok_{uid}"))
    bot.send_message(ADMIN_ID, f"Новый чек от ID {uid} (@{message.from_user.username})", reply_markup=kb)

# --- Очистка просроченных ---
def auto_delete_loop():
    while True:
        try:
            expired = db.get_all_expired_keys()
            for user_id, u_uuid in expired:
                deleted = (delete_user_from_xray(f"trial_{user_id}") or 
                           delete_user_from_xray(f"user_{user_id}"))
                if deleted:
                    db.delete_key_by_uuid(u_uuid)
                    try:
                        bot.send_message(user_id, "🔴 Ключ истёк и был автоматически удалён.")
                    except:
                        pass
        except Exception as e:
            print(f"[CLEANUP ERROR] {e}")
        time.sleep(1800)

threading.Thread(target=auto_delete_loop, daemon=True).start()

if __name__ == "__main__":
    print(f"[{datetime.datetime.now(MOSCOW_TZ)}] Бот запущен...")
    bot.infinity_polling()
