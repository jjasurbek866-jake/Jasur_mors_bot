import os
import telebot
from telebot import types
import json
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading

# 1. RENDER UCHUN SOXTA VEB-SERVER (Botni 24/7 tirik saqlash uchun)
class SimpleHTTPRequestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is running!")

def run_server():
    # Render o'zi beradigan PORT-ni oladi, topilmasa 10000-portda ishlaydi
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(('0.0.0.0', port), SimpleHTTPRequestHandler)
    server.serve_forever()

# Serverni bot ishlashidan oldin alohida parallel oqimda yoqib yuboramiz
threading.Thread(target=run_server, daemon=True).start()


# 2. BOT TOKЕNINI OLISH VA BOTNI REJISTRATSIYA QILISH
# Render-dagi Environment Variables-ga kiritgan tokeningizni o'qiydi
BOT_TOKEN = os.environ.get("BOT_TOKEN")
bot = telebot.TeleBot(BOT_TOKEN)


# 3. BIZNES LOGIKASI VA SIZNING ESKI BOT KODLARINGIZ
# Ma'lumotlarni saqlash uchun JSON fayl bilan ishlash
DATA_FILE = "mors_biznes_data.json"

def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    return {"kirim": 0, "chiqim": 0, "foyda": 0, "savdo_tarixi": []}

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)

# Boshlang'ich buyruq: /start
@bot.message_handler(commands=['start'])
def start_command(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    btn1 = types.KeyboardButton("📊 Statistika")
    btn2 = types.KeyboardButton("➕ Kirim qo'shish")
    btn3 = types.KeyboardButton("➖ Chiqim qo'shish")
    markup.add(btn1)
    markup.add(btn2, btn3)
    
    bot.send_message(
        message.chat.id, 
        f"Salom {message.from_user.first_name}! Mors biznesingizni hisob-kitob qilish botiga xush kelibsiz. Quyidagi menyudan foydalaning:", 
        reply_markup=markup
    )

# Menyudagi tugmalar bosilganda ishlaydigan qism
@bot.message_handler(func=lambda message: True)
def handle_menu(message):
    data = load_data()
    
    if message.text == "📊 Statistika":
        foyda = data["kirim"] - data["chiqim"]
        text = (
            f"💰 *Biznesingiz statistikasi:*\n\n"
            f"🟩 Umumiy kirim: {data['kirim']} so'm\n"
            f"🟥 Umumiy chiqim: {data['chiqim']} so'm\n"
            f"🟨 Sof foyda: {foyda} so'm"
        )
        bot.send_message(message.chat.id, text, parse_mode="Markdown")
        
    elif message.text == "➕ Kirim qo'shish":
        msg = bot.send_message(message.chat.id, "Kirim miqdorini kiriting (faqat raqamda):")
        bot.register_next_step_handler(msg, process_kirim)
        
    elif message.text == "➖ Chiqim qo'shish":
        msg = bot.send_message(message.chat.id, "Chiqim miqdorini kiriting (faqat raqamda):")
        bot.register_next_step_handler(msg, process_chiqim)

def process_kirim(message):
    try:
        amount = int(message.text)
        data = load_data()
        data["kirim"] += amount
        save_data(data)
        bot.send_message(message.chat.id, f"✅ {amount} so'm kirim muvaffaqiyatli saqlindi!")
    except ValueError:
        bot.send_message(message.chat.id, "❌ Xato! Iltimos, faqat raqam kiriting.")

def process_chiqim(message):
    try:
        amount = int(message.text)
        data = load_data()
        data["chiqim"] += amount
        save_data(data)
        bot.send_message(message.chat.id, f"✅ {amount} so'm chiqim muvaffaqiyatli saqlindi!")
    except ValueError:
        bot.send_message(message.chat.id, "❌ Xato! Iltimos, faqat raqam kiriting.")


# 4. BOTNI DOIMIY ISHGA TUSHIRISH (Polling)
if __name__ == '__main__':
    print("Bot muvaffaqiyatli ishga tushdi...")
    bot.polling(none_stop=True)