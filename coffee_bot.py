import logging
import sqlite3
import os
import threading
from datetime import datetime
from pytz import timezone  # 🔧 ДОДАНО
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
from flask import Flask

# Налаштування логування
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Токен бота і ID адмін-групи
BOT_TOKEN = os.getenv("BOT_TOKEN", "7488970157:AAE24_QrAyc5rWyaMqiiOGpCZKPkXs68N0I")
ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID", "-1002512354620")

# Локації
LOCATIONS = {
    "location1": "📍 ЖК Славутич",
    "location2": "📍 вул. Анни Ахматової, 31",
    "location3": "📍 вул. Лариси Руденко 15/14"
}

# Flask сервер для Render
app = Flask(__name__)

@app.route('/')
def home():
    return 'Coffee Bot is running!'

@app.route('/health')
def health():
    return 'OK'

def run_web_server():
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)

class CoffeeReviewBot:
    def __init__(self):
        self.init_database()
    
    def init_database(self):
        db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'coffee_reviews.db')
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS reviews (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                username TEXT,
                location TEXT,
                rating INTEGER,
                comment TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        conn.commit()
        conn.close()

    def save_review(self, user_id, username, location, rating, comment):
        db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'coffee_reviews.db')
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO reviews (user_id, username, location, rating, comment)
            VALUES (?, ?, ?, ?, ?)
        ''', (user_id, username, location, rating, comment))
        conn.commit()
        conn.close()

bot = CoffeeReviewBot()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[InlineKeyboardButton(loc_name, callback_data=f"location_{loc_id}")]
                for loc_id, loc_name in LOCATIONS.items()]
    await update.message.reply_text(
        "☕ Вітаємо в системі відгуків про нашу каву! ☕\n\nОберіть локацію:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def location_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    location_id = query.data.split('_')[1]
    context.user_data['location'] = location_id
    context.user_data['location_name'] = LOCATIONS[location_id]

    keyboard = [[InlineKeyboardButton(f"{rating} ⭐", callback_data=f"rating_{rating}")]
                for rating in range(1, 6)]

    await query.edit_message_text(
        f"Ви обрали: {LOCATIONS[location_id]}\n\nОцініть нашу каву від 1 до 5 зірок:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def rating_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    rating = int(query.data.split('_')[1])
    context.user_data['rating'] = rating

    location_name = context.user_data.get('location_name', 'Невідома локація')
    await query.edit_message_text(
        f"📍 Локація: {location_name}\n⭐ Ваша оцінка: {rating} ⭐\n\n"
        "Напишіть коментар або натисніть /skip щоб пропустити."
    )

async def skip_comment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await save_review_and_thank(update, context, "")

async def receive_comment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await save_review_and_thank(update, context, update.message.text)

async def save_review_and_thank(update: Update, context: ContextTypes.DEFAULT_TYPE, comment: str):
    user = update.effective_user
    location = context.user_data.get('location', 'unknown')
    location_name = context.user_data.get('location_name', 'Невідома локація')
    rating = context.user_data.get('rating', 0)

    bot.save_review(user.id, user.username or user.first_name, location, rating, comment)

    await update.message.reply_text(
        f"🙏 Дякуємо!\n📍 {location_name}\n⭐ {rating} ⭐\n💬 {comment or 'Без коментаря'}\n\n"
        "Для нового відгуку натисніть /start"
    )

    # 🕐 Виправлений час
    kyiv_time = datetime.now(timezone("Europe/Kyiv")).strftime("%d.%m.%Y %H:%M")

    admin_message = (
        f"📝 НОВИЙ ВІДГУК\n\n"
        f"👤 Користувач: {user.username or user.first_name}\n"
        f"📍 Локація: {location_name}\n"
        f"⭐ Оцінка: {rating} ⭐\n"
        f"💬 Коментар: {comment or 'Без коментаря'}\n"
        f"🕐 Час: {kyiv_time}"
    )

    try:
        await context.bot.send_message(chat_id=ADMIN_CHAT_ID, text=admin_message)
    except Exception as e:
        print(f"Помилка надсилання в групу: {e}")

    context.user_data.clear()

def main():
    threading.Thread(target=run_web_server).start()
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("skip", skip_comment))
    app.add_handler(CommandHandler("admin", admin_reviews))
    app.add_handler(CallbackQueryHandler(location_selected, pattern="^location_"))
    app.add_handler(CallbackQueryHandler(rating_selected, pattern="^rating_"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, receive_comment))

    app.run_polling()

if __name__ == "__main__":
    main()
