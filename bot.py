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
TOKEN = "6463994781:AAF_..."  # O'zingizning to'g'ri tokeningizni yozing
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
# FSM STATE VA STRUKTURA
# =====================================================================
class SavdoState(StatesGroup):
    miqdor_kiritish = State()

async def init_db():
    async with aiosqlite.connect(DB_NAME) as db:
        # User ID ustuni qo'shilgan sales jadvali
        await db.execute("""
            CREATE TABLE IF NOT EXISTS sales (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                day_num INTEGER,
                item TEXT,
                qty INTEGER,
                price INTEGER,
                chiqim INTEGER,
                litr REAL,
                time TEXT
            )
        """)
        # Har bir user uchun alohida joriy kun sozlamalari
        await db.execute("""
            CREATE TABLE IF NOT EXISTS user_settings (
                user_id INTEGER PRIMARY KEY,
                current_day INTEGER DEFAULT 1
            )
        """)
        await db.commit()

async def get_user_day(user_id: int) -> int:
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT current_day FROM user_settings WHERE user_id = ?", (user_id,)) as cursor:
            row = await cursor.fetchone()
            if row:
                return row[0]
            else:
                await db.execute("INSERT INTO user_settings (user_id, current_day) VALUES (?, 1)", (user_id,))
                await db.commit()
                return 1

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

# 🌟 USER UCHUN ALOHIDA /start (KUNNI 1-KUNGA RESET QILISH):
@dp.message(Command("start"))
async def start_cmd(message: Message):
    user_id = message.from_user.id
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            "INSERT INTO user_settings (user_id, current_day) VALUES (?, 1) "
            "ON CONFLICT(user_id) DO UPDATE SET current_day = 1",
            (user_id,)
        )
        await db.commit()
    
    await message.answer(
        "☀️ Tizim yangilandi!\n1-kun boshlandi!\n\nMahsulotni tanlang:",
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
    user_id = message.from_user.id
    
    # SOTILISH NARXLARI:
    narxlar = {"☕ katta": 3000, "🥫 kichik": 2000, "🍼 1L": 7000, "🥛 1.5L": 9000, "🛢 5L": 30000}
    
    # 1 DONA UCHUN CHIQIMLAR (TANNARX):
    tannarxlar = {"☕ katta": 450, "🥫 kichik": 350, "🍼 1L": 2700, "🥛 1.5L": 3300, "🛢 5L": 8500}
    
    # HAQIQIY HAJMLAR (LITR):
    litrlar = {"☕ katta": 0.3, "🥫 kichik": 0.2, "🍼 1L": 1.0, "🥛 1.5L": 1.5, "🛢 5L": 5.0}
    
    birlik_narx = narxlar.get(selected_item, 0)
    birlik_tannarx = tannarxlar.get(selected_item, 0)
    birlik_litr = litrlar.get(selected_item, 0.0)
    
    price = birlik_narx
    total = birlik_narx * qty
    total_chiqim = birlik_tannarx * qty
    total_litr = round(birlik_litr * qty, 2)
    
    current_day = await get_user_day(user_id)

    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            "INSERT INTO sales(user_id, day_num, item, qty, price, chiqim, litr, time) VALUES(?,?,?,?,?,?,?,?)",
            (user_id, current_day, selected_item, qty, price, total_chiqim, total_litr, str(datetime.now()))
        )
        await db.commit()

    await message.answer(
        f"✅ Saqlandi!\n\n"
        f"🛒 Mahsulot: {selected_item}\n"
        f"📦 Miqdor: {qty} ta\n"
        f"💵 Jami tushum: {total:,} so‘m\n"
        f"📉 Ishlatilgan mors: {total_litr} litr",
        reply_markup=get_main_keyboard()
    )
    await state.clear()

# KUNNI YAKUNLASH (FAQAT SHU USER UCHUN)
@dp.message(F.text == "🏁 Kunni yakunlash")
async def finish_day(msg: Message):
    user_id = msg.from_user.id
    current_day = await get_user_day(user_id)
    next_day = current_day + 1
    
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            "UPDATE user_settings SET current_day = ? WHERE user_id = ?",
            (next_day, user_id)
        )
        await db.commit()
        
    await msg.answer(f"🏁 *{current_day}-kun* yakunlandi!\n🚀 *{next_day}-kun* ochildi.", parse_mode="Markdown")

# HISOBOT (FAQAT SHU USER'NIKI):
@dp.message(F.text == "📊 hisobot")
async def report(msg: Message):
    user_id = msg.from_user.id
    async with aiosqlite.connect(DB_NAME) as db:
        cur = await db.execute("""
            SELECT day_num, SUM(qty * price), SUM(chiqim), SUM(litr) 
            FROM sales 
            WHERE user_id = ?
            GROUP BY day_num 
            ORDER BY day_num ASC
        """, (user_id,))
        rows = await cur.fetchall()

    current_day = await get_user_day(user_id)
    report_text = "📊 *KUNLIK BIZNES HISOBOTI*\n───────────────────\n"
    grand_kirim, grand_chiqim, grand_litr = 0, 0, 0
    
    if not rows:
        report_text += "Hozircha sizda savdo ma'lumotlari yo'q.\n"
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
# RUN
# =====================================================================
async def main():
    await init_db()
    await bot.delete_webhook(drop_pending_updates=True)
    await start_web_server()
    asyncio.create_task(self_ping_loop())
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
