import logging
import sqlite3
import os
import threading
from datetime import datetime, timezone
import pytz
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
from flask import Flask

# Налаштування логування
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)
logger = logging.getLogger(__name__)

# Отримуємо токен з змінних середовища
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID")

# Локації кав'ярень
LOCATIONS = {
    "location1": "📍 ЖК Славутич",
    "location2": "📍 вул. Анни Ахматової, 31", 
    "location3": "📍 вул. Лариси Руденко, 15/14"
}

# Flask веб-сервер
app = Flask(__name__)

@app.route('/')
def home():
    return 'Coffee Bot is running!'

@app.route('/ping')
def ping():
    return 'OK', 200

@app.route('/health')
def health():
    return 'OK'

def run_web_server():
    try:
        port = int(os.environ.get('PORT', 10000))
        app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)
    except Exception as e:
        logger.error(f"Помилка запуску веб-сервера: {e}")

class CoffeeReviewBot:
    def __init__(self):
        self.init_database()
    
    def init_database(self):
        try:
            conn = sqlite3.connect('coffee_reviews.db')
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS reviews (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    username TEXT,
                    location TEXT,
                    comment TEXT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Помилка ініціалізації БД: {e}")
    
    def save_review(self, user_id, username, location, comment):
        try:
            conn = sqlite3.connect('coffee_reviews.db')
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO reviews (user_id, username, location, comment)
                VALUES (?, ?, ?, ?)
            ''', (user_id, username, location, comment))
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Помилка збереження відгуку: {e}")

bot = CoffeeReviewBot()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    keyboard = [
        [InlineKeyboardButton(loc_name, callback_data=f"location_{loc_id}")]
        for loc_id, loc_name in LOCATIONS.items()
    ]
    await update.message.reply_text(
        "👋 Привіт! Оберіть свою локацію:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def location_selected(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    location_id = query.data.split('_')[1]
    context.user_data['location'] = location_id
    context.user_data['location_name'] = LOCATIONS[location_id]
    await query.edit_message_text("📝 Якщо бажаєте, напишіть більш детальний відгук про каву або обслуговування:")

async def save_review_and_thank(update: Update, context: ContextTypes.DEFAULT_TYPE, comment: str) -> None:
    user = update.effective_user
    location_name = context.user_data.get('location_name', 'Невідома локація')
    
    bot.save_review(
        user_id=user.id,
        username=user.username or user.first_name,
        location=context.user_data.get('location'),
        comment=comment
    )
    
    kiev_time = datetime.now(pytz.timezone('Europe/Kiev')).strftime("%d.%m.%Y %H:%M")
    
    await update.message.reply_text(
        f"❤️ Дякуємо за ваш відгук!\n\n"
        f"📍 Локація: {location_name}\n"
        f"💬 Коментар: {comment or 'Без коментаря'}\n\n"
        f"Новий відгук: /start"
    )
    
    await context.bot.send_message(
        chat_id=ADMIN_CHAT_ID,
        text=f"📝 НОВИЙ ВІДГУК\n\n"
             f"👤 Користувач: {user.username or user.first_name}\n"
             f"📍 Локація: {location_name}\n"
             f"💬 Коментар: {comment or 'Без коментаря'}\n"
             f"🕐 Час: {kiev_time}"
    )
    
    context.user_data.clear()

async def skip_comment(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await save_review_and_thank(update, context, "")

async def receive_comment(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await save_review_and_thank(update, context, update.message.text)

async def admin_reviews(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    conn = sqlite3.connect('coffee_reviews.db')
    cursor = conn.cursor()
    cursor.execute('SELECT username, location, comment, timestamp FROM reviews ORDER BY timestamp DESC LIMIT 10')
    
    text = "📊 Останні 10 відгуків:\n\n"
    for username, location, comment, timestamp in cursor.fetchall():
        dt = datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
        local_time = dt.astimezone(pytz.timezone('Europe/Kiev')).strftime("%d.%m.%Y %H:%M")
        text += (
            f"👤 {username}\n"
            f"📍 {LOCATIONS.get(location, location)}\n"
            f"💬 {comment or 'Без коментаря'}\n"
            f"🕐 {local_time}\n"
            "─" * 30 + "\n\n"
        )
    
    await update.message.reply_text(text)
    conn.close()

def main() -> None:
    web_thread = threading.Thread(target=run_web_server, daemon=True)
    web_thread.start()
    
    application = Application.builder().token(BOT_TOKEN).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("skip", skip_comment))
    application.add_handler(CommandHandler("reviews", admin_reviews))
    application.add_handler(CallbackQueryHandler(location_selected, pattern="^location_"))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, receive_comment))
    
    logger.info("Бот запущений")
    application.run_polling()

if __name__ == '__main__':
    main()
