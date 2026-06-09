import asyncio
import logging
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.utils.keyboard import ReplyKeyboardBuilder
import aiosqlite
import aiohttp
from aiohttp import web

# 1. BOT TOKEN VA RENDER URL (O'zingiznikiga almashtiring)
TOKEN = "8964012400:AAFVLbUReppLSsbJSi-403HSSsYZt0kTiC0"  # BotFather'dan olingan to'g'ri token turishi kerak!
RENDER_URL = "https://jasur-mors-bot.onrender.com"

# Bot va Dispatcher obyektlari
bot = Bot(token=TOKEN)
dp = Dispatcher()

# Logging (Xatoliklarni ko'rish uchun)
logging.basicConfig(level=logging.INFO)

# =====================================================================
# RENDER UCHUN VEB-SERVER VA AVTOMATIK UYG'OTUVCHI (1-USUL)
# =====================================================================

# Render ping yuborganda 200 qaytaradigan oddiy sahifa
async def handle_ping(request):
    return web.Response(text="Bot ishlayapti, hammasi joyida!")

# Bot o'z-o'ziga har 10 daqiqada so'rov yuborib, uxlashga qo'ymaydi
async def self_ping_loop():
    await asyncio.sleep(30) # Bot yongandan keyin biroz kutib ishga tushadi
    async with aiohttp.ClientSession() as session:
        while True:
            try:
                async with session.get(RENDER_URL) as response:
                    if response.status == 200:
                        print("🤖 [Keep-Alive] Bot muvaffaqiyatli uyg'otildi!")
            except Exception as e:
                print("⚠️ [Keep-Alive] Ping yuborishda xatolik:", e)
            
            await asyncio.sleep(600) # 10 daqiqa kutadi (600 soniya)

# Veb-serverni orqa fonda yurgizish
async def start_web_server():
    app = web.Application()
    app.router.add_get('/', handle_ping)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', 10000) # Render 10000 portni so'raydi
    await site.start()
    print("🌐 Web Server 10000-portda ishga tushdi!")

# =====================================================================
# MA'LUMOTLAR BAZASI (SQLITE) QISMI
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

# =====================================================================
# BOT BUYRUQLARI VA KLAVIATURA (SAVDO LOGIKASI)
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
    builder.adjust(2, 2, 1, 2) # Tugmalarni qatorga joylashtirish
    return builder.as_markup(resize_keyboard=True)

@dp.message(Command("start"))
async def start_cmd(message: types.Message):
    await message.answer(
        "☀️ 1-kun boshlandi (Sinov rejimi)!\nMahsulotni tanlang:",
        reply_markup=get_main_keyboard()
    )

# Tugmalar bosilganda ishlaydigan handler (O'zingizni biznes hisob-kitobingiz)
@dp.message(F.text.in_(["☕ katta", "🥫 kichik", "🍼 1L", "🥛 1.5L", "🛢 5L"]))
async def handle_sales(message: types.Message):
    mahsulot = message.text
    # Bu yerga savdo kiritilganda bazaga yozish kodlaringiz tushadi
    await message.answer(f"✅ {mahsulot} savdoga qo'shildi!")

@dp.message(F.text == "📊 Hisobot")
async def show_report(message: types.Message):
    # Bu yerda bazadan ma'lumotlarni yig'ib hisobot chiqariladi
    hisobot_matni = (
        "📊 **KUNLIK BIZNES HISOBOTI**\n\n"
        "📆 1-kun:\n"
        "💰 Tushum: 372,000 so'm\n"
        "📉 Xarajat: 121,500 so'm\n"
        "💎 Sof Foyda: 250,500 so'm\n"
        "🥤 Sarflangan mors: 48.9 litr"
    )
    await message.answer(hisobot_matni)

@dp.message(F.text == "🏁 Kunni yakunlash")
async def end_day(message: types.Message):
    await message.answer("🏁 Kun yakunlandi! Hisobotlar saqlandi.")

# =====================================================================
# ASOSIY ISHGA TUSHIRISH (MAIN) FURIYASI
# =====================================================================
async def main():
    # 1. Bazani yaratish/tekshirish
    await init_db()
    
    # 2. Render veb-serverini yoqish
    await start_web_server()
    
    # 3. Avtomatik o'zini uyg'otish tizimini fonda yoqish (1-USUL)
    asyncio.create_task(self_ping_loop())
    
    # 4. Telegram botni polling (xabarlarni kutish) rejimida yoqish
    print("🤖 Bot muvaffaqiyatli tarmoqqa ulandi!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())