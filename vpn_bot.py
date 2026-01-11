# bot.py
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import datetime
import uuid
import requests
import json
import time
import threading
import random  # Добавлен для рандомных ID
import db
from config import *

# Отключаем предупреждения об отсутствии SSL сертификата (так как у вас IP)
requests.packages.urllib3.disable_warnings()
bot = telebot.TeleBot(BOT_TOKEN)
session = requests.Session()

# --- Взаимодействие с 3X-UI через API ---
def xui_login():
    """Авторизация в панели для получения сессии"""
    try:
        login_url = f"{PANEL_URL}/{PANEL_PATH}/login"
        r = session.post(login_url, data={"username": PANEL_USER, "password": PANEL_PASS}, verify=False, timeout=10)
        return r.status_code == 200
    except Exception as e:
        print(f"Ошибка входа в панель: {e}")
        return False

def add_user_to_xray(user_uuid, email, days):
    """Реальное добавление пользователя в конфиг Xray на сервере"""
    if not xui_login(): return False
    
    # Время истечения в миллисекундах
    expiry_time = int((time.time() + (days * 86400)) * 1000)
    
    payload = {
        "id": INBOUND_ID,
        "settings": json.dumps({
            "clients": [{
                "id": user_uuid,
                "alterId": 0,
                "email": email,
                "limitIp": 2,  # Без лимита
                "totalGB": 0,
                "expiryTime": expiry_time,
                "enable": True,
                "tgId": "",
                "subId": ""
            }]
        })
    }
    try:
        r = session.post(f"{PANEL_URL}/{PANEL_PATH}/panel/api/inbounds/addClient", json=payload, verify=False)
        return r.json().get("success", False)
    except Exception as e:
        print(f"Ошибка добавления клиента: {e}")
        return False

def delete_user_from_xray(email):
    """Удаление пользователя из Xray по email (используется для просроченных)"""
    if not xui_login(): return False
    try:
        r = session.post(f"{PANEL_URL}/{PANEL_PATH}/panel/api/inbounds/{INBOUND_ID}/delClient/{email}", verify=False)
        return r.json().get("success", False)
    except Exception as e:
        print(f"Ошибка удаления клиента: {e}")
        return False

# --- Вспомогательные функции ---
def generate_vless_link(u_uuid):
    """Генерация ссылки формата VLESS Reality для Hiddify (Happ Plus)"""
    return (f"vless://{u_uuid}@{SERVER_IP}:{SERVER_PORT}?type=tcp&encryption=none&security=reality"
            f"&sni={SNI}&fp={FP}&pbk={PBK}&sid={SID}&spx=%2F#MAGAMIX_VPN")

def get_remaining_time_str(end_date):
    """Вспомогательная: красивое оставшееся время (для показа ключа)"""
    now = datetime.datetime.now()
    delta = end_date - now
    if delta.total_seconds() <= 0:
        return "истёк"
    if delta.days >= 1:
        return f"{delta.days} дн."
    hours = int(delta.total_seconds() // 3600) + (1 if delta.total_seconds() % 3600 > 0 else 0)
    return f"{hours} ч."

# --- Обработка команд бота ---
@bot.message_handler(commands=['start'])
def start_handler(message):
    user_id = message.from_user.id
    db.add_user(user_id, message.from_user.username)
    
    # Проверка на первый вход (бесплатный период 3 дня)
    user_keys = db.get_keys(user_id)
    if not user_keys:
        u_uuid = str(uuid.uuid4())
        email = f"trial_{user_id}"
        if add_user_to_xray(u_uuid, email, 3):
            db.add_key(user_id, u_uuid, SID, 3)
            link = generate_vless_link(u_uuid)
            bot.send_message(user_id, f"🎁 Привет! Тебе выдан пробный период на 3 дня!\n\nКлюч для Happ Plus:\n`{link}`", parse_mode="Markdown")
    
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(InlineKeyboardButton("💳 Купить VPN", callback_data="buy"),
           InlineKeyboardButton("🔑 Мои ключи", callback_data="my_keys"))
    kb.add(InlineKeyboardButton("🆘 Поддержка", url="t.me/nejnayatp3"))  # Замени на реальный
    
    bot.send_message(user_id, "Вы в главном меню MAGAMIX VPN. Выберите действие:", reply_markup=kb)

@bot.callback_query_handler(func=lambda call: True)
def query_handler(call):
    uid = call.from_user.id
    
    if call.data == "buy":
        kb = InlineKeyboardMarkup()
        for k, v in PRICES.items():
            kb.add(InlineKeyboardButton(f"{v['name']} — {v['price']}₽", callback_data=f"plan_{k}"))
        bot.edit_message_text("Выберите тарифный план:", uid, call.message.id, reply_markup=kb)
    
    elif call.data.startswith("plan_"):
        plan_key = call.data.replace("plan_", "")
        data = PRICES[plan_key]
        db.add_payment(uid, plan_key)  # Запись в БД
        
        text = (f"💳 *Оплата тарифа: {data['name']}*\n\n"
                f"Сумма к оплате: *{data['price']}₽*\n"
                f"Банк: {PAY_BANK}\n"
                f"Номер телефона: `{PAY_PHONE}`\n\n"
                "⚠️ Пришлите ФОТО или СКРИНШОТ чека после перевода.")
        bot.edit_message_text(text, uid, call.message.id, parse_mode="Markdown")
    
    elif call.data == "my_keys":
        keys = db.get_keys(uid)
        if not keys:
            bot.answer_callback_query(call.id, "У вас пока нет активных ключей 😔")
            bot.edit_message_text("У вас пока нет активных ключей.", uid, call.message.id)
            return

        kb = InlineKeyboardMarkup(row_width=1)
        msg = "🔑 **Ваши активные ключи:**\n\n"

        now = datetime.datetime.now()

        for key_row in keys:
            u_uuid = key_row[1]
            end_date = datetime.datetime.fromisoformat(key_row[4].isoformat())  # Убедимся в datetime

            delta = end_date - now
            if delta.total_seconds() <= 0:
                continue

            days_left = delta.days
            hours_left = int(delta.total_seconds() // 3600) + (1 if delta.total_seconds() % 3600 > 0 else 0)

            time_str = f"{days_left} дн." if days_left >= 1 else f"{hours_left} ч."

            fake_id = random.randint(10000, 99999)
            button_text = f"🔐 {fake_id}  ({time_str})"
            kb.add(InlineKeyboardButton(button_text, callback_data=f"show_{u_uuid}"))

            msg += f"• {fake_id} — осталось **{time_str}**\n"

        bot.edit_message_text(msg, uid, call.message.id, parse_mode="Markdown", reply_markup=kb)
    
    elif call.data.startswith("show_"):
        u_uuid = call.data.replace("show_", "")

        db.cursor.execute("SELECT end_date FROM keys WHERE uuid = ? AND user_id = ?", (u_uuid, uid))
        row = db.cursor.fetchone()

        if not row:
            bot.answer_callback_query(call.id, "Ключ не найден или уже истёк")
            return

        end_date = datetime.datetime.fromisoformat(str(row[0]))
        expiry_str = end_date.strftime("%d.%m.%Y %H:%M")
        remaining = get_remaining_time_str(end_date)

        link = generate_vless_link(u_uuid)

        text = (f"📍 **Ваш ключ**\n\n"
                f"Действует до: `{expiry_str}`\n"
                f"Осталось: **{remaining}**\n\n"
                f"`{link}`")

        bot.send_message(uid, text, parse_mode="Markdown")
    
    elif call.data.startswith("adm_ok_"):
        target_id = int(call.data.split("_")[2])
        plan_key = db.get_last_pending_plan(target_id)
        if not plan_key:
            bot.send_message(ADMIN_ID, "❌ Нет ожидающих платежей для этого пользователя.")
            return
        days = PRICES[plan_key]['days']
        u_uuid = str(uuid.uuid4())
        email = f"user_{target_id}"
        if add_user_to_xray(u_uuid, email, days):
            db.add_key(target_id, u_uuid, SID, days)
            link = generate_vless_link(u_uuid)
            bot.send_message(target_id, f"✅ Оплата подтверждена! Ваш ключ на {days} дней:\n\n`{link}`", parse_mode="Markdown")
            bot.edit_message_text(f"Выдано пользователю {target_id}", ADMIN_ID, call.message.id)
        else:
            bot.send_message(ADMIN_ID, "❌ Ошибка при связи с API 3X-UI")

# --- Прием чеков ---
@bot.message_handler(content_types=['photo'])
def handle_receipt(message):
    uid = message.from_user.id
    bot.send_message(uid, "⏳ Чек получен и отправлен на проверку. Ожидайте подтверждения.")
    
    bot.forward_message(ADMIN_ID, message.chat.id, message.id)
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("✅ Подтвердить и выдать ключ", callback_data=f"adm_ok_{uid}"))
    bot.send_message(ADMIN_ID, f"🔔 Новый чек от @{message.from_user.username} (ID: {uid})", reply_markup=kb)

# --- Фоновый процесс удаления по времени ---
def auto_delete_loop():
    while True:
        try:
            expired = db.get_all_expired_keys()
            for row in expired:
                user_id, u_uuid = row
                trial_email = f"trial_{user_id}"
                user_email = f"user_{user_id}"

                deleted = False
                if delete_user_from_xray(trial_email):
                    deleted = True
                if delete_user_from_xray(user_email):
                    deleted = True

                if deleted:
                    db.delete_key_by_uuid(u_uuid)
                    try:
                        bot.send_message(user_id, "🔴 Ваш ключ истёк и был автоматически удалён.")
                    except:
                        pass
        except Exception as e:
            print(f"Ошибка в цикле очистки: {e}")
        time.sleep(1800)  # Каждые 30 минут

threading.Thread(target=auto_delete_loop, daemon=True).start()

if __name__ == "__main__":
    print(f"[{datetime.datetime.now()}] Бот MAGAMIX запущен...")
    bot.infinity_polling()
