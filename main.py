import os
import logging
from fastapi import FastAPI, Request, Form, UploadFile, File
from fastapi.responses import HTMLResponse, JSONResponse
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN")

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from services.gemini import GeminiService

# Ініціалізація Gemini
gemini_service = GeminiService()

# Глобальний екземпляр бота
app_instance = None

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Відповідає на команду /start"""
    user = update.effective_user
    WEBAPP_URL = os.getenv("WEBAPP_URL", "https://telegram-food-bot-jedx.onrender.com")
    
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
    
    keyboard = [[
        InlineKeyboardButton(
            text="📸 Додати прийом їжі",
            web_app=WebAppInfo(url=f"{WEBAPP_URL}/add-meal?user_id={user.id}")
        ),
        InlineKeyboardButton(
            text="📊 Дашборд",
            web_app=WebAppInfo(url=f"{WEBAPP_URL}/")
        )
    ]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    welcome_text = f"""
🍽️ *Вітаю, {user.first_name}!*

Я AI-нутриціолог на базі *Gemini 2.5 Flash*.

*Що я вмію:*
📸 Аналізувати фото їжі
📊 Розраховувати калорії та БЖУ
💡 Давати рекомендації

*Як користуватися:*
1. Натисни кнопку "Додати прийом їжі"
2. Сфотографуй страву
3. Отримай аналіз та збережи
"""
    
    await update.message.reply_text(
        welcome_text,
        parse_mode="Markdown",
        reply_markup=reply_markup
    )

async def setup_bot():
    """Налаштовує бота"""
    global app_instance
    
    if app_instance is None:
        logger.info("Creating bot application...")
        app_instance = Application.builder().token(BOT_TOKEN).build()
        
        app_instance.add_handler(CommandHandler("start", start))
        
        await app_instance.initialize()
        
        webhook_url = f"{os.getenv('WEBAPP_URL', 'https://telegram-food-bot-jedx.onrender.com')}/webhook"
        await app_instance.bot.set_webhook(webhook_url)
        
        logger.info(f"✅ Bot setup complete. Webhook: {webhook_url}")
    
    return app_instance

# FastAPI додаток
app = FastAPI()

@app.on_event("startup")
async def startup_event():
    logger.info("🚀 Starting up...")
    await setup_bot()
    logger.info("✅ Startup complete")

@app.on_event("shutdown")
async def shutdown_event():
    logger.info("🛑 Shutting down...")
    if app_instance:
        await app_instance.bot.delete_webhook()
        await app_instance.shutdown()

@app.post("/webhook")
async def webhook(request: Request):
    try:
        data = await request.json()
        logger.info(f"📨 Webhook received: {data.get('message', {}).get('text', 'no text')}")
        
        bot_app = await setup_bot()
        update = Update.de_json(data, bot_app.bot)
        await bot_app.process_update(update)
        
        return JSONResponse({"status": "ok"})
    except Exception as e:
        logger.error(f"❌ Webhook error: {e}", exc_info=True)
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)

# ========== API для WebApp ==========

@app.post("/api/analyze")
async def analyze_meal(photo: UploadFile = File(...)):
    """Аналіз фото їжі через Gemini"""
    try:
        photo_bytes = await photo.read()
        analysis = await gemini_service.analyze_meal(photo_bytes, photo.filename)
        return JSONResponse(analysis)
    except Exception as e:
        logger.error(f"Analysis error: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)

@app.get("/")
async def index():
    return HTMLResponse("""
    <!DOCTYPE html>
    <html>
    <head>
        <title>FoodTracker - Gemini AI</title>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            body {
                font-family: system-ui, sans-serif;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                min-height: 100vh;
                margin: 0;
                padding: 20px;
            }
            .container {
                max-width: 600px;
                margin: 0 auto;
                background: white;
                border-radius: 24px;
                padding: 24px;
                box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            }
            h1 { color: #333; margin-bottom: 8px; }
            .badge {
                background: #667eea;
                color: white;
                padding: 4px 12px;
                border-radius: 20px;
                font-size: 12px;
                display: inline-block;
                margin-bottom: 20px;
            }
            button {
                background: #667eea;
                color: white;
                border: none;
                padding: 12px 24px;
                border-radius: 12px;
                font-size: 16px;
                cursor: pointer;
                width: 100%;
                margin-top: 16px;
            }
            button:hover { background: #5a67d8; }
            #result {
                margin-top: 20px;
                padding: 16px;
                background: #f8f9fa;
                border-radius: 16px;
                display: none;
            }
            .loading { text-align: center; color: #666; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🍽️ FoodTracker</h1>
            <div class="badge">🤖 Powered by Gemini 2.5 Flash</div>
            <p>Сфотографуйте страву, і AI визначить калорії та БЖУ</p>
            
            <input type="file" id="photoInput" accept="image/*" style="display: none">
            <button onclick="document.getElementById('photoInput').click()">
                📸 Завантажити фото
            </button>
            
            <div id="result">
                <h3>📊 Результат аналізу</h3>
                <div id="analysisResult"></div>
            </div>
        </div>
        
        <script>
            document.getElementById('photoInput').onchange = async (e) => {
                const file = e.target.files[0];
                if (!file) return;
                
                const formData = new FormData();
                formData.append('photo', file);
                
                document.getElementById('result').style.display = 'block';
                document.getElementById('analysisResult').innerHTML = '<div class="loading">🔍 Аналізую фото через Gemini 2.5 Flash...</div>';
                
                try {
                    const response = await fetch('/api/analyze', {
                        method: 'POST',
                        body: formData
                    });
                    const data = await response.json();
                    
                    document.getElementById('analysisResult').innerHTML = `
                        <p><strong>🍽️ Страва:</strong> ${data.name}</p>
                        <p><strong>🔥 Калорії:</strong> ${data.calories} ккал</p>
                        <p><strong>🥩 Білки:</strong> ${data.protein} г</p>
                        <p><strong>🧈 Жири:</strong> ${data.fat} г</p>
                        <p><strong>🍚 Вуглеводи:</strong> ${data.carbs} г</p>
                        <p><strong>💡 Рекомендація:</strong> ${data.feedback}</p>
                    `;
                } catch (error) {
                    document.getElementById('analysisResult').innerHTML = '<p style="color: red;">❌ Помилка аналізу</p>';
                }
            };
        </script>
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
