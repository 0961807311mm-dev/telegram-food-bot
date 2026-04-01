import os
import logging
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN")

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# Глобальний екземпляр
app_instance = None

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Відповідає на команду /start"""
    logger.info(f"✅ START COMMAND RECEIVED from user {update.effective_user.id}")
    await update.message.reply_text(
        "🍽️ *Бот працює!*\n\nВітаю! Це тестове повідомлення.",
        parse_mode="Markdown"
    )
    logger.info("✅ Reply sent")

async def setup_bot():
    """Налаштовує бота"""
    global app_instance
    
    if app_instance is None:
        logger.info("Creating bot application...")
        app_instance = Application.builder().token(BOT_TOKEN).build()
        
        # Додаємо обробник
        app_instance.add_handler(CommandHandler("start", start))
        
        # Ініціалізуємо
        await app_instance.initialize()
        
        # Встановлюємо вебхук
        webhook_url = f"{os.getenv('WEBAPP_URL', 'https://telegram-food-bot-jedx.onrender.com')}/webhook"
        await app_instance.bot.set_webhook(webhook_url)
        
        logger.info(f"✅ Bot setup complete. Webhook: {webhook_url}")
    
    return app_instance

# FastAPI додаток
app = FastAPI()

@app.on_event("startup")
async def startup_event():
    """Запуск при старті"""
    logger.info("🚀 Starting up...")
    await setup_bot()
    logger.info("✅ Startup complete")

@app.on_event("shutdown")
async def shutdown_event():
    """Зупинка при завершенні"""
    logger.info("🛑 Shutting down...")
    if app_instance:
        await app_instance.bot.delete_webhook()
        await app_instance.shutdown()
    logger.info("✅ Shutdown complete")

@app.post("/webhook")
async def webhook(request: Request):
    """Обробка вебхуків"""
    try:
        data = await request.json()
        logger.info(f"📨 Webhook received: {data.get('message', {}).get('text', 'no text')}")
        
        # Створюємо Update та обробляємо
        update = Update.de_json(data, None)
        bot = await setup_bot()
        await bot.process_update(update)
        
        return JSONResponse({"status": "ok"})
    except Exception as e:
        logger.error(f"❌ Webhook error: {e}", exc_info=True)
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)

@app.get("/")
async def index():
    return HTMLResponse("""
    <html>
    <body>
        <h1>🍽️ FoodTracker Bot</h1>
        <p>Bot is running!</p>
        <p>Status: <span style="color: green;">✅ Active</span></p>
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
