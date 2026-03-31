import os
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Form, UploadFile, File, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv
import httpx
import json
from datetime import datetime, timedelta
from typing import Optional, List
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

# Імпорт наших модулів
from bot.handlers import get_bot, setup_handlers
from services.supabase_client import supabase, init_supabase
from services.gemini import GeminiService
from services.nutrition import NutritionCalculator
from models.schemas import UserProfile, MealCreate, MealResponse

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
if not os.path.exists(webapp_dir):
    os.makedirs(webapp_dir)
    
static_dir = os.path.join(webapp_dir, "static")
if not os.path.exists(static_dir):
    os.makedirs(static_dir)

# Lifespan менеджер
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Управління життєвим циклом додатку"""
    # Запуск при старті
    logger.info("Starting bot application...")
    
    # Ініціалізація Supabase
    init_supabase()
    
    # Отримуємо бота та налаштовуємо обробники
    bot = get_bot()
    setup_handlers(bot)
    
    # Налаштування вебхука
    webhook_url = f"{os.getenv('WEBAPP_URL')}/webhook"
    try:
        await bot.bot.set_webhook(webhook_url)
        logger.info(f"Webhook set to {webhook_url}")
    except Exception as e:
        logger.error(f"Failed to set webhook: {e}")
    
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
        await bot.bot.delete_webhook()
        logger.info("Webhook deleted")
    except Exception as e:
        logger.error(f"Error deleting webhook: {e}")

# Створення FastAPI додатку
app = FastAPI(lifespan=lifespan)

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
        bot = get_bot()
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
        with open(os.path.join(webapp_dir, "index.html"), "r", encoding="utf-8") as f:
            html = f.read()
        return HTMLResponse(content=html)
    except FileNotFoundError:
        logger.error("index.html not found")
        return HTMLResponse(content="<h1>Error: index.html not found</h1>", status_code=404)

@app.get("/add-meal", response_class=HTMLResponse)
async def add_meal_page(request: Request):
    """Сторінка додавання їжі"""
    try:
        with open(os.path.join(webapp_dir, "add_meal.html"), "r", encoding="utf-8") as f:
            html = f.read()
        return HTMLResponse(content=html)
    except FileNotFoundError:
        logger.error("add_meal.html not found")
        return HTMLResponse(content="<h1>Error: add_meal.html not found</h1>", status_code=404)

@app.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request):
    """Сторінка налаштувань"""
    try:
        with open(os.path.join(webapp_dir, "settings.html"), "r", encoding="utf-8") as f:
            html = f.read()
        return HTMLResponse(content=html)
    except FileNotFoundError:
        logger.error("settings.html not found")
        return HTMLResponse(content="<h1>Error: settings.html not found</h1>", status_code=404)

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
        daily_calories = nutrition_calculator.calculate_tdee(user_profile.dict())
        
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
        
        bot = get_bot()
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
async def health_check():
    """Перевірка стану бота"""
    return JSONResponse({
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "supabase": "connected" if supabase else "disconnected"
    })

# ============================================
# ROOT ENDPOINT
# ============================================
@app.get("/health-check")
async def health_check_root():
    """Альтернативний health check"""
    return {"status": "ok", "message": "Bot is running"}

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
