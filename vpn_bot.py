import uuid
import datetime
import sqlite3
import json
import subprocess
from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils import executor
from config import *

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot)

# база
conn = sqlite3.connect("users.db")
cursor = conn.cursor()
cursor.execute("""CREATE TABLE IF NOT EXISTS users(
    tg_id INTEGER,
    username TEXT,
    uuid TEXT,
    short_id TEXT,
    plan TEXT,
    expiry DATE
)""")
conn.commit()

# временные заказы
user_orders = {}

# /start
@dp.message_handler(commands=["start"])
async def start(msg: types.Message):
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("💳 Купить VPN", callback_data="buy"))
    await msg.answer("Добро пожаловать в MAGAMIX VPN", reply_markup=kb)

# выбрать тариф
@dp.callback_query_handler(lambda c: c.data == "buy")
async def choose_plan(call: types.CallbackQuery):
    kb = InlineKeyboardMarkup()
    for k, v in PRICES.items():
        kb.add(InlineKeyboardButton(f"{v['name']} — {v['price']}₽", callback_data=f"plan_{k}"))
    kb.add(InlineKeyboardButton("🔙 Назад", callback_data="back"))
    await call.message.edit_text("Выберите тариф:", reply_markup=kb)

# показать оплату
@dp.callback_query_handler(lambda c: c.data.startswith("plan_"))
async def payment_info(call: types.CallbackQuery):
    plan = call.data.replace("plan_", "")
    user_orders[call.from_user.id] = plan
    data = PRICES[plan]

    text = (
        f"💳 Оплата\n\n"
        f"📞 {PAY_PHONE}\n"
        f"🏦 {PAY_BANK}\n"
        f"💰 Сумма: {data['price']} ₽"
    )

    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("✅ Оплатил", callback_data="paid"))
    kb.add(InlineKeyboardButton("🔙 Назад", callback_data="buy"))

    await call.message.edit_text(text, reply_markup=kb)

# ждать чек
@dp.callback_query_handler(lambda c: c.data == "paid")
async def wait_check(call: types.CallbackQuery):
    await call.message.answer("📸 Пришлите чек перевода (фото или документ)")

# получение чека
@dp.message_handler(content_types=["photo", "document"])
async def get_check(msg: types.Message):
    if msg.from_user.id not in user_orders:
        return

    plan = user_orders[msg.from_user.id]
    data = PRICES[plan]

    kb = InlineKeyboardMarkup()
    kb.add(
        InlineKeyboardButton("✅ Выдать", callback_data=f"approve_{msg.from_user.id}"),
        InlineKeyboardButton("❌ Отклонить", callback_data=f"reject_{msg.from_user.id}")
    )

    caption = (
        f"🧾 Оплата\n\n"
        f"👤 @{msg.from_user.username}\n"
        f"📦 {data['name']}\n"
        f"💰 {data['price']} ₽\n"
        f"🕒 {datetime.datetime.now()}"
    )

    await bot.send_message(ADMIN_ID, caption, reply_markup=kb)
    await msg.forward(ADMIN_ID)
    await msg.answer("⏳ Чек отправлен на проверку")