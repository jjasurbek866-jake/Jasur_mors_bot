import asyncio
from aiogram import Bot, Dispatcher, Router, F
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
import aiosqlite
from datetime import datetime
import os
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading

# ====================================================
# RENDER VEB SERVERI
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
TOKEN = "8953766480:AAEWjsI_WpB8gXusHLl2Nr6XBAhfcUhW2oI" # BotFather bergan o'sha yangi tokeningizni to'liq yozing

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

# (chiqim, litr)
FORMULA = {
    "☕ katta": (333.33, 0.334),  
    "🥤 kichik": (250.0, 0.25),    
    "🧴 1L": (1000.0, 1.0),       
    "🧴 1.5L": (1500.0, 1.5),     
    "🛢 5L": (5000.0, 5.0)        
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
    async with aiosqlite.connect("mors.db") as db:
        await db.execute("""
        CREATE TABLE IF NOT EXISTS sales (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            day_num INTEGER,
            item TEXT,
            qty INTEGER,
            price INTEGER,
            chiqim REAL,
            litr REAL,
            time TEXT
        )
        """)
        try:
            await db.execute("ALTER TABLE sales ADD COLUMN chiqim REAL DEFAULT 0")
        except: pass
        try:
            await db.execute("ALTER TABLE sales ADD COLUMN litr REAL DEFAULT 0")
        except: pass
            
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
        await db.execute("UPDATE settings SET value = '1' WHERE key = 'current_day'")
        await db.execute("DELETE FROM sales")
        await db.commit()
    await msg.answer("☀️ *1-kun* boshlandi! Mahsulotni tanlang:", reply_markup=menu(), parse_mode="Markdown")

@router.message(F.text.in_(PRICES.keys()))
async def item(msg: Message):
    user_state[msg.from_user.id] = msg.text
    await msg.answer(f"🔢 {msg.text} dan nechta sotildi? Faqat raqam yozing:")

@router.message(lambda msg: msg.text.isdigit())
async def save(msg: Message):
    uid = msg.from_user.id
    if uid not in user_state:
        return

    selected_item = user_state[uid]
    qty = int(msg.text)
    price = PRICES[selected_item]
    total = qty * price
    
    one_chiqim, one_litr = FORMULA[selected_item]
    total_chiqim = round(one_chiqim * qty, 2)
    total_litr = round(one_litr * qty, 2)
    
    current_day = await get_current_day()

    async with aiosqlite.connect("mors.db") as db:
        await db.execute(
            "INSERT INTO sales(day_num, item, qty, price, chiqim, litr, time) VALUES(?,?,?,?,?,?,?)",
            (current_day, selected_item, qty, price, total_chiqim, total_litr, str(datetime.now()))
        )
        await db.commit()

    await msg.answer(
        f"✅ Saqlandi!\n\n🛒 Mahsulot: {selected_item}\n📦 Miqdor: {qty} ta\n💵 Jami: {total:,} so‘m\n📉 Sarflandi: {total_litr} litr mors"
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
        cur = await db.execute("SELECT day_num, SUM(qty * price), SUM(chiqim), SUM(litr) FROM sales GROUP BY day_num ORDER BY day_num ASC")
        rows = await cur.fetchall()

    current_day = await get_current_day()
    report_text = "📊 *KUNLIK BIZNES HISOBOTI*\n───────────────────\n"
    grand_kirim, grand_chiqim, grand_litr = 0, 0, 0
    
    if not rows:
        report_text += "Hozircha savdo ma'lumotlari yo'q.\n"
    else:
        for row in rows:
            day, day_kirim, day_chiqim, day_litr = row[0] or 1, row[1] or 0, int(row[2] or 0), round(row[3] or 0, 2)
            grand_kirim += day_kirim
            grand_chiqim += day_chiqim
            grand_litr += day_litr
            report_text += f"📅 *{day}-kun:* \n   💰 Tushum: {day_kirim:,} so‘m\n   📉 Xarajat: {day_chiqim:,} so‘m\n   💵 Sof Foyda: {(day_kirim - day_chiqim):,} so‘m\n   🛢 Sarflangan: {day_litr} litr\n\n"
            
    report_text += f"───────────────────\nℹ️ Joriy holat: {current_day}-kun.\n📊 *UMUMIY YAKUN:* \n   💵 Tushum: {grand_kirim:,} so‘m\n   💸 Xarajat: {grand_chiqim:,} so‘m\n   💎 SOF FOYDA: {(grand_kirim - grand_chiqim):,} so‘m\n   🧪 SOTILGAN MORS: {round(grand_litr, 2)} LITR"
    await msg.answer(report_text, parse_mode="Markdown")

async def main():
    await init_db()
    await bot.delete_webhook(drop_pending_updates=True)
    dp.include_router(router)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())