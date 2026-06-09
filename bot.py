import asyncio
import logging
from aiogram import Bot, Dispatcher, types, F
from aiogram.types import Message
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import ReplyKeyboardBuilder
import aiosqlite
import aiohttp
from aiohttp import web
from datetime import datetime

# 1. SOZLAMALAR
TOKEN = "8964012400:AAFVLbUReppLSsbJSi-403HSSsYZt0kTiC0"  # O'zingizning oxirgi to'g'ri tokeningizni yozing
RENDER_URL = "https://jasur-mors-bot.onrender.com"
DB_NAME = "mors_biznes.db"

bot = Bot(token=TOKEN)
dp = Dispatcher()
logging.basicConfig(level=logging.INFO)

# =====================================================================
# RENDER UCHUN AVTOMATIK UYG'OTUVCHI (WEB SERVER + PING)
# =====================================================================
async def handle_ping(request):
    return web.Response(text="Bot uyg'oq!")

async def self_ping_loop():
    await asyncio.sleep(30)
    async with aiohttp.ClientSession() as session:
        while True:
            try:
                async with session.get(RENDER_URL) as response:
                    if response.status == 200:
                        print("🤖 [Keep-Alive] Ping muvaffaqiyatli!")
            except Exception as e:
                print("⚠️ [Keep-Alive] Xatolik:", e)
            await asyncio.sleep(600)  # Har 10 daqiqada

async def start_web_server():
    app = web.Application()
    app.router.add_get('/', handle_ping)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', 10000)
    await site.start()

# =====================================================================
# FSM STATE VA STRUKTURA (OLDINGI HOLATIDEK)
# =====================================================================
class SavdoState(StatesGroup):
    miqdor_kiritish = State()

# Oddiy foydalanuvchi holatini vaqtinchalik saqlash (Sening kodingdagi uslub)
user_state = {}

async def init_db():
    async with aiosqlite.connect(DB_NAME) as db:
        # Sales jadvali sening asliyatdek
        await db.execute("""
            CREATE TABLE IF NOT EXISTS sales (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                day_num INTEGER,
                item TEXT,
                qty INTEGER,
                price INTEGER,
                chiqim INTEGER,
                litr REAL,
                time TEXT
            )
        """)
        # Settings jadvali kunni saqlash uchun
        await db.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)
        # Agar current_day yo'q bo'lsa, 1-kun deb kiritamiz
        await db.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('current_day', '1')")
        await db.commit()

async def get_current_day():
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT value FROM settings WHERE key = 'current_day'") as cursor:
            row = await cursor.fetchone()
            return int(row[0]) if row else 1

# =====================================================================
# KLAVIATURA
# =====================================================================
def get_main_keyboard():
    builder = ReplyKeyboardBuilder()
    builder.button(text="☕ katta")
    builder.button(text="🥫 kichik")
    builder.button(text="🍼 1L")
    builder.button(text="🥛 1.5L")
    builder.button(text="🛢 5L")
    builder.button(text="🏁 Kunni yakunlash")
    builder.button(text="📊 hisobot")
    builder.adjust(2, 2, 1, 2)
    return builder.as_markup(resize_keyboard=True)

# =====================================================================
# HANDLERLAR
# =====================================================================

@dp.message(Command("start"))
async def start_cmd(message: Message):
    current_day = await get_current_day()
    await message.answer(
        f"☀️ {current_day}-kun boshlandi!\nMahsulotni tanlang:",
        reply_markup=get_main_keyboard()
    )

@dp.message(F.text.in_(["☕ katta", "🥫 kichik", "🍼 1L", "🥛 1.5L", "🛢 5L"]))
async def process_mahsulot(message: Message, state: FSMContext):
    await state.update_data(tanlangan_mahsulot=message.text)
    await state.set_state(SavdoState.miqdor_kiritish)
    await message.answer(f"Nechta {message.text} sotildi? (Faqat son kiriting):")

@dp.message(SavdoState.miqdor_kiritish)
async def process_miqdor(message: Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("⚠️ Iltimos, faqat musbat son kiriting!")
        return

    qty = int(message.text)
    user_data = await state.get_data()
    selected_item = user_data['tanlangan_mahsulot']
    
    # Narxlar, xarajatlar va litr hisob-kitoblari (Sening aslingdek)
    narxlar = {"☕ katta": 8000, "🥫 kichik": 5000, "🍼 1L": 12000, "🥛 1.5L": 16000, "🛢 5L": 50000}
    xarajatlar = {"☕ katta": 2500, "🥫 kichik": 1500, "🍼 1L": 4000, "🥛 1.5L": 5500, "🛢 5L": 18000}
    litrlar = {"☕ katta": 0.4, "🥫 kichik": 0.25, "🍼 1L": 1.0, "🥛 1.5L": 1.5, "🛢 5L": 5.0}
    
    birlik_narx = narxlar.get(selected_item, 0)
    birlik_chiqim = xarajatlar.get(selected_item, 0)
    birlik_litr = litrlar.get(selected_item, 0.0)
    
    price = birlik_narx  # sening kodingdagi price ustuni uchun
    total = birlik_narx * qty  # jami tushum matn uchun
    total_chiqim = birlik_chiqim * qty
    total_litr = round(birlik_litr * qty, 2)
    
    current_day = await get_current_day()
    uid = message.from_user.id

    # AYNAN SENING ASLIY INSERT SCRIPTING
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            "INSERT INTO sales(day_num, item, qty, price, chiqim, litr, time) VALUES(?,?,?,?,?,?,?)",
            (current_day, selected_item, qty, price, total_chiqim, total_litr, str(datetime.now()))
        )
        await db.commit()

    # AYNAN SENING ASLIY JAVOB MATNING
    await message.answer(
        f"✅ Saqlandi!\n\n"
        f"🛒 Mahsulot: {selected_item}\n"
        f"📦 Miqdor: {qty} ta\n"
        f"💵 Jami tushum: {total:,} so‘m\n"
        f"📉 Ishlatilgan mors: {total_litr} litr",
        reply_markup=get_main_keyboard()
    )
    
    if uid in user_state:
        del user_state[uid]
        
    await state.clear()

# AYNAN SENING ASLIY KUNNI YAKUNLASH SCRIPTING
@dp.message(F.text == "🏁 Kunni yakunlash")
async def finish_day(msg: Message):
    current_day = await get_current_day()
    next_day = current_day + 1
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("UPDATE settings SET value = ? WHERE key = 'current_day'", (str(next_day),))
        await db.commit()
    await msg.answer(f"🏁 *{current_day}-kun* yakunlandi!\n🚀 *{next_day}-kun* ochildi.", parse_mode="Markdown")

# AYNAN SENING ASLIY HISOBOT SCRIPTING
@dp.message(F.text == "📊 hisobot")
async def report(msg: Message):
    async with aiosqlite.connect(DB_NAME) as db:
        cur = await db.execute("""
            SELECT day_num, SUM(qty * price), SUM(chiqim), SUM(litr) 
            FROM sales 
            GROUP BY day_num 
            ORDER BY day_num ASC
        """)
        rows = await cur.fetchall()

    current_day = await get_current_day()
    report_text = "📊 *KUNLIK BIZNES HISOBOTI*\n───────────────────\n"
    grand_kirim, grand_chiqim, grand_litr = 0, 0, 0
    
    if not rows:
        report_text += "Hozircha savdo ma'lumotlari yo'q.\n"
    else:
        for row in rows:
            day = row[0] or 1
            day_kirim = row[1] or 0
            
            day_chiqim = round(row[2] or 0)
            day_litr = round(row[3] or 0, 2)
            day_foyda = day_kirim - day_chiqim
            
            grand_kirim += day_kirim
            grand_chiqim += day_chiqim
            grand_litr += day_litr
            
            report_text += f"📅 *{day}-kun:* \n"
            report_text += f"   💰 Tushum: {day_kirim:,} so‘m\n"
            report_text += f"   📉 Xarajat: {day_chiqim:,} so‘m\n"
            report_text += f"   💵 Sof Foyda: {day_foyda:,} so‘m\n"
            report_text += f"   🛢 Sarflangan mors: *{day_litr} litr*\n\n"
            
    report_text += f"───────────────────\nℹ️ Joriy holat: {current_day}-kun.\n"
    report_text += f"📊 *UMUMIY YAKUN:* \n"
    report_text += f"   💵 Jami tushum: {grand_kirim:,} so‘m\n"
    report_text += f"   💸 Jami xarajat: {round(grand_chiqim):,} so‘m\n"
    report_text += f"   💎 JAMI SOF FOYDA: {round(grand_kirim - grand_chiqim):,} so‘m\n"
    report_text += f"   🧪 JAMI SOTILGAN MORS: *{round(grand_litr, 2)} LITR*"
    
    await msg.answer(report_text, parse_mode="Markdown")

# =====================================================================
# ASLIY MAIN FUNKSIYA (WEB SERVER BILAN INTEGRATSIYA)
# =====================================================================
async def main():
    await init_db()
    await bot.delete_webhook(drop_pending_updates=True)
    
    # Render web serverini fonda ishga tushirish
    await start_web_server()
    asyncio.create_task(self_ping_loop())
    
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())