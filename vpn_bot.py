import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import datetime
import uuid
import requests
import json
import time
import threading
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
        r = session.post(f"{PANEL_URL}/{PANEL_PATH}/panel/api/inbounds/addClient", json=payload, verify=False)
        return r.json().get("success", False)
    except:
        return False

def delete_user_from_xray(email):
    """Удаление пользователя из Xray по email (используется для просроченных)"""
    if not xui_login(): return False
    try:
        r = session.post(f"{PANEL_URL}/{PANEL_PATH}/panel/api/inbounds/delClient/{INBOUND_ID}/{email}", verify=False)
        return r.json().get("success", False)
    except:
        return False

# --- Вспомогательные функции ---

def generate_vless_link(u_uuid):
    """Генерация ссылки формата VLESS Reality для Happ Plus"""
    return (f"vless://{u_uuid}@{SERVER_IP}:{SERVER_PORT}?type=tcp&encryption=none&security=reality"
            f"&sni={SNI}&fp={FP}&pbk={PBK}&sid={SID}&spx=%2F#MAGAMIX_VPN")

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
            db.add_key(user_id, u_uuid, "sid", 3)
            link = generate_vless_link(u_uuid)
            bot.send_message(user_id, f"🎁 Привет! Тебе выдан пробный период на 3 дня!\n\nКлюч для Happ Plus:\n`{link}`", parse_mode="Markdown")
    
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(InlineKeyboardButton("💳 Купить VPN", callback_data="buy"), 
           InlineKeyboardButton("🔑 Мои ключи", callback_data="my_keys"))
    kb.add(InlineKeyboardButton("🆘 Поддержка", url="t.me"))
    
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
        db.add_payment(uid, plan_key) # Запись в БД
        
        text = (f"💳 *Оплата тарифа: {data['name']}*\n\n"
                f"Сумма к оплате: *{data['price']}₽*\n"
                f"Банк: {PAY_BANK}\n"
                f"Номер телефона: `{PAY_PHONE}`\n\n"
                "⚠️ Пришлите ФОТО или СКРИНШОТ чека после перевода.")
        bot.edit_message_text(text, uid, call.message.id, parse_mode="Markdown")

    elif call.data == "my_keys":
        keys = db.get_keys(uid)
        if not keys:
            bot.answer_callback_query(call.id, "У вас пока нет активных ключей.")
        else:
            msg = "🔑 *Ваши активные ключи:*\n\n"
            for k in keys:
                # k в данном случае кортеж (id, uuid, sid, start, end)
                link = generate_vless_link(k[1])
                msg += f"📅 Действует до: {k[4][:10]}\n`{link}`\n\n"
            bot.send_message(uid, msg, parse_mode="Markdown")

    elif call.data.startswith("adm_ok_"):
        # Логика подтверждения администратором
        target_id = int(call.data.split("_")[2])
        u_uuid = str(uuid.uuid4())
        days = 30 # Здесь можно извлечь из последней записи payments в БД
        
        email = f"user_{target_id}"
        if add_user_to_xray(u_uuid, email, days):
            db.add_key(target_id, u_uuid, "sid", days)
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
    
    # Пересылка админу
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
                user_id, u_uuid = row[0], row[1]
                # Сначала пробуем триал, потом обычный email
                if delete_user_from_xray(f"trial_{user_id}") or delete_user_from_xray(f"user_{user_id}"):
                    db.delete_key_by_uuid(u_uuid)
                    try: bot.send_message(user_id, "🔴 Срок вашей подписки истек. VPN отключен.")
                    except: pass
        except Exception as e:
            print(f"Ошибка в цикле очистки: {e}")
        time.sleep(3600) # Проверка каждый час

threading.Thread(target=auto_delete_loop, daemon=True).start()

if __name__ == "__main__":
    print(f"[{datetime.datetime.now()}] Бот MAGAMIX запущен...")
    bot.infinity_polling()
