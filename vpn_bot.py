import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import uuid, random
from config import *
from db import *

bot = telebot.TeleBot(BOT_TOKEN)
orders = {}

SHORT_IDS = ["8b","87c72e","a55e4a67","082b0cc04005"]

def vless_link(uuid, sid, uid):
    return (
        f"vless://{uuid}@{SERVER_IP}:{SERVER_PORT}"
        f"?type=tcp&encryption=none&security=reality"
        f"&pbk={PBK}&fp={FP}&sni={SNI}&sid={sid}&spx=%2F"
        f"#MAGAMIX-{uid}"
    )


def main_menu():
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("💳 Купить VPN", callback_data="buy"))
    kb.add(InlineKeyboardButton("🔑 Мои ключи", callback_data="keys"))
    kb.add(InlineKeyboardButton("👥 Реферальная ссылка", callback_data="ref"))
    kb.add(InlineKeyboardButton("🛠 Техподдержка", url="https://t.me/nejnayatp3"))
    return kb


@bot.message_handler(commands=["start"])
def start(msg):
    args = msg.text.split()
    ref = args[1] if len(args) > 1 else None

    my_ref = create_user(msg.from_user.id, ref)

    if ref:
        referrer = get_user_by_ref(ref)
        if referrer:
            if not extend_key(referrer, REF_BONUS_DAYS):
                add_key(
                    referrer,
                    str(uuid.uuid4()),
                    random.choice(SHORT_IDS),
                    REF_BONUS_DAYS
                )
            bot.send_message(referrer, f"🎉 Вам начислено +{REF_BONUS_DAYS} дней за приглашение!")

    bot.send_message(
        msg.chat.id,
        "🔥 **MAGAMIX VPN** 🔥\n\n"
        "Безопасный и быстрый VPN.\n"
        "Оплата → проверка → ключ.\n\n"
        "Выберите действие:",
        reply_markup=main_menu(),
        parse_mode="Markdown"
    )


@bot.callback_query_handler(func=lambda c: True)
def cb(c):
    uid = c.from_user.id

    if c.data == "keys":
        key = get_key(uid)
        if key:
            link = vless_link(key[0], key[1], uid)
            bot.send_message(uid, f"🔑 Ваш ключ:\n\n{link}\n\n⏳ До: {key[2]}")
        else:
            bot.send_message(uid, "❌ У вас нет ключей", reply_markup=main_menu())

    elif c.data == "ref":
        bot.send_message(
            uid,
            f"👥 Ваша реферальная ссылка:\n"
            f"https://t.me/{bot.get_me().username}?start=R{uid}\n\n"
            f"За каждого +{REF_BONUS_DAYS} дней"
        )

    elif c.data == "buy":
        kb = InlineKeyboardMarkup()
        for k,v in PRICES.items():
            kb.add(InlineKeyboardButton(f"{v['name']} — {v['price']}₽", callback_data=f"plan_{k}"))
        bot.edit_message_text("📦 Выберите тариф:", uid, c.message.message_id, reply_markup=kb)

    elif c.data.startswith("plan_"):
        plan = c.data.split("_")[1]
        orders[uid] = plan
        p = PRICES[plan]
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton("✅ Я оплатил", callback_data="paid"))
        bot.edit_message_text(
            f"💳 Оплата\n\n📞 {PAY_PHONE}\n🏦 {PAY_BANK}\n💰 {p['price']} ₽",
            uid, c.message.message_id, reply_markup=kb
        )

    elif c.data == "paid":
        bot.send_message(uid, "📸 Отправьте чек")


@bot.message_handler(content_types=["photo","document"])
def check(msg):
    uid = msg.from_user.id
    if uid not in orders:
        return

    plan = orders[uid]
    kb = InlineKeyboardMarkup()
    kb.add(
        InlineKeyboardButton("✅ Выдать", callback_data=f"give_{uid}"),
        InlineKeyboardButton("❌ Отклонить", callback_data=f"deny_{uid}")
    )

    bot.forward_message(ADMIN_ID, msg.chat.id, msg.message_id)
    bot.send_message(
        ADMIN_ID,
        f"🧾 Оплата\nID: {uid}\nТариф: {PRICES[plan]['name']}",
        reply_markup=kb
    )


@bot.callback_query_handler(func=lambda c: c.data.startswith(("give_","deny_")))
def admin(c):
    if c.from_user.id != ADMIN_ID:
        return

    action, uid = c.data.split("_")
    uid = int(uid)

    if action == "give":
        days = PRICES[orders[uid]]["days"]
        uuid_val = str(uuid.uuid4())
        sid = random.choice(SHORT_IDS)

        add_key(uid, uuid_val, sid, days)
        link = vless_link(uuid_val, sid, uid)
        bot.send_message(uid, f"✅ VPN активирован:\n\n{link}")

    else:
        bot.send_message(uid, "❌ Оплата отклонена")

    orders.pop(uid, None)
    bot.answer_callback_query(c.id)


print("🔥 BOT RUNNING")
bot.infinity_polling()
