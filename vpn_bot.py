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
    db.add_key(telegram_id, u, sid, days)
    link = f"vless://{u}@{SERVER_IP}:{SERVER_PORT}?type=tcp&encryption=none&security=reality&pbk={PBK}&fp={FP}&sni={SNI}&sid={sid}&spx=%2F#MAGAMIX-{telegram_id}"
    return link

# Автоудаление просроченных ключей каждые 10 минут
def cleanup_expired_keys():
    while True:
        db.delete_expired_keys()
        threading.Event().wait(600)

threading.Thread(target=cleanup_expired_keys, daemon=True).start()

# ==================== МЕНЮ =====================
def main_menu(user_id=None):
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("💳 Купить VPN", callback_data="buy"))
    kb.add(InlineKeyboardButton("🔑 Мои ключи", callback_data="my_keys"))
    kb.add(InlineKeyboardButton("🛠 Техподдержка", url="https://t.me/nejnayatp3"))
    keys = db.get_keys(user_id) if user_id else []
    if not keys:
        kb.add(InlineKeyboardButton("🎁 Получить 3 дня", callback_data="free3"))
    return kb

# ==================== СТАРТ =====================
@bot.message_handler(commands=['start'])
def start(message):
    ref = None
    if message.text.startswith("/start ref-"):
        try:
            ref = int(message.text.split("-")[1])
        except:
            ref = None

    # Добавляем пользователя
    db.add_user(message.from_user.id, message.from_user.username, referrer_id=ref)
    
    # Продление реферального ключа
    if ref:
        db.extend_key(ref, 10)
        bot.send_message(ref, f"🎉 Пользователь @{message.from_user.username} присоединился по вашей ссылке! Ваш ключ продлен на 10 дней.")

    # Главное меню
    bot.send_message(message.chat.id,
                     f"🔥 Привет, {message.from_user.username}! Добро пожаловать в MAGAMIX VPN! 🔥\n"
                     "Защищай свои данные и пользуйся интернетом без ограничений!",
                     reply_markup=main_menu(message.from_user.id))

# ==================== КНОПКИ =====================
@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    user_id = call.from_user.id

    # Меню покупки
    if call.data == "buy":
        kb = InlineKeyboardMarkup()
        for k, v in PRICES.items():
            kb.add(InlineKeyboardButton(f"{v['name']} — {v['price']}₽", callback_data=f"plan_{k}"))
        kb.add(InlineKeyboardButton("🔙 Назад", callback_data="back"))
        bot.edit_message_text("Выберите тариф:", chat_id=user_id, message_id=call.message.message_id, reply_markup=kb)

    elif call.data.startswith("plan_"):
        plan = call.data.replace("plan_", "")
        db.add_payment(user_id, plan)
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton("✅ Оплатил", callback_data=f"paid_{plan}"))
        kb.add(InlineKeyboardButton("🔙 Назад", callback_data="buy"))
        bot.edit_message_text(f"💳 Оплата\n\n📞 {PAY_PHONE}\n🏦 {PAY_BANK}\n💰 {PRICES[plan]['price']} ₽", chat_id=user_id, message_id=call.message.message_id, reply_markup=kb)

    elif call.data.startswith("paid_"):
        plan = call.data.replace("paid_", "")
        bot.send_message(user_id, "📸 Пришлите чек перевода (фото или документ)")
        bot.send_message(ADMIN_ID, f"💰 Новый платеж: @{call.from_user.username} — {PRICES[plan]['name']} — {PRICES[plan]['price']}₽")
        kb_admin = InlineKeyboardMarkup()
        kb_admin.add(InlineKeyboardButton("✅ Выдать", callback_data=f"admin_issue_{user_id}_{plan}"))
        kb_admin.add(InlineKeyboardButton("❌ Отклонить", callback_data=f"admin_decline_{user_id}_{plan}"))
        bot.send_message(ADMIN_ID, "Проверка платежа:", reply_markup=kb_admin)

    elif call.data == "back":
        bot.edit_message_text("Главное меню:", chat_id=user_id, message_id=call.message.message_id, reply_markup=main_menu(user_id))

    elif call.data == "my_keys":
        keys = db.get_keys(user_id)
        if not keys:
            bot.send_message(user_id, "У вас нет активных ключей.", reply_markup=main_menu(user_id))
        else:
            text = "🔑 Ваши ключи:\n\n"
            for k in keys:
                text += create_vless_link(user_id, days=(k[4]-k[3]).days) + "\n"
            bot.send_message(user_id, text)

    elif call.data == "free3":
        create_vless_link(user_id, days=3)
        bot.send_message(user_id, "🎁 Ваш бесплатный ключ на 3 дня создан!", reply_markup=main_menu(user_id))

    # Админ: выдача/отклонение
    elif call.data.startswith("admin_issue_"):
        parts = call.data.split("_")
        target_id = int(parts[2])
        plan = parts[3]
        create_vless_link(target_id, PRICES[plan]['days'])
        db.set_payment_status(target_id, plan, "issued")
        bot.send_message(target_id, f"✅ Ваш ключ {PRICES[plan]['name']} активирован!")
        bot.send_message(ADMIN_ID, f"Ключ выдан @{target_id}")

    elif call.data.startswith("admin_decline_"):
        parts = call.data.split("_")
        target_id = int(parts[2])
        plan = parts[3]
        db.set_payment_status(target_id, plan, "declined")
        bot.send_message(target_id, f"❌ Ваш платеж {PRICES[plan]['name']} отклонен")
        bot.send_message(ADMIN_ID, f"Платеж отклонен @{target_id}")

# ==================== ЧЕК =====================
@bot.message_handler(content_types=['photo', 'document'])
def handle_check(message):
    bot.send_message(ADMIN_ID, f"📸 Новый чек от @{message.from_user.username}")
    bot.forward_message(ADMIN_ID, message.chat.id, message.message_id)
    bot.send_message(message.from_user.id, "⏳ Чек отправлен на проверку")

# ==================== ЗАПУСК =====================
print("[INFO] Бот запущен и ждёт сообщений...")
bot.infinity_polling()
