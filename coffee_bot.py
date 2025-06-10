import logging
import sqlite3
import os
import threading
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
from flask import Flask

# Налаштування логування
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)
logger = logging.getLogger(__name__)

# Отримуємо токен з змінних середовища (для безпеки на Render)
BOT_TOKEN = os.getenv("BOT_TOKEN", "7488970157:AAE24_QrAyc5rWyaMqiiOGpCZKPkXs68N0I")

# ID групи куди надсилати відгуки (отримайте через @userinfobot)
ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID", "-1002512354620")

# Локації кав'ярень
LOCATIONS = {
    "location1": "📍 ЖК Славутич",
    "location2": "📍 вул. Анни Ахматової, 31", 
    "location3": "📍 вул. Лариси Руденко 15/14"
}

# Додаємо Flask веб-сервер для Render
app = Flask(__name__)

@app.route('/')
def home():
    return 'Coffee Bot is running!'

@app.route('/health')
def health():
    return 'OK'

def run_web_server():
    """Запуск веб-сервера в окремому потоці"""
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)

# Тексти для оцінок видалено - використовуємо тільки зірочки

class CoffeeReviewBot:
    def __init__(self):
        self.init_database()
    
    def init_database(self):
        """Ініціалізація бази даних для зберігання відгуків"""
        # Використовуємо абсолютний шлях для бази даних
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
        """Збереження відгуку в базу даних"""
        db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'coffee_reviews.db')
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO reviews (user_id, username, location, rating, comment)
            VALUES (?, ?, ?, ?, ?)
        ''', (user_id, username, location, rating, comment))
        
        conn.commit()
        conn.close()

# Ініціалізація бота
bot = CoffeeReviewBot()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Початкове повідомлення з вибором локації"""
    keyboard = []
    
    for loc_id, loc_name in LOCATIONS.items():
        keyboard.append([InlineKeyboardButton(loc_name, callback_data=f"location_{loc_id}")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    welcome_text = """
👋 Привіт! Обери, будь ласка, свою локацію:
"""
    
    await update.message.reply_text(welcome_text, reply_markup=reply_markup)

async def location_selected(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обробка вибору локації"""
    query = update.callback_query
    await query.answer()
    
    location_id = query.data.split('_')[1]
    location_name = LOCATIONS[location_id]
    
    # Зберігаємо вибрану локацію в контексті користувача
    context.user_data['location'] = location_id
    context.user_data['location_name'] = location_name
    
    # Створюємо кнопки для оцінки
    keyboard = []
    for rating in range(1, 6):
        keyboard.append([InlineKeyboardButton(
            f"{rating} ⭐", 
            callback_data=f"rating_{rating}"
        )])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    text = f"""
Ви обрали: {location_name}

☕️ Як вам кава? Оберіть оцінку від 1 до 5:",
"""
    
    await query.edit_message_text(text, reply_markup=reply_markup)

async def rating_selected(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обробка вибору оцінки"""
    query = update.callback_query
    await query.answer()
    
    rating = int(query.data.split('_')[1])
    
    # Зберігаємо оцінку в контексті користувача
    context.user_data['rating'] = rating
    
    rating_text = f"{rating} ⭐"
    location_name = context.user_data.get('location_name', 'Невідома локація')
    
    text = f"""
📍 Локація: {location_name}
⭐ Ваша оцінка: {rating_text}

📝Якщо бажаєте, напишіть більш детальний відгук про каву або обслуговування.

Або натисніть /skip щоб пропустити детальний коментар.
"""
    
    await query.edit_message_text(text)

async def skip_comment(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Пропуск детального коментаря"""
    await save_review_and_thank(update, context, "")

async def receive_comment(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Отримання детального коментаря"""
    comment = update.message.text
    await save_review_and_thank(update, context, comment)

async def save_review_and_thank(update: Update, context: ContextTypes.DEFAULT_TYPE, comment: str) -> None:
    """Збереження відгуку та відправка подяки"""
    user = update.effective_user
    location = context.user_data.get('location', 'unknown')
    location_name = context.user_data.get('location_name', 'Невідома локація')
    rating = context.user_data.get('rating', 0)
    
    # Зберігаємо відгук в базу даних
    bot.save_review(
        user_id=user.id,
        username=user.username or user.first_name,
        location=location,
        rating=rating,
        comment=comment
    )
    
    # Відправляємо повідомлення подяки
    thank_you_text = f"""
Дякуємо за ваш відгук! ❤️

📍 Локація: {location_name}
⭐ Оцінка: {rating} ⭐
💬 Коментар: {comment if comment else "Без коментаря"}

Для нового відгуку натисніть /start
"""
    
    await update.message.reply_text(thank_you_text)
    
    # Відправляємо відгук в адмін-групу
    admin_message = f"""
📝 НОВИЙ ВІДГУК

👤 Користувач: {user.username or user.first_name}
📍 Локація: {location_name}  
⭐ Оцінка: {rating} ⭐
💬 Коментар: {comment if comment else "Без коментаря"}
🕐 Час: {datetime.now().strftime("%d.%m.%Y %H:%M")}
"""
    
    try:
        await context.bot.send_message(chat_id=ADMIN_CHAT_ID, text=admin_message)
    except Exception as e:
        print(f"Помилка відправки в адмін-групу: {e}")
    
    # Очищаємо дані користувача
    context.user_data.clear()

async def admin_reviews(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Команда для перегляду останніх відгуків (тільки для адмінів)"""
    # Тут можна додати перевірку на права адміністратора
    
    db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'coffee_reviews.db')
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT username, location, rating, comment, timestamp 
        FROM reviews 
        ORDER BY timestamp DESC 
        LIMIT 10
    ''')
    
    reviews = cursor.fetchall()
    conn.close()
    
    if not reviews:
        await update.message.reply_text("Поки що немає відгуків.")
        return
    
    text = "📊 Останні 10 відгуків:\n\n"
    
    for review in reviews:
        username, location, rating, comment, timestamp = review
        location_name = LOCATIONS.get(location, location)
        
        text += f"👤 {username}\n"
        text += f"📍 {location_name}\n"
        text += f"⭐ {rating}/5 ⭐\n"
        text += f"💬 {comment if comment else 'Без коментаря'}\n"
        text += f"🕐 {timestamp}\n"
        text += "─" * 30 + "\n\n"
    
    await update.message.reply_text(text)

def main() -> None:
    """Запуск бота"""
    # Запускаємо веб-сервер в окремому потоці
    web_thread = threading.Thread(target=run_web_server)
    web_thread.daemon = True
    web_thread.start()
    
    # Створюємо додаток
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Додаємо обробники команд
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("skip", skip_comment))
    application.add_handler(CommandHandler("reviews", admin_reviews))
    
    # Додаємо обробники callback-запитів
    application.add_handler(CallbackQueryHandler(location_selected, pattern="^location_"))
    application.add_handler(CallbackQueryHandler(rating_selected, pattern="^rating_"))
    
    # Додаємо обробник текстових повідомлень
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, receive_comment))
    
    # Запускаємо бота
    print("Бот та веб-сервер запущені! Натисніть Ctrl+C для зупинки.")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
