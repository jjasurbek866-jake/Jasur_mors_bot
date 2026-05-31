import asyncio
from aiogram import Bot, Dispatcher, Router, F
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
import aiosqlite
from datetime import datetime

TOKEN = "8964012400:AAE4QLsxhG9gbKjmCz-GOpMh17gMNH77P2E"

bot = Bot(token=TOKEN)
dp = Dispatcher()
router = Router()

PRICES = {
    "☕ katta": 3000,
    "🥤 kichik": 2000,
    "🧴 1L": 5000,
    "🧴 1.5L": 8000,
    "🛢 5L": 25000
}

user_state = {}

# MENU
def menu():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="☕ katta"), KeyboardButton(text="🥤 kichik")],
            [KeyboardButton(text="🧴 1L"), KeyboardButton(text="🧴 1.5L")],
            [KeyboardButton(text="🛢 5L")],
            [KeyboardButton(text="📊 hisobot")]
        ],
        resize_keyboard=True
    )

# DB INIT (DROP YO‘Q!)
async def init_db():
    async with aiosqlite.connect("mors.db") as db:
        await db.execute("""
        CREATE TABLE IF NOT EXISTS sales (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            item TEXT,
            qty INTEGER,
            price INTEGER,
            time TEXT
        )
        """)
        await db.commit()

# 🔥 START (HAMMA NARSA RESET BO‘LADI)
@router.message(F.text == "/start")
async def start(msg: Message):
    user_state.clear()  # RAM tozalash

    async with aiosqlite.connect("mors.db") as db:
        await db.execute("DELETE FROM sales")  # 🔥 HAMMA DATA RESET
        await db.commit()

    await msg.answer("🚀 Bot yangidan ishga tushdi (0 dan)", reply_markup=menu())

# ITEM TANLASH
@router.message(F.text.in_(PRICES.keys()))
async def item(msg: Message):
    user_state[msg.from_user.id] = msg.text
    await msg.answer("🔢 Nechta sotding? raqam kiriting")

# QTY SAQLASH
@router.message(F.text.isdigit())
async def save(msg: Message):
    uid = msg.from_user.id

    if uid not in user_state:
        return

    item = user_state[uid]
    qty = int(msg.text)
    price = PRICES[item]
    total = qty * price

    async with aiosqlite.connect("mors.db") as db:
        await db.execute(
            "INSERT INTO sales(item, qty, price, time) VALUES(?,?,?,?)",
            (item, qty, price, str(datetime.now()))
        )
        await db.commit()

    await msg.answer(
        "✅ Saqlandi!\n\n"
        f"🛒 Mahsulot: {item}\n"
        f"📦 Miqdor: {qty}\n"
        f"💵 Jami: {total} so‘m"
    )

    del user_state[uid]

# HISOBOT
@router.message(F.text == "📊 hisobot")
async def report(msg: Message):
    async with aiosqlite.connect("mors.db") as db:
        cur = await db.execute("SELECT SUM(qty * price) FROM sales")
        total = (await cur.fetchone())[0] or 0

        cur = await db.execute("SELECT COUNT(*) FROM sales")
        count = (await cur.fetchone())[0]

    await msg.answer(
        f"📊 HISOBOT\n\n"
        f"🧾 Sotuvlar soni: {count}\n"
        f"💰 Umumiy tushum: {total} so‘m"
    )

# MAIN
async def main():
    await init_db()
    dp.include_router(router)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())