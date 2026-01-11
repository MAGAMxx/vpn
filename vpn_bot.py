# vpn_bot.py
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import uuid, random, requests, threading, time
from datetime import datetime, timedelta
from db import add_key, get_active_keys, extend_key, cleanup_expired_keys, add_referral, check_referral
from config import BOT_TOKEN, ADMIN_ID, PAY_PHONE, PAY_BANK, PRICES, SERVER_IP, SERVER_PORT, PBK, FP, SNI, XRAY_API_URL, XRAY_API_TOKEN

bot = telebot.TeleBot(BOT_TOKEN)
user_orders = {}
SHORT_IDS = ["8b","87c72e","a55e4a67","082b0cc04005","93281c7c7dcc2a81","15518f9d8686e6","c2f8","37de7da930"]

HEADERS = {"Content-Type": "application/json"}
if XRAY_API_TOKEN:
    HEADERS["Authorization"] = f"Bearer {XRAY_API_TOKEN}"

# --- Главное меню ---
def main_menu():
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("💳 Купить VPN", callback_data="buy"))
    kb.add(InlineKeyboardButton("🛠 Техподдержка", url="https://t.me/nejnayatp3"))
    kb.add(InlineKeyboardButton("🔑 Мои ключи", callback_data="mykeys"))
    return kb

# --- Создание ключа и регистрация в Xray ---
def create_vless_link(telegram_id, plan_days):
    user_uuid = str(uuid.uuid4())
    sid = random.choice(SHORT_IDS)

    # POST к Xray API
    payload = {
        "add": [
            {
                "email": user_uuid,
                "level": 0,
                "flow": "",
                "alterId": 0,
                "security": "reality",
                "shortIds": [sid],
                "expiry": plan_days
            }
        ]
    }
    try:
        url = f"{XRAY_API_URL}/v1/clients"
        resp = requests.post(url, json=payload, headers=HEADERS, timeout=5)
        if resp.status_code == 200:
            print(f"[INFO] Клиент создан на Xray: {user_uuid}")
        else:
            print(f"[ERROR] Xray API: {resp.status_code} {resp.text}")
    except Exception as e:
        print(f"[ERROR] Не удалось создать клиента на Xray: {e}")

    add_key(telegram_id, user_uuid, sid, "manual", plan_days)
    return f"vless://{user_uuid}@{SERVER_IP}:{SERVER_PORT}?type=tcp&encryption=none&security=reality&pbk={PBK}&fp={FP}&sni={SNI}&sid={sid}&spx=%2F#MAGAMIX-{telegram_id}"

# --- Удаление пользователя с Xray ---
def delete_xray_user(user_uuid):
    try:
        url = f"{XRAY_API_URL}/v1/clients/{user_uuid}"
        resp = requests.delete(url, headers=HEADERS, timeout=5)
        if resp.status_code == 200:
            print(f"[INFO] Клиент удалён с Xray: {user_uuid}")
        else:
            print(f"[ERROR] Не удалось удалить клиента Xray: {resp.status_code} {resp.text}")
    except Exception as e:
        print(f"[ERROR] Исключение при удалении клиента Xray: {e}")

# --- Автоудаление ключей ---
def cleanup_expired_keys_full():
    import sqlite3
    conn = sqlite3.connect("vpn.db")
    cursor = conn.cursor()
    now = datetime.utcnow().isoformat()
    cursor.execute("SELECT id, uuid FROM keys WHERE end_date<?", (now,))
    rows = cursor.fetchall()
    for key_id, uuid_key in rows:
        delete_xray_user(uuid_key)
        cursor.execute("DELETE FROM keys WHERE id=?", (key_id,))
        print(f"[INFO] Удалён ключ {uuid_key}")
    conn.commit()
    conn.close()

# --- Бот ---
@bot.message_handler(commands=['start'])
def start_handler(message):
    bot.send_message(message.chat.id,
        "🔥 Добро пожаловать в MAGAMIX VPN! 🔥\n\nС нами вы получаете свободу интернета и защиту данных!\nВыберите тариф и начните пользоваться прямо сейчас 💻🛡",
        reply_markup=main_menu())

@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    if call.data == "buy":
        kb = InlineKeyboardMarkup()
        for k, v in PRICES.items():
            kb.add(InlineKeyboardButton(f"{v['name']} — {v['price']}₽", callback_data=f"plan_{k}"))
        kb.add(InlineKeyboardButton("🔙 Назад", callback_data="back"))
        bot.edit_message_text("Выберите тариф:", chat_id=call.message.chat.id,
                              message_id=call.message.message_id, reply_markup=kb)

    elif call.data.startswith("plan_"):
        plan = call.data.replace("plan_", "")
        user_orders[call.from_user.id] = plan
        data = PRICES[plan]
        text = f"💳 Оплата\n\n📞 {PAY_PHONE}\n🏦 {PAY_BANK}\n💰 Сумма: {data['price']} ₽"
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton("✅ Оплатил", callback_data="paid"))
        kb.add(InlineKeyboardButton("🔙 Назад", callback_data="buy"))
        bot.edit_message_text(text, chat_id=call.message.chat.id,
                              message_id=call.message.message_id, reply_markup=kb)

    elif call.data == "paid":
        bot.send_message(call.message.chat.id, "📸 Пришлите чек перевода (фото или документ)")

    elif call.data == "back":
        bot.edit_message_text("Главное меню:", chat_id=call.message.chat.id,
                              message_id=call.message.message_id, reply_markup=main_menu())

    elif call.data == "mykeys":
        keys = get_active_keys(call.from_user.id)
        if not keys:
            bot.send_message(call.message.chat.id, "У вас нет активных ключей. 🔑 Купите ключ.", reply_markup=main_menu())
            return
        for k in keys:
            link = f"vless://{k[2]}@{SERVER_IP}:{SERVER_PORT}?type=tcp&encryption=none&security=reality&pbk={PBK}&fp={FP}&sni={SNI}&sid={k[3]}&spx=%2F#MAGAMIX-{call.from_user.id}"
            bot.send_message(call.message.chat.id, f"Ваш ключ ({k[4]}):\n{link}")

# --- Чеки оплаты ---
@bot.message_handler(content_types=['photo', 'document'])
def handle_check(message):
    user_id = message.from_user.id
    if user_id not in user_orders:
        bot.reply_to(message, "❌ Нет активного заказа.")
        return

    plan = user_orders[user_id]
    data = PRICES[plan]
    caption = f"🧾 Оплата\n\n👤 @{message.from_user.username}\n📦 {data['name']}\n💰 {data['price']} ₽"
    bot.send_message(ADMIN_ID, caption)
    if message.photo:
        bot.forward_message(ADMIN_ID, message.chat.id, message.message_id)
    elif message.document:
        bot.forward_message(ADMIN_ID, message.chat.id, message.message_id)
    bot.reply_to(message, "⏳ Чек отправлен на проверку")
    print(f"[INFO] Пользователь @{message.from_user.username} прислал чек для {data['name']}")

# --- Рефералька ---
@bot.message_handler(commands=['ref'])
def ref_handler(message):
    ref_code = f"REF-{message.from_user.id}"
    bot.send_message(message.chat.id, f"Ваш реферальный код: {ref_code}\nПригласите друга, и ваш ключ продлится на 10 дней!")

@bot.message_handler(commands=['invite'])
def invite_handler(message):
    parts = message.text.split()
    if len(parts) != 2:
        bot.reply_to(message, "Используйте: /invite <ref_code>")
        return
    ref_code = parts[1]
    ref_user_id = check_referral(ref_code)
    if not ref_user_id:
        bot.reply_to(message, "Неверный реферальный код.")
        return
    extended = extend_key(ref_user_id, 10)
    if extended:
        add_referral(ref_user_id, message.from_user.id)
        bot.reply_to(message, f"✅ Ключ пользователя {ref_user_id} продлён на 10 дней за приглашение!")
    else:
        # Создаём новый ключ на 10 дней
        create_vless_link(ref_user_id, 10)
        bot.reply_to(message, "✅ Новый ключ создан на 10 дней за приглашение!")

# --- Автоочистка ключей ---
def auto_cleanup_loop():
    while True:
        cleanup_expired_keys_full()
        time.sleep(600)  # каждые 10 минут

threading.Thread(target=auto_cleanup_loop, daemon=True).start()

print("[INFO] Бот запущен...")
bot.infinity_polling()
