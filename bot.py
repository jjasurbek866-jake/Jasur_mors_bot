import asyncio
import logging
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import ReplyKeyboardBuilder
import aiosqlite
import aiohttp
from aiohttp import web
from datetime import datetime

# 1. SOZLAMALAR
TOKEN = "8964012400:AAFVLbUReppLSsbJSi-403HSSsYZt0kTiC0"  # O'zingizning to'g'ri tokeningizni yozing
RENDER_URL = "https://jasur-mors-bot.onrender.com"

bot = Bot(token=TOKEN)
dp = Dispatcher()
logging.basicConfig(level=logging.INFO)

# =====================================================================
# RENDER UCHUN AVTOMATIK UYG'OTUVCHI (1-USUL)
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
# STATE - HOLATLAR
# =====================================================================
class SavdoState(StatesGroup):
    miqdor_kiritish = State()

# =====================================================================
# MA'LUMOTLAR BAZASI
# =====================================================================
DB_NAME = "mors_biznes.db"

async def init_db():
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS savdo (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                kun_soni INTEGER,
                turi TEXT,
                quanlity INTEGER,
                narx INTEGER,
                sana TEXT
            )
        """)
        await db.commit()

async def get_current_day():
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT MAX(kun_soni) FROM savdo") as cursor:
            row = await cursor.fetchone()
            if row[0] is None:
                return 1
            return row[0]

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
    builder.button(text="📊 Hisobot")
    builder.adjust(2, 2, 1, 2)
    return builder.as_markup(resize_keyboard=True)

# =====================================================================
# HANDLERLAR (SAVDO LOGIKASI)
# =====================================================================

@dp.message(Command("start"))
async def start_cmd(message: types.Message):
    joriy_kun = await get_current_day()
    await message.answer(
        f"☀️ {joriy_kun}-kun boshlandi (Sinov rejimi)!\nMahsulotni tanlang:",
        reply_markup=get_main_keyboard()
    )

@dp.message(F.text.in_(["☕ katta", "🥫 kichik", "🍼 1L", "🥛 1.5L", "🛢 5L"]))
async def process_mahsulot(message: types.Message, state: FSMContext):
    await state.update_data(tanlangan_mahsulot=message.text)
    await state.set_state(SavdoState.miqdor_kiritish)
    await message.answer(f"Nechta {message.text} sotildi? (Faqat son kiriting):")

@dp.message(SavdoState.miqdor_kiritish)
async def process_miqdor(message: types.Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("⚠️ Iltimos, faqat musbat son kiriting!")
        return

    miqdor = int(message.text)
    user_data = await state.get_data()
    mahsulot = user_data['tanlangan_mahsulot']
    
    # SENING ASLIY NARX REJANG:
    narxlar = {"☕ katta": 8000, "🥫 kichik": 5000, "🍼 1L": 12000, "🥛 1.5L": 16000, "🛢 5L": 50000}
    birlik_narx = narxlar.get(mahsulot, 0)
    jami_narx = birlik_narx * miqdor
    
    joriy_kun = await get_current_day()
    sana_str = datetime.now().strftime("%Y-%m-%d %H:%M")

    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            "INSERT INTO savdo (kun_soni, turi, quanlity, narx, sana) VALUES (?, ?, ?, ?, ?)",
            (joriy_kun, mahsulot, miqdor, jami_narx, sana_str)
        )
        await db.commit()

    await state.clear()
    await message.answer(f"✅ Saqlandi! {miqdor} ta {mahsulot} kiritildi.", reply_markup=get_main_keyboard())

# OLDINGI ESKI FORMATDAGI ASLIY HISOBOT TIZIMI
@dp.message(F.text == "📊 Hisobot")
async def show_report(message: types.Message):
    joriy_kun = await get_current_day()
    
    # Sening original litr va xarajat o'lchovlaring:
    litr_olchov = {"☕ katta": 0.4, "🥫 kichik": 0.25, "🍼 1L": 1.0, "🥛 1.5L": 1.5, "🛢 5L": 5.0}
    xarajat_olchov = {"☕ katta": 2500, "🥫 kichik": 1500, "🍼 1L": 4000, "🥛 1.5L": 5500, "🛢 5L": 18000}

    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT turi, quanlity, narx FROM savdo WHERE kun_soni = ?", (joriy_kun,)) as cursor:
            rows = await cursor.fetchall()

    if not rows:
        await message.answer(f"📊 {joriy_kun}-kun uchun hali hech qanday savdo kiritilmadi.")
        return

    jami_tushum = 0
    jami_xarajat = 0
    jami_litr = 0.0

    for row in rows:
        turi, miqdor, narx = row
        if turi == "KUN_BOSHILISHI":
            continue
        jami_tushum += narx
        jami_xarajat += xarajat_olchov.get(turi, 0) * miqdor
        jami_litr += litr_olchov.get(turi, 0.0) * miqdor

    sof_foyda = jami_tushum - jami_xarajat

    hisobot_matni = (
        f"📊 **KUNLIK BIZNES HISOBOTI**\n\n"
        f"📆 {joriy_kun}-kun:\n"
        f"💰 Tushum: {jami_tushum:,} so'm\n"
        f"📉 Xarajat: {jami_xarajat:,} so'm\n"
        f"💎 Sof Foyda: {sof_foyda:,} so'm\n"
        f"🥤 Sarflangan mors: {round(jami_litr, 1)} litr"
    )
    await message.answer(hisobot_matni)

@dp.message(F.text == "🏁 Kunni yakunlash")
async def end_day(message: types.Message):
    joriy_kun = await get_current_day()
    
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            "INSERT INTO savdo (kun_soni, turi, quanlity, narx, sana) VALUES (?, ?, ?, ?, ?)",
            (joriy_kun + 1, "KUN_BOSHILISHI", 0, 0, datetime.now().strftime("%Y-%m-%d"))
        )
        await db.commit()
        
    await message.answer(f"🏁 {joriy_kun}-kun yakunlandi! Ertaga {joriy_kun + 1}-kun hisoblanadi.", reply_markup=get_main_keyboard())

# =====================================================================
# RUN
# =====================================================================
async def main():
    await init_db()
    await start_web_server()
    asyncio.create_task(self_ping_loop())
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())