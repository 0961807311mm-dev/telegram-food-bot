# ============================================
# Файл: main.py (повністю виправлений для Docker)
# ============================================
import os
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Form, UploadFile, File
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv
import json
from datetime import datetime, timedelta
from typing import Optional, List
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

# Імпорт наших модулів
from bot.handlers import get_application, setup_handlers
from services.supabase_client import supabase, init_supabase
from services.gemini import GeminiService
from services.nutrition import NutritionCalculator
from models.schemas import UserProfile

load_dotenv()

# Налаштування логування
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Ініціалізація сервісів
gemini_service = GeminiService()
nutrition_calculator = NutritionCalculator()

# Scheduler для нагадувань
scheduler = AsyncIOScheduler()

# WebApp директорія
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
webapp_dir = os.path.join(BASE_DIR, "webapp")
static_dir = os.path.join(webapp_dir, "static")

# Створюємо директорії якщо їх немає
os.makedirs(webapp_dir, exist_ok=True)
os.makedirs(static_dir, exist_ok=True)

# Lifespan менеджер
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Управління життєвим циклом додатку"""
    # Запуск при старті
    logger.info("Starting bot application...")
    
    # Ініціалізація Supabase
    init_supabase()
    
    # Отримуємо бота та налаштовуємо обробники
    try:
        bot = get_application()
        setup_handlers(bot)
        
        # Налаштування вебхука
        webhook_url = f"{os.getenv('WEBAPP_URL')}/webhook"
        await bot.bot.set_webhook(webhook_url)
        logger.info(f"Webhook set to {webhook_url}")
    except Exception as e:
        logger.error(f"Failed to setup bot: {e}")
    
    # Запуск шедулера для нагадувань
    scheduler.add_job(
        check_notifications,
        CronTrigger(minute="*/5"),  # Кожні 5 хвилин
        id="notifications",
        replace_existing=True
    )
    scheduler.start()
    logger.info("Scheduler started")
    
    yield
    
    # Закриття при зупинці
    logger.info("Shutting down...")
    scheduler.shutdown()
    try:
        bot = get_application()
        await bot.bot.delete_webhook()
        logger.info("Webhook deleted")
    except Exception as e:
        logger.error(f"Error during shutdown: {e}")

# Створення FastAPI додатку
app = FastAPI(lifespan=lifespan, title="FoodTracker Bot", version="1.0.0")

# Монтуємо статичні файли
app.mount("/static", StaticFiles(directory=static_dir), name="static")

# ============================================
# TELEGRAM WEBHOOK
# ============================================
@app.post("/webhook")
async def webhook(request: Request):
    """Обробка вебхуків від Telegram"""
    try:
        update_data = await request.json()
        bot = get_application()
        await bot.process_update(update_data)
        return JSONResponse({"status": "ok"})
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)

# ============================================
# WEBAPP СТОРІНКИ
# ============================================
@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """Головний дашборд"""
    try:
        index_path = os.path.join(webapp_dir, "index.html")
        if not os.path.exists(index_path):
            logger.error(f"index.html not found at {index_path}")
            return HTMLResponse(content="<h1>Error: index.html not found</h1>", status_code=404)
        
        with open(index_path, "r", encoding="utf-8") as f:
            html = f.read()
        return HTMLResponse(content=html)
    except Exception as e:
        logger.error(f"Error serving index: {e}")
        return HTMLResponse(content=f"<h1>Error: {e}</h1>", status_code=500)

@app.get("/add-meal", response_class=HTMLResponse)
async def add_meal_page(request: Request):
    """Сторінка додавання їжі"""
    try:
        add_meal_path = os.path.join(webapp_dir, "add_meal.html")
        if not os.path.exists(add_meal_path):
            logger.error(f"add_meal.html not found at {add_meal_path}")
            return HTMLResponse(content="<h1>Error: add_meal.html not found</h1>", status_code=404)
        
        with open(add_meal_path, "r", encoding="utf-8") as f:
            html = f.read()
        return HTMLResponse(content=html)
    except Exception as e:
        logger.error(f"Error serving add-meal: {e}")
        return HTMLResponse(content=f"<h1>Error: {e}</h1>", status_code=500)

@app.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request):
    """Сторінка налаштувань"""
    try:
        settings_path = os.path.join(webapp_dir, "settings.html")
        if not os.path.exists(settings_path):
            logger.error(f"settings.html not found at {settings_path}")
            return HTMLResponse(content="<h1>Error: settings.html not found</h1>", status_code=404)
        
        with open(settings_path, "r", encoding="utf-8") as f:
            html = f.read()
        return HTMLResponse(content=html)
    except Exception as e:
        logger.error(f"Error serving settings: {e}")
        return HTMLResponse(content=f"<h1>Error: {e}</h1>", status_code=500)

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
        
        # Розрахувати норму калорій
        user_profile = UserProfile(**profile)
        daily_calories = nutrition_calculator.calculate_tdee({
            "age": user_profile.age,
            "gender": user_profile.gender,
            "height": user_profile.height,
            "weight": user_profile.weight,
            "activity_level": user_profile.activity_level,
            "goal": user_profile.goal
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
        
        # Конвертуємо дату в діапазон
        start_date = f"{date}T00:00:00"
        end_date = f"{date}T23:59:59"
        
        response = supabase.table("meals").select("*").eq("telegram_id", telegram_id).gte("created_at", start_date).lte("created_at", end_date).execute()
        
        return JSONResponse(response.data)
    except Exception as e:
        logger.error(f"Error getting meals: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)

@app.post("/api/analyze")
async def analyze_meal(telegram_id: int = Form(...), photo: UploadFile = File(...)):
    """Аналіз фото їжі через Gemini"""
    try:
        # Читаємо фото
        photo_bytes = await photo.read()
        
        # Аналізуємо через Gemini
        analysis = await gemini_service.analyze_meal(photo_bytes, photo.filename)
        
        return JSONResponse(analysis)
    except Exception as e:
        logger.error(f"Error analyzing meal: {e}")
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
    """Отримати тижневий звіт"""
    try:
        if supabase is None:
            return JSONResponse({"error": "Database not initialized"}, status_code=500)
        
        # Отримуємо дані за останні 7 днів
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
        
        # Отримуємо профіль користувача для норм
        user_response = supabase.table("users").select("*").eq("telegram_id", telegram_id).execute()
        user_profile = user_response.data[0] if user_response.data else None
        
        # Генеруємо AI аналіз
        ai_analysis = await gemini_service.analyze_weekly(meals, avg_per_day, user_profile)
        
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
        
        # Видаляємо старі нагадування
        supabase.table("notifications").delete().eq("telegram_id", telegram_id).execute()
        
        # Додаємо нові
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
# ФОНОВІ ЗАДАЧІ
# ============================================
async def check_notifications():
    """Перевірка та відправка нагадувань"""
    try:
        if supabase is None:
            logger.warning("Supabase not initialized, skipping notifications")
            return
        
        current_time = datetime.utcnow().strftime("%H:%M")
        
        # Знаходимо всі активні нагадування на цей час
        response = supabase.table("notifications").select("*").eq("notification_time", current_time).eq("is_active", True).execute()
        
        if not response.data:
            return
        
        bot = get_application()
        for notification in response.data:
            telegram_id = notification.get("telegram_id")
            
            try:
                # Відправляємо повідомлення
                await bot.bot.send_message(
                    chat_id=telegram_id,
                    text="🍽️ *Час прийому їжі!*\n\nНе забудьте додати свій прийом їжі до щоденника харчування.",
                    parse_mode="Markdown"
                )
                logger.info(f"Notification sent to {telegram_id} at {current_time}")
            except Exception as e:
                logger.error(f"Failed to send notification to {telegram_id}: {e}")
    except Exception as e:
        logger.error(f"Error checking notifications: {e}")

# ============================================
# HEALTH CHECK
# ============================================
@app.get("/health")
@app.get("/health-check")
async def health_check():
    """Перевірка стану бота"""
    return JSONResponse({
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "supabase": "connected" if supabase else "disconnected",
        "python_version": "3.11"
    })

# ============================================
# ROOT ENDPOINT INFO
# ============================================
@app.get("/info")
async def info():
    """Інформація про сервіс"""
    return JSONResponse({
        "name": "FoodTracker Bot",
        "version": "1.0.0",
        "description": "Telegram food tracker bot with Gemini AI",
        "endpoints": [
            "/ - WebApp Dashboard",
            "/webhook - Telegram Webhook",
            "/health - Health Check",
            "/api/* - API Endpoints"
        ]
    })

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
