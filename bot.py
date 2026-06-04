import asyncio
from aiogram import Bot, Dispatcher, Router, F
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
import aiosqlite
from datetime import datetime
import os
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading

# ====================================================
# RENDER VEB SERVERI (Bot o'chib qolmasligi uchun)
class SimpleHTTPRequestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Mors Bot is running!")

def run_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(('0.0.0.0', port), SimpleHTTPRequestHandler)
    server.serve_forever()

threading.Thread(target=run_server, daemon=True).start()
# ====================================================

# ⚠️ BOT TOKENINGIZNI SHU YERGA TO'G'RI QO'YING
TOKEN = "8964012400:AAGjzHhuoQvfac1IVkBWa_rkorVjH7WdJmo" # O'zingizning yangi tokeningiz tursin

bot = Bot(token=TOKEN)
dp = Dispatcher()
router = Router()

# Narxlar (Faqat tushum hisoblanadi, xarajatlarsiz)
PRICES = {
    "☕ katta": 3000,
    "🥤 kichik": 2000,
    "🧴 1L": 5000,
    "🧴 1.5L": 8000,
    "🛢 5L": 25000
}

user_state = {}

def menu():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="☕ katta"), KeyboardButton(text="🥤 kichik")],
            [KeyboardButton(text="🧴 1L"), KeyboardButton(text="🧴 1.5L")],
            [KeyboardButton(text="🛢 5L")],
            [KeyboardButton(text="🏁 Kunni yakunlash"), KeyboardButton(text="📊 hisobot")]
        ],
        resize_keyboard=True
    )

async def init_db():
    # 🛠 ESKI BAZADAN QOLGAN XATOLIKLARNI TOZALASH UCHUN MAJBURIY CHORA
    try:
        if os.path.exists("mors.db"):
            os.remove("mors.db") # Eski xato bazani kodning o'zi majburlab o'chirib tashlaydi!
    except:
        pass

    async with aiosqlite.connect("mors.db") as db:
        # Mutlaqo toza va yangi jadval noldan ochiladi
        await db.execute("""
        CREATE TABLE IF NOT EXISTS sales (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            day_num INTEGER,
            item TEXT,
            qty INTEGER,
            price INTEGER,
            time TEXT
        )
        """)
        await db.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
        """)
        await db.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('current_day', '1')")
        await db.commit()

async def get_current_day():
    async with aiosqlite.connect("mors.db") as db:
        cur = await db.execute("SELECT value FROM settings WHERE key = 'current_day'")
        row = await cur.fetchone()
        return int(row[0]) if row else 1

@router.message(F.text == "/start")
async def start(msg: Message):
    async with aiosqlite.connect("mors.db") as db:
        # 🔄 Har safar start bosilganda 1-kunga qaytaradi va bazani tozalaydi
        await db.execute("UPDATE settings SET value = '1' WHERE key = 'current_day'")
        await db.execute("DELETE FROM sales")
        await db.commit()
    await msg.answer("☀️ *1-kun* boshlandi! Mahsulotni tanlang:", reply_markup=menu(), parse_mode="Markdown")

@router.message(F.text.in_(PRICES.keys()))
async def item(msg: Message):
    user_state[msg.from_user.id] = msg.text
    await msg.answer(f"🔢 {msg.text} dan nechta sotildi? Faqat raqam kiriting:")

@router.message(lambda msg: msg.text.isdigit())
async def save(msg: Message):
    uid = msg.from_user.id
    if uid not in user_state:
        return

    selected_item = user_state[uid]
    qty = int(msg.text)
    price = PRICES[selected_item]
    total = qty * price
    
    current_day = await get_current_day()

    async with aiosqlite.connect("mors.db") as db:
        await db.execute(
            "INSERT INTO sales(day_num, item, qty, price, time) VALUES(?,?,?,?,?)",
            (current_day, selected_item, qty, price, str(datetime.now()))
        )
        await db.commit()

    await msg.answer(
        f"✅ Saqlandi!\n\n🛒 Mahsulot: {selected_item}\n📦 Miqdor: {qty} ta\n💵 Jami: {total:,} so‘m"
    )
    if uid in user_state:
        del user_state[uid]

@router.message(F.text == "🏁 Kunni yakunlash")
async def finish_day(msg: Message):
    current_day = await get_current_day()
    next_day = current_day + 1
    async with aiosqlite.connect("mors.db") as db:
        await db.execute("UPDATE settings SET value = ? WHERE key = 'current_day'", (str(next_day),))
        await db.commit()
    await msg.answer(f"🏁 *{current_day}-kun* yakunlandi!\n🚀 *{next_day}-kun* ochildi.", parse_mode="Markdown")

@router.message(F.text == "📊 hisobot")
async def report(msg: Message):
    async with aiosqlite.connect("mors.db") as db:
        cur = await db.execute("SELECT day_num, SUM(qty * price) FROM sales GROUP BY day_num ORDER BY day_num ASC")
        rows = await cur.fetchall()

    current_day = await get_current_day()
    report_text = "📊 *KUNLIK SAVDO HISOBOTI*\n───────────────────\n"
    grand_tushum = 0
    
    if not rows:
        report_text += "Hozircha savdo ma'lumotlari yo'q.\n"
    else:
        for row in rows:
            day, day_tushum = row[0] or 1, row[1] or 0
            grand_tushum += day_tushum
            report_text += f"📅 *{day}-kun:* {day_tushum:,} so‘m\n"
            
    report_text += f"───────────────────\nℹ️ Joriy holat: {current_day}-kun ketmoqda.\n💰 *Umumiy tushum:* {grand_tushum:,} so‘m"
    await msg.answer(report_text, parse_mode="Markdown")

async def main():
    await init_db()
    await bot.delete_webhook(drop_pending_updates=True)
    dp.include_router(router)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())