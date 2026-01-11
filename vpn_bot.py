import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import uuid, random, requests
from datetime import datetime
from config import *
from db import create_user, get_user_by_ref, add_key, extend_key, get_active_key

bot = telebot.TeleBot(BOT_TOKEN)
user_orders = {}

# ===== VLESS link =====
def generate_vless_link(uuid_val, short_id, tg_id):
    return f"vless://{uuid_val}@{SERVER_IP}:{SERVER_PORT}?type=tcp&encryption=none&security=reality&pbk={PBK}&fp={FP}&sni={SNI}&sid={short_id}&spx=%2F#MAGAMIX-{tg_id}"

# ===== Xray API =====
def create_xray_user(uuid_val, short_id, days):
    url = f"{XRAY_API_URL}/vless-user"
    data = {
        "uuid": uuid_val,
        "short_id": short_id,
        "expiry_days": days
    }
    headers = {"Authorization": f"Bearer {XRAY_API_TOKEN}"}
    try:
        r = requests.post(url, json=data, headers=headers, timeout=10)
        return r.ok
    except Exception as e:
        print(f"[ERROR] Xray API: {e}")
        return False

# ===== MAIN MENU =====
def main_menu():
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("💳 Купить VPN", callback_data="buy"))
    kb.add(InlineKeyboardButton("🔑 Мои ключи", callback_data="keys"))
    kb.add(InlineKeyboardButton("🛠 Техподдержка", url="https://t.me/nejnayatp3"))
    return kb

# ===== START =====
@bot.message_handler(commands=['start'])
def start(message):
    args = message.text.split()
    referred_by = args[1] if len(args) > 1 else None
    create_user(message.from_user.id, referred_by)
    bot.send_message(message.chat.id, f"🔥 Привет {message.from_user.first_name}! Добро пожаловать в MAGAMIX VPN 🔥\nЗащищай свои данные и пользуйся интернетом без ограничений!", reply_markup=main_menu())

# ===== CALLBACKS =====
@bot.callback_query_handler(func=lambda call: True)
def callbacks(call):
    tg_id = call.from_user.id

    if call.data == "keys":
        key = get_active_key(tg_id)
        if key:
            link = generate_vless_link(key[0], key[1], tg_id)
            bot.send_message(tg_id, f"🔑 Ваш ключ:\n{link}\n💳 План: {key[2]}\n⏳ До: {key[3]}")
        else:
            kb = InlineKeyboardMarkup()
            kb.add(InlineKeyboardButton("💳 Купить VPN", callback_data="buy"))
            bot.send_message(tg_id, "У вас нет ключей. Купите новый:", reply_markup=kb)
        return

    elif call.data == "buy":
        kb = InlineKeyboardMarkup()
        for k,v in PRICES.items():
            kb.add(InlineKeyboardButton(f"{v['name']} — {v['price']}₽", callback_data=f"plan_{k}"))
        kb.add(InlineKeyboardButton("⬅ Назад", callback_data="back"))
        bot.edit_message_text("📦 Выберите тариф:", call.message.chat.id, call.message.message_id, reply_markup=kb)

    elif call.data.startswith("plan_"):
        plan = call.data.split("_")[1]
        user_orders[tg_id] = plan
        price = PRICES[plan]["price"]

        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton("✅ Я оплатил", callback_data="paid"))
        kb.add(InlineKeyboardButton("⬅ Назад", callback_data="buy"))

        bot.edit_message_text(
            f"💳 Оплата\n\n📞 {PAY_PHONE}\n🏦 {PAY_BANK}\n💰 {price} ₽\n\nПосле оплаты нажмите «Я оплатил»",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=kb
        )

    elif call.data == "paid":
        bot.send_message(tg_id, "📸 Отправьте чек перевода (фото или документ)")

    elif call.data == "back":
        bot.edit_message_text("Главное меню:", tg_id, call.message.message_id, reply_markup=main_menu())

# ===== CHECK HANDLER =====
@bot.message_handler(content_types=['photo','document'])
def check_handler(message):
    uid = message.from_user.id
    if uid not in user_orders:
        bot.reply_to(message, "❌ У вас нет активного заказа")
        return

    plan = user_orders[uid]
    price = PRICES[plan]["price"]

    kb = InlineKeyboardMarkup()
    kb.add(
        InlineKeyboardButton("✅ Выдать", callback_data=f"give_{uid}"),
        InlineKeyboardButton("❌ Отклонить", callback_data=f"deny_{uid}")
    )

    caption = (
        f"🧾 Оплата VPN\n\n"
        f"👤 ID: {uid}\n"
        f"📦 {PRICES[plan]['name']}\n"
        f"💰 {price} ₽"
    )

    bot.forward_message(ADMIN_ID, message.chat.id, message.message_id)
    bot.send_message(ADMIN_ID, caption, reply_markup=kb)
    bot.reply_to(message, "⏳ Чек отправлен на проверку")

# ===== ADMIN =====
@bot.callback_query_handler(func=lambda call: call.data.startswith(("give_","deny_")))
def admin(call):
    if call.from_user.id != ADMIN_ID:
        return

    action, uid = call.data.split("_")
    uid = int(uid)

    if action == "give":
        plan = user_orders.get(uid)
        uuid_val = str(uuid.uuid4())
        short_id = random.choice(["8b","87c72e","a55e4a67","082b0cc04005"])
        days = PRICES[plan]["days"]

        # создаём пользователя на панели
        if create_xray_user(uuid_val, short_id, days):
            add_key(uid, uuid_val, short_id, plan, days)
            link = generate_vless_link(uuid_val, short_id, uid)
            bot.send_message(uid, f"✅ VPN активирован!\n\n{link}")
            bot.send_message(ADMIN_ID, f"✅ Выдано пользователю {uid}")
        else:
            bot.send_message(ADMIN_ID, f"❌ Ошибка при создании на панели для {uid}")

        user_orders.pop(uid, None)
    else:
        bot.send_message(uid, "❌ Оплата отклонена. Свяжитесь с поддержкой.")
        bot.send_message(ADMIN_ID, f"❌ Отклонено {uid}")
        user_orders.pop(uid, None)

    bot.answer_callback_query(call.id)

# ===== RUN =====
print("🔥 MAGAMIX VPN BOT RUNNING")
bot.infinity_polling()
