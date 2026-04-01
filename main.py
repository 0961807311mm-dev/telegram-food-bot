# ============================================
# Файл: main.py (ПОВНИЙ ФІНАЛЬНИЙ)
# ============================================
import os
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Form, UploadFile, File
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv
from datetime import datetime, timedelta
from typing import Optional, List
import json

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN")
WEBAPP_URL = os.getenv("WEBAPP_URL", "https://telegram-food-bot-jedx.onrender.com")

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import Application, CommandHandler, ContextTypes
from telegram.constants import ParseMode

# Імпорт сервісів
from services.gemini import GeminiService
from services.supabase_client import supabase, init_supabase
from services.nutrition import NutritionCalculator

# Ініціалізація сервісів
try:
    gemini_service = GeminiService()
    logger.info("Gemini service initialized")
except Exception as e:
    logger.error(f"Gemini init error: {e}")
    gemini_service = None

nutrition_calculator = NutritionCalculator()

# Глобальний екземпляр бота
app_instance = None

# ============================================
# TELEGRAM БОТ
# ============================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Відповідає на команду /start"""
    user = update.effective_user
    
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

Я твій персональний AI-нутриціолог на базі *Gemini 2.5 Flash*.

*Що я вмію:*
📸 Аналізувати фото їжі через AI
📊 Вести щоденник калорій
📈 Розраховувати норми БЖУ
💡 Давати персоналізовані рекомендації
⏰ Нагадувати про прийоми їжі
🤖 Аналізувати харчування за тиждень

*Як користуватися:*
1️⃣ Налаштуй свій профіль (вік, вага, ціль)
2️⃣ Додавай прийоми їжі через камеру
3️⃣ Стеж за прогресом у дашборді
4️⃣ Отримуй AI-рекомендації

*Почни з налаштувань, щоб я розрахував твою норму калорій!*
"""
    
    await update.message.reply_text(
        welcome_text,
        parse_mode=ParseMode.MARKDOWN,
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
        
        webhook_url = f"{WEBAPP_URL}/webhook"
        await app_instance.bot.set_webhook(webhook_url)
        
        logger.info(f"✅ Bot setup complete. Webhook: {webhook_url}")
    
    return app_instance

# ============================================
# FASTAPI ДОДАТОК
# ============================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Управління життєвим циклом"""
    logger.info("🚀 Starting up...")
    
    # Ініціалізація Supabase
    init_supabase()
    
    # Налаштування бота
    await setup_bot()
    
    logger.info("✅ Startup complete")
    
    yield
    
    logger.info("🛑 Shutting down...")
    if app_instance:
        await app_instance.bot.delete_webhook()
        await app_instance.shutdown()

app = FastAPI(lifespan=lifespan)

# Монтуємо статичні файли
os.makedirs("webapp/static", exist_ok=True)
app.mount("/static", StaticFiles(directory="webapp/static"), name="static")

# ============================================
# TELEGRAM WEBHOOK
# ============================================

@app.post("/webhook")
async def webhook(request: Request):
    """Обробка вебхуків від Telegram"""
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

# ============================================
# WEBAPP СТОРІНКИ
# ============================================

@app.get("/")
async def index():
    """Головна сторінка дашборду"""
    try:
        with open("webapp/index.html", "r", encoding="utf-8") as f:
            html = f.read()
        return HTMLResponse(content=html)
    except FileNotFoundError:
        return HTMLResponse("""
        <!DOCTYPE html>
        <html>
        <head><title>FoodTracker</title></head>
        <body>
            <h1>🍽️ FoodTracker</h1>
            <p>Бот працює! Відкрийте Telegram та надішліть /start</p>
        </body>
        </html>
        """)

@app.get("/add-meal")
async def add_meal_page():
    """Сторінка додавання їжі"""
    try:
        with open("webapp/add_meal.html", "r", encoding="utf-8") as f:
            html = f.read()
        return HTMLResponse(content=html)
    except FileNotFoundError:
        return HTMLResponse("""
        <!DOCTYPE html>
        <html>
        <head><title>Додати прийом</title></head>
        <body>
            <h1>📸 Додати прийом їжі</h1>
            <input type="file" id="photo" accept="image/*">
            <button onclick="analyze()">Аналізувати</button>
            <div id="result"></div>
            <script>
                async function analyze() {
                    const file = document.getElementById('photo').files[0];
                    const formData = new FormData();
                    formData.append('photo', file);
                    const response = await fetch('/api/analyze', {method: 'POST', body: formData});
                    const data = await response.json();
                    document.getElementById('result').innerHTML = JSON.stringify(data);
                }
            </script>
        </body>
        </html>
        """)

@app.get("/settings")
async def settings_page():
    """Сторінка налаштувань"""
    try:
        with open("webapp/settings.html", "r", encoding="utf-8") as f:
            html = f.read()
        return HTMLResponse(content=html)
    except FileNotFoundError:
        return HTMLResponse("""
        <!DOCTYPE html>
        <html>
        <head><title>Налаштування</title></head>
        <body>
            <h1>⚙️ Налаштування</h1>
            <form id="profileForm">
                <input type="number" id="age" placeholder="Вік">
                <select id="gender"><option>male</option><option>female</option></select>
                <input type="number" id="height" placeholder="Зріст">
                <input type="number" id="weight" placeholder="Вага">
                <button type="submit">Зберегти</button>
            </form>
            <script>
                const telegramId = new URLSearchParams(window.location.search).get('user_id');
                document.getElementById('profileForm').onsubmit = async (e) => {
                    e.preventDefault();
                    const profile = {
                        age: document.getElementById('age').value,
                        gender: document.getElementById('gender').value,
                        height: document.getElementById('height').value,
                        weight: document.getElementById('weight').value,
                        activity_level: 'moderate',
                        goal: 'maintain'
                    };
                    await fetch(`/api/user/${telegramId}`, {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify(profile)
                    });
                    alert('Збережено!');
                };
            </script>
        </body>
        </html>
        """)

# ============================================
# API ENDPOINTS
# ============================================

@app.get("/api/user/{telegram_id}")
async def get_user(telegram_id: int):
    """Отримати дані користувача"""
    try:
        if supabase is None:
            return JSONResponse({"error": "Database not initialized"}, status_code=500)
        
        response = supabase.table("users").select("*").eq("telegram_id", telegram_id).execute()
        if response.data:
            return JSONResponse(response.data[0])
        return JSONResponse({"error": "User not found"}, status_code=404)
    except Exception as e:
        logger.error(f"Error getting user: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)

@app.post("/api/user/{telegram_id}")
async def update_user(telegram_id: int, profile: dict):
    """Оновити профіль користувача"""
    try:
        if supabase is None:
            return JSONResponse({"error": "Database not initialized"}, status_code=500)
        
        # Розраховуємо норму калорій
        daily_calories = nutrition_calculator.calculate_tdee({
            "age": profile.get("age", 25),
            "gender": profile.get("gender", "male"),
            "height": profile.get("height", 170),
            "weight": profile.get("weight", 70),
            "activity_level": profile.get("activity_level", "moderate"),
            "goal": profile.get("goal", "maintain")
        })
        
        data = {
            "telegram_id": telegram_id,
            "age": profile.get("age"),
            "gender": profile.get("gender"),
            "height": profile.get("height"),
            "weight": profile.get("weight"),
            "activity_level": profile.get("activity_level"),
            "goal": profile.get("goal"),
            "daily_calorie_goal": daily_calories,
            "updated_at": datetime.utcnow().isoformat()
        }
        
        # Перевіряємо чи існує користувач
        existing = supabase.table("users").select("*").eq("telegram_id", telegram_id).execute()
        
        if existing.data:
            response = supabase.table("users").update(data).eq("telegram_id", telegram_id).execute()
        else:
            data["created_at"] = datetime.utcnow().isoformat()
            response = supabase.table("users").insert(data).execute()
        
        return JSONResponse(response.data[0] if response.data else {})
    except Exception as e:
        logger.error(f"Error updating user: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)

@app.get("/api/meals/{telegram_id}")
async def get_meals(telegram_id: int, date: Optional[str] = None):
    """Отримати прийоми їжі за день"""
    try:
        if supabase is None:
            return JSONResponse({"error": "Database not initialized"}, status_code=500)
        
        if not date:
            date = datetime.utcnow().date().isoformat()
        
        start_date = f"{date}T00:00:00"
        end_date = f"{date}T23:59:59"
        
        response = supabase.table("meals").select("*").eq("telegram_id", telegram_id).gte("created_at", start_date).lte("created_at", end_date).order("created_at", desc=True).execute()
        
        return JSONResponse(response.data)
    except Exception as e:
        logger.error(f"Error getting meals: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)

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

@app.post("/api/meals")
async def create_meal(meal: dict):
    """Зберегти прийом їжі"""
    try:
        if supabase is None:
            return JSONResponse({"error": "Database not initialized"}, status_code=500)
        
        meal_data = {
            "telegram_id": meal.get("telegram_id"),
            "photo_url": meal.get("photo_url"),
            "name": meal.get("name"),
            "calories": meal.get("calories"),
            "protein": meal.get("protein"),
            "fat": meal.get("fat"),
            "carbs": meal.get("carbs"),
            "feedback": meal.get("feedback"),
            "created_at": datetime.utcnow().isoformat()
        }
        
        response = supabase.table("meals").insert(meal_data).execute()
        
        return JSONResponse(response.data[0] if response.data else {})
    except Exception as e:
        logger.error(f"Error creating meal: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)

@app.get("/api/weekly-report/{telegram_id}")
async def get_weekly_report(telegram_id: int):
    """Отримати тижневий звіт з AI-аналізом"""
    try:
        if supabase is None:
            return JSONResponse({"error": "Database not initialized"}, status_code=500)
        
        week_ago = (datetime.utcnow() - timedelta(days=7)).isoformat()
        
        response = supabase.table("meals").select("*").eq("telegram_id", telegram_id).gte("created_at", week_ago).execute()
        
        meals = response.data
        
        if not meals:
            return JSONResponse({"error": "No meals found for the last week"}, status_code=404)
        
        # Агрегуємо дані
        total_calories = sum(m.get("calories", 0) for m in meals)
        total_protein = sum(m.get("protein", 0) for m in meals)
        total_fat = sum(m.get("fat", 0) for m in meals)
        total_carbs = sum(m.get("carbs", 0) for m in meals)
        
        avg_per_day = {
            "calories": total_calories / 7,
            "protein": total_protein / 7,
            "fat": total_fat / 7,
            "carbs": total_carbs / 7
        }
        
        # Отримуємо профіль користувача
        user_response = supabase.table("users").select("*").eq("telegram_id", telegram_id).execute()
        user_profile = user_response.data[0] if user_response.data else None
        
        # Генеруємо AI аналіз
        ai_analysis = "📊 *Тижневий звіт*\n\n"
        
        if gemini_service:
            try:
                ai_analysis = await gemini_service.analyze_weekly(meals, avg_per_day, user_profile)
            except Exception as e:
                logger.error(f"Gemini weekly analysis error: {e}")
                ai_analysis = "⚠️ Не вдалося згенерувати AI-аналіз. Спробуйте пізніше."
        
        return JSONResponse({
            "total": {
                "calories": total_calories,
                "protein": total_protein,
                "fat": total_fat,
                "carbs": total_carbs
            },
            "average_per_day": avg_per_day,
            "meals_count": len(meals),
            "ai_analysis": ai_analysis
        })
    except Exception as e:
        logger.error(f"Error getting weekly report: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)

@app.post("/api/notifications/{telegram_id}")
async def set_notifications(telegram_id: int, times: List[str]):
    """Встановити час нагадувань"""
    try:
        if supabase is None:
            return JSONResponse({"error": "Database not initialized"}, status_code=500)
        
        supabase.table("notifications").delete().eq("telegram_id", telegram_id).execute()
        
        for time_str in times:
            data = {
                "telegram_id": telegram_id,
                "notification_time": time_str,
                "is_active": True,
                "created_at": datetime.utcnow().isoformat()
            }
            supabase.table("notifications").insert(data).execute()
        
        return JSONResponse({"status": "success", "times": times})
    except Exception as e:
        logger.error(f"Error setting notifications: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)

@app.get("/api/notifications/{telegram_id}")
async def get_notifications(telegram_id: int):
    """Отримати налаштування нагадувань"""
    try:
        if supabase is None:
            return JSONResponse({"error": "Database not initialized"}, status_code=500)
        
        response = supabase.table("notifications").select("*").eq("telegram_id", telegram_id).execute()
        times = [n.get("notification_time") for n in response.data if n.get("is_active")]
        return JSONResponse({"times": times})
    except Exception as e:
        logger.error(f"Error getting notifications: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)

# ============================================
# HEALTH CHECK
# ============================================

@app.get("/health")
async def health():
    """Перевірка стану сервісу"""
    return JSONResponse({
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "supabase": "connected" if supabase else "disconnected",
        "gemini": "initialized" if gemini_service else "failed",
        "bot": "ready" if app_instance else "initializing"
    })

# ============================================
# ЗАПУСК
# ============================================

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
