# ============================================
# Файл: main.py (ПОВНИЙ ФІНАЛЬНИЙ)
# ============================================
import os
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, UploadFile, File
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

from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters
from bot.handlers import setup_handlers

# Імпорт сервісів
from services.gemini import GeminiService
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
# ТИМЧАСОВЕ СХОВИЩЕ В ПАМ'ЯТІ
# ============================================
_memory_db = {
    "users": {},
    "meals": {},
    "supplements": {},
    "water": {},
    "notifications": {}
}

def init_supabase():
    """Заглушка для сумісності"""
    logger.info("⚠️ Running in memory-only mode")
    return None

supabase = None

def save_user_profile(telegram_id: int, profile: dict):
    """Зберегти профіль в пам'яті"""
    _memory_db["users"][telegram_id] = profile
    logger.info(f"✅ Profile saved in memory for {telegram_id}")
    return profile

def get_user_profile(telegram_id: int):
    """Отримати профіль з пам'яті"""
    return _memory_db["users"].get(telegram_id)

def save_meal(telegram_id: int, meal_data: dict):
    """Зберегти прийом в пам'яті"""
    if telegram_id not in _memory_db["meals"]:
        _memory_db["meals"][telegram_id] = []
    _memory_db["meals"][telegram_id].append(meal_data)
    logger.info(f"✅ Meal saved in memory for {telegram_id}")
    return meal_data

def get_today_meals(telegram_id: int):
    """Отримати прийоми з пам'яті"""
    return _memory_db["meals"].get(telegram_id, [])

def get_weekly_meals(telegram_id: int):
    """Отримати прийоми за тиждень з пам'яті"""
    meals = _memory_db["meals"].get(telegram_id, [])
    week_ago = datetime.now() - timedelta(days=7)
    filtered = []
    for meal in meals:
        try:
            meal_time = datetime.fromisoformat(meal.get("created_at", datetime.now().isoformat()))
            if meal_time >= week_ago:
                filtered.append(meal)
        except:
            filtered.append(meal)
    return filtered

def save_supplement(telegram_id: int, supplement_data: dict):
    """Зберегти вітамін/добавку в пам'яті"""
    if telegram_id not in _memory_db["supplements"]:
        _memory_db["supplements"][telegram_id] = []
    _memory_db["supplements"][telegram_id].append(supplement_data)
    logger.info(f"✅ Supplement saved in memory for {telegram_id}")
    return supplement_data

def get_supplements(telegram_id: int):
    """Отримати вітаміни/добавки з пам'яті"""
    return _memory_db["supplements"].get(telegram_id, [])

def save_water(telegram_id: int, amount: int):
    """Зберегти кількість води в пам'яті"""
    current = _memory_db["water"].get(telegram_id, 0)
    _memory_db["water"][telegram_id] = current + amount
    logger.info(f"✅ Water saved in memory for {telegram_id}: {_memory_db['water'][telegram_id]} ml")
    return _memory_db["water"][telegram_id]

def get_water(telegram_id: int):
    """Отримати кількість води з пам'яті"""
    return _memory_db["water"].get(telegram_id, 0)

def save_notifications(telegram_id: int, times: list):
    """Зберегти нагадування в пам'яті"""
    _memory_db["notifications"][telegram_id] = times
    logger.info(f"✅ Notifications saved in memory for {telegram_id}")
    return True

def get_notifications(telegram_id: int):
    """Отримати нагадування з пам'яті"""
    return _memory_db["notifications"].get(telegram_id, [])

# ============================================
# FASTAPI ДОДАТОК
# ============================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Управління життєвим циклом"""
    logger.info("🚀 Starting up...")
    init_supabase()
    
    # Налаштування бота
    global app_instance
    if app_instance is None:
        logger.info("Creating bot application...")
        app_instance = Application.builder().token(BOT_TOKEN).build()
        setup_handlers(app_instance)
        await app_instance.initialize()
        
        webhook_url = f"{WEBAPP_URL}/webhook"
        await app_instance.bot.set_webhook(webhook_url)
        logger.info(f"✅ Bot setup complete. Webhook: {webhook_url}")
    
    logger.info("✅ Startup complete")
    
    yield
    
    logger.info("🛑 Shutting down...")
    if app_instance:
        await app_instance.bot.delete_webhook()
        await app_instance.shutdown()

app = FastAPI(lifespan=lifespan)

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
        
        if app_instance is None:
            return JSONResponse({"status": "error", "message": "Bot not initialized"}, status_code=500)
        
        update = Update.de_json(data, app_instance.bot)
        await app_instance.process_update(update)
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
        <body><h1>🍽️ FoodTracker</h1><p>Відкрийте Telegram та надішліть /start</p></body>
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
        <body><h1>⚙️ Налаштування</h1><p>Будь ласка, оновіть додаток</p></body>
        </html>
        """)

# ============================================
# API ENDPOINTS
# ============================================

@app.get("/api/user/{telegram_id}")
async def get_user(telegram_id: int):
    """Отримати дані користувача"""
    try:
        profile = get_user_profile(telegram_id)
        if profile:
            return JSONResponse(profile)
        return JSONResponse({"error": "User not found"}, status_code=404)
    except Exception as e:
        logger.error(f"Error getting user: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)

@app.post("/api/user/{telegram_id}")
async def update_user(telegram_id: int, profile: dict):
    """Оновити профіль користувача"""
    try:
        age = profile.get("age", 25)
        if age:
            age = int(age)
        
        height = profile.get("height", 170)
        if height:
            height = int(height)
        
        weight = profile.get("weight", 70)
        if weight:
            weight = float(weight)
        
        profile_data = {
            "age": age,
            "gender": profile.get("gender", "male"),
            "height": height,
            "weight": weight,
            "activity_level": profile.get("activity_level", "moderate"),
            "goal": profile.get("goal", "maintain"),
        }
        
        daily_calories = nutrition_calculator.calculate_tdee(profile_data)
        
        user_data = {
            "age": age,
            "gender": profile.get("gender"),
            "height": height,
            "weight": weight,
            "activity_level": profile.get("activity_level"),
            "goal": profile.get("goal"),
            "daily_calorie_goal": daily_calories,
            "updated_at": datetime.utcnow().isoformat()
        }
        
        result = save_user_profile(telegram_id, user_data)
        return JSONResponse(result or {})
    except Exception as e:
        logger.error(f"Error updating user: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)

@app.get("/api/meals/{telegram_id}")
async def get_meals(telegram_id: int):
    """Отримати прийоми їжі"""
    try:
        meals = get_today_meals(telegram_id)
        return JSONResponse(meals)
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
        telegram_id = meal.get("telegram_id")
        logger.info(f"📝 API: Saving meal for user {telegram_id}")
        
        if not telegram_id:
            return JSONResponse({"error": "telegram_id required"}, status_code=400)
        
        meal_data = {
            "name": meal.get("name", "Невідомо"),
            "calories": meal.get("calories", 0),
            "protein": meal.get("protein", 0),
            "fat": meal.get("fat", 0),
            "carbs": meal.get("carbs", 0),
            "feedback": meal.get("feedback", ""),
            "created_at": datetime.utcnow().isoformat()
        }
        
        result = save_meal(telegram_id, meal_data)
        
        if result:
            logger.info(f"✅ Meal saved for user {telegram_id}")
            return JSONResponse(result)
        else:
            return JSONResponse({"error": "Failed to save meal"}, status_code=500)
            
    except Exception as e:
        logger.error(f"❌ Error creating meal: {e}", exc_info=True)
        return JSONResponse({"error": str(e)}, status_code=500)

@app.get("/api/supplements/{telegram_id}")
async def get_supplements_endpoint(telegram_id: int):
    """Отримати вітаміни/добавки"""
    try:
        supplements = get_supplements(telegram_id)
        return JSONResponse(supplements)
    except Exception as e:
        logger.error(f"Error getting supplements: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)

@app.post("/api/supplements")
async def create_supplement(supplement: dict):
    """Зберегти вітамін/добавку"""
    try:
        telegram_id = supplement.get("telegram_id")
        supplement_data = {
            "name": supplement.get("name"),
            "created_at": datetime.utcnow().isoformat()
        }
        result = save_supplement(telegram_id, supplement_data)
        return JSONResponse(result or {})
    except Exception as e:
        logger.error(f"Error saving supplement: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)

@app.get("/api/water/{telegram_id}")
async def get_water_endpoint(telegram_id: int):
    """Отримати кількість води"""
    try:
        total = get_water(telegram_id)
        return JSONResponse({"total": total})
    except Exception as e:
        logger.error(f"Error getting water: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)

@app.post("/api/water/{telegram_id}")
async def save_water_endpoint(telegram_id: int, data: dict):
    """Зберегти кількість води"""
    try:
        amount = data.get("amount", 0)
        total = save_water(telegram_id, amount)
        return JSONResponse({"total": total})
    except Exception as e:
        logger.error(f"Error saving water: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)

@app.get("/api/notifications/{telegram_id}")
async def get_notifications_endpoint(telegram_id: int):
    """Отримати налаштування нагадувань"""
    try:
        times = get_notifications(telegram_id)
        return JSONResponse({"times": times})
    except Exception as e:
        logger.error(f"Error getting notifications: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)

@app.post("/api/notifications/{telegram_id}")
async def set_notifications_endpoint(telegram_id: int, data: dict):
    """Встановити час нагадувань"""
    try:
        times = data.get("times", [])
        result = save_notifications(telegram_id, times)
        return JSONResponse({"status": "success" if result else "error", "times": times})
    except Exception as e:
        logger.error(f"Error setting notifications: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)

@app.get("/api/daily-summary/{telegram_id}")
async def get_daily_summary(telegram_id: int):
    """Отримати денну статистику"""
    try:
        meals = get_today_meals(telegram_id)
        user_profile = get_user_profile(telegram_id)
        
        if not user_profile:
            return JSONResponse({"error": "User profile not found"}, status_code=404)
        
        total_calories = sum(m.get("calories", 0) for m in meals)
        goal_calories = user_profile.get("daily_calorie_goal", 2000)
        
        return JSONResponse({
            "total": {"calories": total_calories},
            "goal": {"calories": goal_calories, "remaining": max(0, goal_calories - total_calories)},
            "progress": min((total_calories / goal_calories) * 100, 100) if goal_calories > 0 else 0,
            "meals_count": len(meals)
        })
    except Exception as e:
        logger.error(f"Error getting daily summary: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)

@app.get("/api/weekly-report/{telegram_id}")
async def get_weekly_report(telegram_id: int):
    """Отримати тижневий звіт з AI-аналізом"""
    try:
        meals = get_weekly_meals(telegram_id)
        
        if not meals:
            return JSONResponse({"error": "No meals found for the last week"}, status_code=404)
        
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
        
        user_profile = get_user_profile(telegram_id)
        
        ai_analysis = "📊 *Тижневий звіт*\n\n"
        
        if gemini_service:
            try:
                ai_analysis = await gemini_service.analyze_weekly(meals, avg_per_day, user_profile)
            except Exception as e:
                logger.error(f"Gemini weekly analysis error: {e}")
                ai_analysis = "⚠️ Не вдалося згенерувати AI-аналіз. Спробуйте пізніше."
        
        return JSONResponse({
            "total": {"calories": total_calories, "protein": total_protein, "fat": total_fat, "carbs": total_carbs},
            "average_per_day": avg_per_day,
            "meals_count": len(meals),
            "ai_analysis": ai_analysis
        })
    except Exception as e:
        logger.error(f"Error getting weekly report: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)

@app.get("/test-db")
async def test_db():
    """Тест стану бази даних"""
    return JSONResponse({
        "status": "connected",
        "mode": "in-memory",
        "stats": {
            "users": len(_memory_db["users"]),
            "meals": sum(len(m) for m in _memory_db["meals"].values()),
            "supplements": sum(len(s) for s in _memory_db["supplements"].values()),
            "water": sum(_memory_db["water"].values()),
            "notifications": sum(len(n) for n in _memory_db["notifications"].values())
        }
    })

@app.get("/health")
async def health():
    """Перевірка стану сервісу"""
    return JSONResponse({
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "mode": "in-memory",
        "gemini": "initialized" if gemini_service else "failed",
        "bot": "ready" if app_instance else "initializing"
    })

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
