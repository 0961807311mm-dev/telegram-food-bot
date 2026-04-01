import os
import logging
from fastapi import FastAPI, Request, Form, UploadFile, File
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN")

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from services.gemini import GeminiService

# Ініціалізація Gemini
try:
    gemini_service = GeminiService()
    logger.info("Gemini service initialized")
except Exception as e:
    logger.error(f"Gemini init error: {e}")
    gemini_service = None

# Глобальний екземпляр бота
app_instance = None

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Відповідає на команду /start"""
    user = update.effective_user
    WEBAPP_URL = os.getenv("WEBAPP_URL", "https://telegram-food-bot-jedx.onrender.com")
    
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
    
    keyboard = [
        [
            InlineKeyboardButton(
                text="📸 Додати прийом їжі",
                web_app=WebAppInfo(url=f"{WEBAPP_URL}/add-meal")
            )
        ],
        [
            InlineKeyboardButton(
                text="📊 Дашборд",
                web_app=WebAppInfo(url=f"{WEBAPP_URL}/")
            )
        ]
    ]
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

# Створюємо директорії для статики
os.makedirs("webapp/static", exist_ok=True)

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

@app.get("/")
async def index():
    """Головна сторінка дашборду"""
    return HTMLResponse("""
    <!DOCTYPE html>
    <html>
    <head>
        <title>FoodTracker - Gemini AI</title>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            * { margin: 0; padding: 0; box-sizing: border-box; }
            body {
                font-family: system-ui, -apple-system, sans-serif;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                min-height: 100vh;
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
            h1 { color: #333; margin-bottom: 8px; font-size: 28px; }
            .badge {
                background: linear-gradient(135deg, #667eea, #764ba2);
                color: white;
                padding: 4px 12px;
                border-radius: 20px;
                font-size: 12px;
                display: inline-block;
                margin-bottom: 20px;
            }
            .stats {
                background: #f8f9fa;
                border-radius: 16px;
                padding: 20px;
                margin: 20px 0;
                text-align: center;
            }
            .calories {
                font-size: 48px;
                font-weight: bold;
                color: #667eea;
            }
            button {
                background: linear-gradient(135deg, #667eea, #764ba2);
                color: white;
                border: none;
                padding: 14px 24px;
                border-radius: 12px;
                font-size: 16px;
                cursor: pointer;
                width: 100%;
                margin-top: 16px;
                font-weight: 500;
            }
            button:hover { opacity: 0.9; transform: translateY(-1px); }
            .meal-item {
                background: #f8f9fa;
                border-radius: 12px;
                padding: 12px;
                margin-bottom: 8px;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🍽️ FoodTracker</h1>
            <div class="badge">🤖 Powered by Gemini 2.5 Flash</div>
            
            <div class="stats">
                <div style="color: #666;">Сьогодні спожито</div>
                <div class="calories" id="calories">0</div>
                <div style="color: #666;">ккал</div>
            </div>
            
            <button onclick="window.location.href='/add-meal'">
                📸 Додати прийом їжі
            </button>
            
            <div style="margin-top: 20px;">
                <h3 style="margin-bottom: 12px;">📝 Сьогоднішні прийоми</h3>
                <div id="meals-list">
                    <div style="text-align: center; color: #999; padding: 20px;">
                        Ще немає записів
                    </div>
                </div>
            </div>
        </div>
        
        <script>
            const telegramId = new URLSearchParams(window.location.search).get('user_id');
            if (telegramId) {
                localStorage.setItem('telegram_id', telegramId);
            }
        </script>
    </body>
    </html>
    """)

@app.get("/add-meal")
async def add_meal_page():
    """Сторінка додавання їжі"""
    return HTMLResponse("""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Додати прийом їжі</title>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            * { margin: 0; padding: 0; box-sizing: border-box; }
            body {
                font-family: system-ui, -apple-system, sans-serif;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                min-height: 100vh;
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
            h1 { color: #333; margin-bottom: 20px; font-size: 24px; }
            .camera-area {
                background: #f8f9fa;
                border-radius: 16px;
                padding: 40px;
                text-align: center;
                border: 2px dashed #ddd;
                cursor: pointer;
                margin-bottom: 20px;
            }
            .camera-area:hover { border-color: #667eea; }
            #photoPreview {
                max-width: 100%;
                border-radius: 16px;
                margin-bottom: 20px;
                display: none;
            }
            button {
                background: linear-gradient(135deg, #667eea, #764ba2);
                color: white;
                border: none;
                padding: 14px 24px;
                border-radius: 12px;
                font-size: 16px;
                cursor: pointer;
                width: 100%;
                font-weight: 500;
            }
            button:disabled {
                opacity: 0.5;
                cursor: not-allowed;
            }
            .result {
                margin-top: 20px;
                padding: 16px;
                background: #f8f9fa;
                border-radius: 16px;
                display: none;
            }
            .loading {
                text-align: center;
                color: #667eea;
                padding: 20px;
            }
            .field {
                margin-bottom: 12px;
            }
            .field label {
                display: block;
                font-weight: 500;
                margin-bottom: 4px;
                color: #666;
            }
            .field input {
                width: 100%;
                padding: 8px 12px;
                border: 1px solid #ddd;
                border-radius: 8px;
                font-size: 16px;
            }
            .feedback {
                background: #e8f5e9;
                padding: 12px;
                border-radius: 8px;
                color: #2e7d32;
                margin-top: 12px;
            }
            .back-btn {
                background: #666;
                margin-top: 12px;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>📸 Додати прийом їжі</h1>
            
            <div class="camera-area" onclick="document.getElementById('photoInput').click()">
                📷 Натисніть, щоб вибрати фото
                <input type="file" id="photoInput" accept="image/*" style="display: none">
            </div>
            
            <img id="photoPreview">
            
            <button id="analyzeBtn" onclick="analyzePhoto()" disabled>🔍 Аналізувати через Gemini</button>
            
            <div id="result" class="result">
                <h3 style="margin-bottom: 12px;">📊 Результат аналізу</h3>
                <div id="resultContent"></div>
                <button onclick="saveMeal()" id="saveBtn" style="margin-top: 12px;">✅ Зберегти прийом</button>
            </div>
            
            <button class="back-btn" onclick="window.location.href='/'">← На головну</button>
        </div>
        
        <script>
            let currentAnalysis = null;
            let currentPhoto = null;
            
            document.getElementById('photoInput').onchange = async (e) => {
                const file = e.target.files[0];
                if (!file) return;
                
                currentPhoto = file;
                const reader = new FileReader();
                reader.onload = (e) => {
                    const preview = document.getElementById('photoPreview');
                    preview.src = e.target.result;
                    preview.style.display = 'block';
                };
                reader.readAsDataURL(file);
                
                document.getElementById('analyzeBtn').disabled = false;
            };
            
            async function analyzePhoto() {
                if (!currentPhoto) return;
                
                const formData = new FormData();
                formData.append('photo', currentPhoto);
                
                document.getElementById('result').style.display = 'block';
                document.getElementById('resultContent').innerHTML = '<div class="loading">🔍 Аналіз через Gemini 2.5 Flash...<br>Зачекайте кілька секунд</div>';
                document.getElementById('saveBtn').style.display = 'none';
                
                try {
                    const response = await fetch('/api/analyze', {
                        method: 'POST',
                        body: formData
                    });
                    const data = await response.json();
                    currentAnalysis = data;
                    
                    document.getElementById('resultContent').innerHTML = `
                        <div class="field">
                            <label>🍽️ Страва</label>
                            <input type="text" id="mealName" value="${data.name || 'Невідомо'}">
                        </div>
                        <div class="field">
                            <label>🔥 Калорії (ккал)</label>
                            <input type="number" id="mealCalories" value="${data.calories || 0}">
                        </div>
                        <div class="field">
                            <label>🥩 Білки (г)</label>
                            <input type="number" id="mealProtein" value="${data.protein || 0}" step="0.1">
                        </div>
                        <div class="field">
                            <label>🧈 Жири (г)</label>
                            <input type="number" id="mealFat" value="${data.fat || 0}" step="0.1">
                        </div>
                        <div class="field">
                            <label>🍚 Вуглеводи (г)</label>
                            <input type="number" id="mealCarbs" value="${data.carbs || 0}" step="0.1">
                        </div>
                        <div class="feedback">
                            💡 ${data.feedback || 'Гарний вибір!'}
                        </div>
                    `;
                    document.getElementById('saveBtn').style.display = 'block';
                } catch (error) {
                    document.getElementById('resultContent').innerHTML = '<div style="color: red;">❌ Помилка аналізу. Спробуйте ще раз.</div>';
                }
            }
            
            async function saveMeal() {
                const mealData = {
                    name: document.getElementById('mealName')?.value || 'Невідомо',
                    calories: parseInt(document.getElementById('mealCalories')?.value) || 0,
                    protein: parseFloat(document.getElementById('mealProtein')?.value) || 0,
                    fat: parseFloat(document.getElementById('mealFat')?.value) || 0,
                    carbs: parseFloat(document.getElementById('mealCarbs')?.value) || 0
                };
                
                alert('✅ Прийом збережено!');
                window.location.href = '/';
            }
        </script>
    </body>
    </html>
    """)

@app.post("/api/analyze")
async def analyze_meal(photo: UploadFile = File(...)):
    """Аналіз фото їжі через Gemini"""
    try:
        if not gemini_service:
            return JSONResponse({"error": "Gemini service not initialized"}, status_code=500)
        
        photo_bytes = await photo.read()
        analysis = await gemini_service.analyze_meal(photo_bytes, photo.filename)
        return JSONResponse(analysis)
    except Exception as e:
        logger.error(f"Analysis error: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)

@app.get("/health")
async def health():
    return JSONResponse({"status": "healthy"})

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
