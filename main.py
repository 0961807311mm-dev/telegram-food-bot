import os
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.constants import ParseMode
from telegram.ext import Application, CommandHandler, ContextTypes

BOT_TOKEN = os.getenv("BOT_TOKEN")
_application = None

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        logger.info(f"✅ START_COMMAND CALLED - user: {update.effective_user.id}")
        user = update.effective_user
        WEBAPP_URL = os.getenv("WEBAPP_URL", "https://telegram-food-bot-jedx.onrender.com")
        
        keyboard = [[
            InlineKeyboardButton(
                text="📊 Відкрити дашборд",
                web_app=WebAppInfo(url=f"{WEBAPP_URL}/")
            )
        ]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        welcome_text = f"🍽️ *Вітаю, {user.first_name}!*\n\nБот працює! 🎉\n\nСкоро тут буде дашборд для відстеження харчування."
        
        await update.message.reply_text(
            welcome_text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=reply_markup
        )
        logger.info(f"✅ Reply sent to user {user.id}")
    except Exception as e:
        logger.error(f"❌ Error in start_command: {e}", exc_info=True)

async def get_application():
    global _application
    if _application is None:
        if not BOT_TOKEN:
            raise ValueError("BOT_TOKEN not set")
        
        # Створюємо Application без Updater
        _application = Application.builder().token(BOT_TOKEN).build()
        
        # Додаємо обробник
        _application.add_handler(CommandHandler("start", start_command))
        
        # Ініціалізуємо
        await _application.initialize()
        
        # Важливо: для webhook потрібно налаштувати бота
        await _application.bot.set_webhook(
            f"{os.getenv('WEBAPP_URL', 'https://telegram-food-bot-jedx.onrender.com')}/webhook"
        )
        
        logger.info("Bot application created, initialized and webhook set")
        
        # Виводимо список обробників для перевірки
        handlers_count = len(_application.handlers.get(0, []))
        logger.info(f"Bot has {handlers_count} handlers for updates")
        
    return _application

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting bot...")
    
    # Ініціалізуємо бота (webhook вже встановлюється всередині)
    bot = await get_application()
    
    yield
    
    logger.info("Shutting down...")
    await bot.bot.delete_webhook()
    await bot.shutdown()

app = FastAPI(lifespan=lifespan)

@app.post("/webhook")
async def webhook(request: Request):
    try:
        # Отримуємо дані від Telegram
        update_data = await request.json()
        message_text = update_data.get('message', {}).get('text', 'no text')
        logger.info(f"📨 Received webhook update: {message_text}")
        
        # Створюємо об'єкт Update
        update = Update.de_json(update_data, None)
        
        # Отримуємо бота і обробляємо оновлення
        bot = await get_application()
        
        # Важливо: передаємо бота в update
        await bot.process_update(update)
        
        return JSONResponse({"status": "ok"})
    except Exception as e:
        logger.error(f"❌ Webhook error: {e}", exc_info=True)
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)

@app.get("/")
async def index():
    return HTMLResponse("""
    <!DOCTYPE html>
    <html>
    <head>
        <title>FoodTracker Bot</title>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            body {
                font-family: system-ui, -apple-system, sans-serif;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                min-height: 100vh;
                margin: 0;
                padding: 20px;
                display: flex;
                align-items: center;
                justify-content: center;
            }
            .card {
                background: white;
                border-radius: 24px;
                padding: 32px;
                text-align: center;
                max-width: 400px;
                box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            }
            h1 { color: #333; margin-bottom: 16px; }
            p { color: #666; line-height: 1.5; }
            .status { color: #4caf50; font-weight: bold; }
        </style>
    </head>
    <body>
        <div class="card">
            <h1>🍽️ FoodTracker Bot</h1>
            <p>Бот працює! 🎉</p>
            <p class="status">✅ Статус: активний</p>
            <p>Відкрийте Telegram та надішліть команду <code>/start</code></p>
        </div>
    </body>
    </html>
    """)

@app.get("/health")
async def health():
    return JSONResponse({"status": "healthy"})

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
