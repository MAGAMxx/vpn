import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from config import *
import db
import threading
import requests
import uuid
import datetime

bot = telebot.TeleBot(BOT_TOKEN)

# ==================== КЛЮЧИ =====================
def create_vless_link(telegram_id, days=30):
    u = str(uuid.uuid4())
    sid = uuid.uuid4().hex[:8]
    # Реальный POST-запрос к Xray API
    payload = {
        "tag": "api",
        "uuid": u,
        "short_id": sid,
        "expiry": days
    }
    try:
        requests.post(f"{XRAY_API_URL}/clients", json=payload)
    except Exception as e:
        print("Xray API Error:", e)
    # Сохраняем в БД
    db.add_key(telegram_id, u, sid, days)
    link = f"vless://{u}@{SERVER_IP}:{SERVER_PORT}?type=tcp&encryption=none&security=reality&pbk={PBK}&fp={FP}&sni={SNI}&sid={sid}&spx=%2F#MAGAMIX-{telegram_id}"
    return link

def cleanup_expired_keys():
    while True:
        db.delete_expired_keys()
        threading.Event().wait(600)  # каждые 10 минут

threading.Thread(target=cleanup_expired_keys, daemon=True).start()

# ==================== МЕНЮ =====================
def main_menu(user_id=None):
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("💳 Купить VPN", callback_data="buy"))
    kb.add(InlineKeyboardButton("🔑 Мои ключи", callback_data="my_keys"))
    kb.add(InlineKeyboardButton("🛠 Техподдержка", url="https://t.me/nejnayatp3"))
    # Для новых пользователей: кнопка 3 дня бесплатно
    keys = db.get_keys(user_id) if user_id else []
    if not keys:
        kb.add(InlineKeyboardButton("🎁 Получить 3 дня", callback_data="free3"))
    return kb

# ==================== СТАРТ =====================
@bot.message_handler(commands=['start'])
def start(message):
    ref = None
    if message.text.startswith("/start ref-"):
        ref = int(message.text.split("-")[1])
    db.add_user(message.from_user.id, message.from_user.username, referrer_id=ref)
    bot.send_message(message.chat.id, f"🔥 Привет, {message.from_user.username}! Добро пожаловать в MAGAMIX VPN! 🔥\n\nЗащищай свои данные и получай полный доступ к интернету!", reply_markup=main_menu(message.from_user.id))
    if ref:
        # Продление ключа пригласившего
        db.extend_key(ref, 10)
        bot.send_message(ref, f"🎉 Пользователь @{message.from_user.username} присоединился по вашей ссылке! Ваш ключ продлен на 10 дней.")

# ==================== ОБРАБОТКА КНОПОК =====================
@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    user_id = call.from_user.id
    if call.data == "buy":
        kb = InlineKeyboardMarkup()
        for k, v in PRICES.items():
            kb.add(InlineKeyboardButton(f"{v['name']} — {v['price']}₽", callback_data=f"plan_{k}"))
        kb.add(InlineKeyboardButton("🔙 Назад", callback_data="back"))
        bot.edit_message_text("Выберите тариф:", chat_id=user_id, message_id=call.message.message_id, reply_markup=kb)

    elif call.data.startswith("plan_"):
        plan = call.data.replace("plan_", "")
        price_data = PRICES[plan]
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton("✅ Оплатил", callback_data=f"paid_{plan}"))
        kb.add(InlineKeyboardButton("🔙 Назад", callback_data="buy"))
        bot.edit_message_text(f"💳 Оплата\n\n📞 {PAY_PHONE}\n🏦 {PAY_BANK}\n💰 {price_data['price']} ₽", chat_id=user_id, message_id=call.message.message_id, reply_markup=kb)

    elif call.data.startswith("paid_"):
        plan = call.data.replace("paid_", "")
        bot.send_message(user_id, "📸 Пришлите чек перевода (фото или документ)")
        bot.send_message(ADMIN_ID, f"💰 Новый платеж: @{call.from_user.username} — {PRICES[plan]['name']} — {PRICES[plan]['price']}₽")

    elif call.data == "back":
        bot.edit_message_text("Главное меню:", chat_id=user_id, message_id=call.message.message_id, reply_markup=main_menu(user_id))

    elif call.data == "my_keys":
        keys = db.get_keys(user_id)
        if not keys:
            bot.send_message(user_id, "У вас нет активных ключей. Купите VPN или получите бесплатные дни.", reply_markup=main_menu(user_id))
        else:
            text = "🔑 Ваши ключи:\n\n"
            for k in keys:
                text += create_vless_link(user_id, days=(k[4]-k[3]).days) + "\n"
            bot.send_message(user_id, text)

    elif call.data == "free3":
        create_vless_link(user_id, days=3)
        bot.send_message(user_id, "🎁 Ваш бесплатный ключ на 3 дня создан!", reply_markup=main_menu(user_id))

# ==================== ОБРАБОТКА ЧЕКОВ =====================
@bot.message_handler(content_types=['photo', 'document'])
def handle_check(message):
    bot.send_message(ADMIN_ID, f"📸 Новый чек от @{message.from_user.username}")
    bot.forward_message(ADMIN_ID, message.chat.id, message.message_id)
    bot.send_message(message.from_user.id, "⏳ Чек отправлен на проверку")

# ==================== ЗАПУСК =====================
print("[INFO] Бот запущен и ждёт сообщений...")
bot.infinity_polling()
