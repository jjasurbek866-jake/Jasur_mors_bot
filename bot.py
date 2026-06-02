import asyncio
from aiogram import Bot, Dispatcher, Router, F
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
import aiosqlite
from datetime import datetime
import os
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading

# ====================================================
# RENDER UCHUN SOXTA VEB-SERVER (24/7 Tirik saqlash uchun)
class SimpleHTTPRequestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is running!")

def run_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(('0.0.0.0', port), SimpleHTTPRequestHandler)
    server.serve_forever()

threading.Thread(target=run_server, daemon=True).start()
# ====================================================

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
            [KeyboardButton(text="🏁 Kunni yakunlash"), KeyboardButton(text="📊 hisobot")]
        ],
        resize_keyboard=True
    )

# DATABASE INITIALIZATION
async def init_db():
    async with aiosqlite.connect("mors.db") as db:
        # sales jadvaliga day_num (kun raqami) ustunini qo'shdik
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
        # joriy aktiv kunni saqlab turish uchun sozlamalar jadvali
        await db.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
        """)
        # Agar birinchi marta ishga tushayotgan bo'lsa, kunni 1-kun deb belgilaymiz
        await db.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('current_day', '1')")
        await db.commit()

# Joriy kun raqamini bazadan olish funksiyasi
async def get_current_day():
    async with aiosqlite.connect("mors.db") as db:
        cur = await db.execute("SELECT value FROM settings WHERE key = 'current_day'")
        row = await cur.fetchone()
        return int(row[0]) if row else 1

# KUNNI BOSHLASH / START
@router.message(F.text == "/start")
async def start(msg: Message):
    current_day = await get_current_day()
    await msg.answer(
        f"☀️ *{current_day}-kun* boshlandi!\n\n"
        f"Bugungi sotuvlarni kiritishingiz mumkin. Quyidagi mahsulotlardan birini tanlang:",
        reply_markup=menu(),
        parse_mode="Markdown"
    )

# MAHSULOT TANLANGANDA
@router.message(F.text.in_(PRICES.keys()))
async def item(msg: Message):
    user_state[msg.from_user.id] = msg.text
    await msg.answer(f"🔢 *{msg.text}* dan nechta sotdingiz? Raqam kiriting:")

# MIQDORNI SAQLASH
@router.message(F.text.isdigit())
async def save(msg: Message):
    uid = msg.from_user.id

    if uid not in user_state:
        return

    item = user_state[uid]
    qty = int(msg.text)
    price = PRICES[item]
    total = qty * price
    current_day = await get_current_day()

    async with aiosqlite.connect("mors.db") as db:
        await db.execute(
            "INSERT INTO sales(day_num, item, qty, price, time) VALUES(?,?,?,?,?)",
            (current_day, item, qty, price, str(datetime.now()))
        )
        await db.commit()

    await msg.answer(
        f"✅ *{current_day}-kun* hisobiga saqlandi!\n\n"
        f"🛒 Mahsulot: {item}\n"
        f"📦 Miqdor: {qty} ta\n"
        f"💵 Jami: {total} so‘m",
        parse_mode="Markdown"
    )

    del user_state[uid]

# KUNNI YAKUNLASH (Keyingi kunga o'tish)
@router.message(F.text == "🏁 Kunni yakunlash")
async def finish_day(msg: Message):
    current_day = await get_current_day()
    next_day = current_day + 1
    
    async with aiosqlite.connect("mors.db") as db:
        await db.execute("UPDATE settings SET value = ? WHERE key = 'current_day'", (str(next_day),))
        await db.commit()
        
    await msg.answer(
        f"🏁 *{current_day}-kun* yakunlandi!\n\n"
        f"🚀 *{next_day}-kun* ochildi. Biznesingizga baraka bersin!",
        parse_mode="Markdown"
    )

# KUNLAR KESIMIDA BATAFSIL HISOBOT
@router.message(F.text == "📊 hisobot")
async def report(msg: Message):
    async with aiosqlite.connect("mors.db") as db:
        # Har bir kun uchun alohida umumiy summani hisoblab chiqarish query'si
        cur = await db.execute("""
            SELECT day_num, SUM(qty * price) 
            FROM sales 
            GROUP BY day_num 
            ORDER BY day_num ASC
        """)
        rows = await cur.fetchall()

        # Umumiy jami tushum
        total_cur = await db.execute("SELECT SUM(qty * price) FROM sales")
        grand_total = (await total_cur.fetchone())[0] or 0

    current_day = await get_current_day()
    
    report_text = "📊 *KUNLIK SAVDO HISOBOTI*\n"
    report_text += "───────────────────\n"
    
    if not rows:
        report_text += "Hozircha hech qaysi kunda savdo qilinmadi.\n"
    else:
        for row in rows:
            day = row[0]
            day_sum = row[1] or 0
            report_text += f"📅 *{day}-kun:*  {day_sum:,} so‘m\n"
            
    report_text += "───────────────────\n"
    report_text += f" joriy holat: *{current_day}-kun* ketmoqda.\n"
    report_text += f"💰 *Umumiy tushum:* {grand_total:,} so‘m"

    await msg.answer(report_text, parse_mode="Markdown")

# MAIN
async def main():
    await init_db()
    dp.include_router(router)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())