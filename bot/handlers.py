# ============================================
# Файл: bot/handlers.py (ПОВНИЙ)
# ============================================
import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

logger = logging.getLogger(__name__)

WEBAPP_URL = os.getenv("WEBAPP_URL", "https://telegram-food-bot-jedx.onrender.com")

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обробка команди /start - показує головне меню"""
    user = update.effective_user
    logger.info(f"📨 Start command from user {user.id}")
    
    # Статичне меню з кнопками
    keyboard = [
        [
            InlineKeyboardButton(
                text="📊 ДАШБОРД",
                web_app=WebAppInfo(url=f"{WEBAPP_URL}/?user_id={user.id}")
            )
        ],
        [
            InlineKeyboardButton(
                text="📸 ДОДАТИ СТРАВУ",
                web_app=WebAppInfo(url=f"{WEBAPP_URL}/add-meal?user_id={user.id}")
            )
        ],
        [
            InlineKeyboardButton(
                text="⚙️ НАЛАШТУВАННЯ",
                web_app=WebAppInfo(url=f"{WEBAPP_URL}/settings?user_id={user.id}")
            )
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    welcome_text = f"""
🍽️ *FoodTracker Pro*

Вітаю, {user.first_name}! 👋

Це твій персональний AI-нутриціолог на базі *Gemini 2.5 Flash*.

*📊 ДАШБОРД* - перегляд статистики та прогресу
*📸 ДОДАТИ СТРАВУ* - аналіз фото через AI
*⚙️ НАЛАШТУВАННЯ* - профіль та параметри

Натискай на кнопки нижче, щоб почати! 🚀
"""
    
    await update.message.reply_text(
        welcome_text,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=reply_markup
    )
    logger.info(f"✅ Menu sent to user {user.id}")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обробка команди /help"""
    user = update.effective_user
    
    keyboard = [
        [
            InlineKeyboardButton(
                text="📊 ДАШБОРД",
                web_app=WebAppInfo(url=f"{WEBAPP_URL}/?user_id={user.id}")
            )
        ],
        [
            InlineKeyboardButton(
                text="📸 ДОДАТИ СТРАВУ",
                web_app=WebAppInfo(url=f"{WEBAPP_URL}/add-meal?user_id={user.id}")
            )
        ],
        [
            InlineKeyboardButton(
                text="⚙️ НАЛАШТУВАННЯ",
                web_app=WebAppInfo(url=f"{WEBAPP_URL}/settings?user_id={user.id}")
            )
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    help_text = """
📖 *Довідка*

*Основні команди:*
/start - Головне меню
/help - Ця довідка

*Як користуватися:*
1️⃣ Налаштуй свій профіль (вік, вага, зріст)
2️⃣ Додавай прийоми їжі через камеру
3️⃣ Стеж за прогресом у дашборді
4️⃣ Отримуй AI-рекомендації

*Підтримка:* @your_support
"""
    
    await update.message.reply_text(
        help_text,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=reply_markup
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обробка будь-якого тексту - показує головне меню"""
    user = update.effective_user
    logger.info(f"📨 Message from user {user.id}: {update.message.text}")
    
    keyboard = [
        [
            InlineKeyboardButton(
                text="📊 ДАШБОРД",
                web_app=WebAppInfo(url=f"{WEBAPP_URL}/?user_id={user.id}")
            )
        ],
        [
            InlineKeyboardButton(
                text="📸 ДОДАТИ СТРАВУ",
                web_app=WebAppInfo(url=f"{WEBAPP_URL}/add-meal?user_id={user.id}")
            )
        ],
        [
            InlineKeyboardButton(
                text="⚙️ НАЛАШТУВАННЯ",
                web_app=WebAppInfo(url=f"{WEBAPP_URL}/settings?user_id={user.id}")
            )
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "🍽️ *Головне меню*\n\nОберіть дію:",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=reply_markup
    )

def setup_handlers(application):
    """Налаштування обробників бота"""
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    logger.info("✅ Handlers setup completed")
