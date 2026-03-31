import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import Application, CommandHandler, ContextTypes
from telegram.constants import ParseMode

logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN")
_application = None

def get_application():
    global _application
    if _application is None:
        if not BOT_TOKEN:
            raise ValueError("BOT_TOKEN not set")
        # Використовуємо builder без створення Updater
        _application = Application.builder().token(BOT_TOKEN).build()
        logger.info("Bot application created")
    return _application

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    WEBAPP_URL = os.getenv("WEBAPP_URL", "")
    
    keyboard = [
        [
            InlineKeyboardButton(
                text="📊 Відкрити дашборд",
                web_app=WebAppInfo(url=f"{WEBAPP_URL}/?user_id={user.id}")
            )
        ],
        [
            InlineKeyboardButton(
                text="📸 Додати прийом їжі",
                web_app=WebAppInfo(url=f"{WEBAPP_URL}/add-meal?user_id={user.id}")
            )
        ],
        [
            InlineKeyboardButton(
                text="⚙️ Налаштування",
                web_app=WebAppInfo(url=f"{WEBAPP_URL}/settings?user_id={user.id}")
            )
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    welcome_text = f"""
🍽️ *Вітаю, {user.first_name}!*

Я твій персональний AI-нутриціолог. Допоможу стежити за харчуванням.

*Що я вмію:*
📸 Аналізувати фото їжі через AI
📊 Вести щоденник калорій
📈 Розраховувати норми БЖУ
💡 Давати рекомендації

*Почни з налаштувань!*
    """
    
    await update.message.reply_text(
        welcome_text,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=reply_markup
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = """
📖 *Довідка*

/start - Головне меню
/help - Ця довідка

*Як користуватися:*
1. Налаштуй профіль в меню
2. Додавай прийоми їжі через камеру
3. Стеж за прогресом у дашборді
    """
    await update.message.reply_text(help_text, parse_mode=ParseMode.MARKDOWN)

def setup_handlers(app: Application):
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", help_command))
    logger.info("Handlers setup completed")
