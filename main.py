import os
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from telegram.ext import Application, CommandHandler
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.constants import ParseMode

BOT_TOKEN = os.getenv("BOT_TOKEN")
_application = None

def get_application():
    global _application
    if _application is None:
        if not BOT_TOKEN:
            raise ValueError("BOT_TOKEN not set")
        _application = Application.builder().token(BOT_TOKEN).build()
        logger.info("Bot application created")
    return _application

async def start_command(update: Update, context):
    user = update.effective_user
    WEBAPP_URL = os.getenv("WEBAPP_URL", "https://your-app.onrender.com")
    
    keyboard = [[
        InlineKeyboardButton(
            text="📊 Відкрити дашборд",
            web_app=WebAppInfo(url=f"{WEBAPP_URL}/")
        )
    ]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    welcome_text = f"🍽️ *Вітаю, {user.first_name}!*\n\nЦе мінімальна версія бота для перевірки."
    
    await update.message.reply_text(
        welcome_text,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=reply_markup
    )

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting bot...")
    bot = get_application()
    bot.add_handler(CommandHandler("start", start_command))
    
    webhook_url = f"{os.getenv('WEBAPP_URL')}/webhook"
    await bot.bot.set_webhook(webhook_url)
    logger.info(f"Webhook set to {webhook_url}")
    
    yield
    
    logger.info("Shutting down...")
    await bot.bot.delete_webhook()

app = FastAPI(lifespan=lifespan)

@app.post("/webhook")
async def webhook(request: Request):
    try:
        update_data = await request.json()
        bot = get_application()
        await bot.process_update(update_data)
        return JSONResponse({"status": "ok"})
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return JSONResponse({"status": "error"}, status_code=500)

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
