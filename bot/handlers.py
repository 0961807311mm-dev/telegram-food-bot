import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
from telegram.constants import ParseMode

logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN")

# Створення бота (новий синтаксис)
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN not set")

bot_app = None

def get_bot():
    """Отримати або створити екземпляр бота"""
    global bot_app
    if bot_app is None:
        bot_app = Application.builder().token(BOT_TOKEN).build()
    return bot_app

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обробка команди /start"""
    user = update.effective_user
    WEBAPP_URL = os.getenv("WEBAPP_URL", "")
    
    # Створюємо клавіатуру з WebApp кнопкою
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

Я твій персональний AI-нутриціолог. Допоможу стежити за харчуванням, аналізувати прийоми їжі та досягати цілей у спортзалі.

*Що я вмію:*
📸 Аналізувати фото їжі через AI
📊 Вести щоденник калорій
📈 Розраховувати норми БЖУ
💡 Давати рекомендації
⏰ Нагадувати про прийоми їжі

*Почни з налаштувань, щоб я розрахував твою норму калорій!*
    """
    
    await update.message.reply_text(
        welcome_text,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=reply_markup
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /help"""
    help_text = """
📖 *Довідка*

*Основні команди:*
/start - Головне меню
/help - Ця довідка
/report - Тижневий звіт
/reset - Скинути дані

*Як користуватися:*
1. Налаштуй свій профіль (вага, зріст, ціль)
2. Додавай прийоми їжі через камеру
3. Стеж за прогресом у дашборді
4. Отримуй AI-рекомендації

*Питання?* Звертайся до адміністратора.
    """
    await update.message.reply_text(help_text, parse_mode=ParseMode.MARKDOWN)

async def report_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /report - тижневий звіт"""
    await update.message.reply_text(
        "📊 Формую тижневий звіт... Зачекайте кілька секунд.\n\n"
        "Ваш звіт буде доступний у дашборді найближчим часом.\n"
        "Відкрийте головний дашборд для детальної інформації.",
        parse_mode=ParseMode.MARKDOWN
    )

async def reset_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /reset - скидання даних"""
    await update.message.reply_text(
        "⚠️ *Підтвердження*\n\n"
        "Ви впевнені, що хочете скинути всі дані харчування?\n"
        "Цю дію неможливо скасувати.",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup([
            [
                InlineKeyboardButton("✅ Так, скинути", callback_data="reset_confirm"),
                InlineKeyboardButton("❌ Ні, скасувати", callback_data="reset_cancel")
            ]
        ])
    )

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обробка callback-запитів від кнопок"""
    query = update.callback_query
    await query.answer()
    
    if query.data == "reset_confirm":
        await query.edit_message_text(
            "✅ Всі дані успішно скинуто!\n"
            "Можете починати вести щоденник харчування заново."
        )
    elif query.data == "reset_cancel":
        await query.edit_message_text("❌ Скидання скасовано.")

def setup_handlers(application):
    """Налаштування обробників команд"""
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("report", report_command))
    application.add_handler(CommandHandler("reset", reset_command))
    application.add_handler(CallbackQueryHandler(button_callback))
    
    logger.info("Handlers setup completed")
