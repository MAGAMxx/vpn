import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import datetime, uuid, requests, json, time, threading, random
import db
from config import *

# Отключаем проверку SSL для работы по IP
requests.packages.urllib3.disable_warnings()

bot = telebot.TeleBot(BOT_TOKEN)
session = requests.Session()

def xui_login():
    try:
        r = session.post(f"{PANEL_URL}/{PANEL_PATH}/login", 
                         data={"username": PANEL_USER, "password": PANEL_PASS}, 
                         verify=False, timeout=5)
        return r.status_code == 200
    except: return False

def add_xray_client(u_uuid, email, days):
    if not xui_login(): return False
    expiry = int((time.time() + (days * 86400)) * 1000)
    payload = {"id": INBOUND_ID, "settings": json.dumps({"clients": [{"id": u_uuid, "email": email, "expiryTime": expiry, "enable": True}]})}
    try:
        r = session.post(f"{PANEL_URL}/{PANEL_PATH}/panel/api/inbounds/addClient", json=payload, verify=False)
        return r.json().get("success", False)
    except: return False

def del_xray_client(email):
    if not xui_login(): return False
    try:
        r = session.post(f"{PANEL_URL}/{PANEL_PATH}/panel/api/inbounds/delClient/{INBOUND_ID}/{email}", verify=False)
        return r.json().get("success", False)
    except: return False

def gen_link(u_uuid):
    return f"vless://{u_uuid}@{SERVER_IP}:{SERVER_PORT}?type=tcp&encryption=none&security=reality&sni={SNI}&fp={FP}&pbk={PBK}&sid={SID}#MAGAMIX_VPN"

@bot.message_handler(commands=['start'])
def start_handler(message):
    uid = message.from_user.id
    db.add_user(uid, message.from_user.username)
    
    # Выдача триала новым
    if not db.get_keys_with_expiry(uid):
        u_uuid = str(uuid.uuid4())
        if add_xray_client(u_uuid, f"trial_{uid}", 3):
            db.add_key(uid, u_uuid, 3)
            bot.send_message(uid, "🎁 Тебе выдан пробный период 3 дня!\n\n✅ Ключ уже доступен в разделе **(Мои ключи)**!", parse_mode="Markdown")

    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(InlineKeyboardButton("💳 Купить VPN", callback_data="buy"),
           InlineKeyboardButton("🔑 Мои ключи", callback_data="my_keys"))
    bot.send_message(uid, "🔥 Добро пожаловать в MAGAMIX VPN!", reply_markup=kb)

@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    uid = call.from_user.id

    if call.data == "buy":
        kb = InlineKeyboardMarkup()
        for k, v in PRICES.items():
            kb.add(InlineKeyboardButton(f"{v['name']} — {v['price']}₽", callback_data=f"plan_{k}"))
        bot.edit_message_text("Выберите тариф:", uid, call.message.id, reply_markup=kb)

    elif call.data.startswith("plan_"):
        plan_key = call.data.replace("plan_", "")
        db.add_payment(uid, plan_key)
        text = f"💳 **Оплата {PRICES[plan_key]['price']}₽**\n\nБанк: {PAY_BANK}\nНомер: `{PAY_PHONE}`\n\nПришлите скриншот чека боту."
        bot.edit_message_text(text, uid, call.message.id, parse_mode="Markdown")

    elif call.data == "my_keys":
        keys = db.get_keys_with_expiry(uid)
        if not keys:
            bot.answer_callback_query(call.id, "У вас нет активных ключей.")
            return

        kb = InlineKeyboardMarkup()
        for u_uuid, end_date in keys:
            # Расчет дней
            dt = datetime.datetime.fromisoformat(str(end_date))
            days_left = (dt - datetime.datetime.now()).days
            if days_left < 0: days_left = 0
            
            # Кнопка с рандомным числом
            rand_id = random.randint(10000, 99999)
            kb.add(InlineKeyboardButton(f"🔐 {rand_id} ({days_left} дней)", callback_data=f"show_{u_uuid}"))
        
        bot.edit_message_text("🔑 Ваши ключи:", uid, call.message.id, reply_markup=kb)

    elif call.data.startswith("show_"):
        u_uuid = call.data.replace("show_", "")
        # Ищем дату в базе вручную для отображения
        db.cursor.execute("SELECT end_date FROM keys WHERE uuid=?", (u_uuid,))
        row = db.cursor.fetchone()
        if row:
            expiry_date = datetime.datetime.fromisoformat(str(row[0])).strftime("%d.%m.%Y")
            bot.send_message(uid, f"📍 **Ваш ключ:**\n\nДействует до: `{expiry_date}`\n\n`{gen_link(u_uuid)}`", parse_mode="Markdown")

    elif call.data.startswith("adm_ok_"):
        tid = int(call.data.split("_")[2])
        pk = db.get_last_pending_plan(tid)
        days = PRICES[pk]['days']
        u_uuid = str(uuid.uuid4())
        
        if add_xray_client(u_uuid, f"user_{tid}", days):
            db.add_key(tid, u_uuid, days)
            bot.send_message(tid, f"✅ Оплата подтверждена! Ключ на {days} дней добавлен в раздел **(Мои ключи)**.")
            bot.edit_message_text(f"✅ Выдано пользователю {tid}", ADMIN_ID, call.message.id)

@bot.message_handler(content_types=['photo'])
def photo_handler(message):
    bot.forward_message(ADMIN_ID, message.chat.id, message.id)
    kb = InlineKeyboardMarkup().add(InlineKeyboardButton("✅ Подтвердить", callback_data=f"adm_ok_{message.from_user.id}"))
    bot.send_message(ADMIN_ID, f"🧾 Чек от @{message.from_user.username} (ID: {message.from_user.id})", reply_markup=kb)
    bot.reply_to(message, "⏳ Чек отправлен на проверку администратору.")

def cleanup_loop():
    while True:
        expired = db.get_all_expired_keys()
        for tid, u_uuid in expired:
            # Пробуем удалить оба типа email
            if del_xray_client(f"user_{tid}") or del_xray_client(f"trial_{tid}"):
                db.delete_key_by_uuid(u_uuid)
                try: bot.send_message(tid, "🔴 Срок действия вашего VPN ключа истек.")
                except: pass
        time.sleep(3600)

threading.Thread(target=cleanup_loop, daemon=True).start()
bot.infinity_polling()
