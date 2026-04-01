# ============================================
# Файл: main.py (ПОВНИЙ З ЛОГУВАННЯМ)
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
from services.supabase_client import supabase, init_supabase, save_user_profile, get_user_profile, save_meal, get_today_meals, get_weekly_meals, save_notifications, get_notifications
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
    logger.info(f"📨 Start command from user {user.id}")
    
    # Перевіряємо чи є профіль
    profile = get_user_profile(user.id)
    
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
    
    if not profile:
        welcome_text = f"""
🍽️ *Вітаю, {user.first_name}!*

Я твій персональний AI-нутриціолог на базі *Gemini 2.5 Flash*.

*Щоб почати, налаштуй свій профіль:*
1️⃣ Натисни кнопку "Налаштування"
2️⃣ Введи свої параметри (вік, вага, зріст)
3️⃣ Обери ціль (схуднення/підтримка/набір)

Після налаштувань я розрахую твою норму калорій!
"""
    else:
        daily_goal = profile.get("daily_calorie_goal", 2000)
        welcome_text = f"""
🍽️ *Вітаю, {user.first_name}!*

Твоя денна норма: *{int(daily_goal)} ккал*

*Що я вмію:*
📸 Аналізувати фото їжі через AI
📊 Вести щоденник калорій
📈 Розраховувати норми БЖУ
💡 Давати персоналізовані рекомендації
⏰ Нагадувати про прийоми їжі
🤖 Аналізувати харчування за тиждень

*Почни з додавання першого прийому їжі!*
"""
    
    await update.message.reply_text(
        welcome_text,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=reply_markup
    )
    logger.info(f"✅ Reply sent to user {user.id}")

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
                <select id="activityLevel">
                    <option value="sedentary">Сидячий</option>
                    <option value="light">Легкий</option>
                    <option value="moderate">Помірний</option>
                    <option value="active">Високий</option>
                </select>
                <select id="goal">
                    <option value="lose">Схуднення</option>
                    <option value="maintain">Підтримка</option>
                    <option value="gain">Набір маси</option>
                </select>
                <button type="submit">Зберегти</button>
            </form>
            <script>
                const telegramId = new URLSearchParams(window.location.search).get('user_id');
                
                async function loadProfile() {
                    const response = await fetch(`/api/user/${telegramId}`);
                    const data = await response.json();
                    if (!data.error) {
                        document.getElementById('age').value = data.age || '';
                        document.getElementById('gender').value = data.gender || 'male';
                        document.getElementById('height').value = data.height || '';
                        document.getElementById('weight').value = data.weight || '';
                        document.getElementById('activityLevel').value = data.activity_level || 'moderate';
                        document.getElementById('goal').value = data.goal || 'maintain';
                    }
                }
                
                document.getElementById('profileForm').onsubmit = async (e) => {
                    e.preventDefault();
                    const profile = {
                        age: parseInt(document.getElementById('age').value),
                        gender: document.getElementById('gender').value,
                        height: parseInt(document.getElementById('height').value),
                        weight: parseFloat(document.getElementById('weight').value),
                        activity_level: document.getElementById('activityLevel').value,
                        goal: document.getElementById('goal').value
                    };
                    const response = await fetch(`/api/user/${telegramId}`, {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify(profile)
                    });
                    if (response.ok) {
                        alert('✅ Профіль збережено!');
                        window.location.href = `/?user_id=${telegramId}`;
                    } else {
                        const error = await response.json();
                        alert('❌ Помилка збереження: ' + (error.error || 'невідома помилка'));
                    }
                };
                
                if (telegramId) loadProfile();
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
        logger.info(f"🔍 API: Getting user {telegram_id}")
        
        if supabase is None:
            logger.error("Database not initialized")
            return JSONResponse({"error": "Database not initialized"}, status_code=500)
        
        profile = get_user_profile(telegram_id)
        if profile:
            logger.info(f"✅ User {telegram_id} found")
            return JSONResponse(profile)
        
        logger.info(f"ℹ️ User {telegram_id} not found")
        return JSONResponse({"error": "User not found"}, status_code=404)
        
    except Exception as e:
        logger.error(f"❌ Error getting user: {e}", exc_info=True)
        return JSONResponse({"error": str(e)}, status_code=500)

@app.post("/api/user/{telegram_id}")
async def update_user(telegram_id: int, profile: dict):
    """Оновити профіль користувача"""
    try:
        logger.info(f"📝 API: Updating user {telegram_id}")
        logger.info(f"Received profile data: {profile}")
        
        if supabase is None:
            logger.error("Database not initialized")
            return JSONResponse({"error": "Database not initialized"}, status_code=500)
        
        # Валідація та конвертація типів
        age = profile.get("age")
        if age is not None:
            age = int(age)
        
        height = profile.get("height")
        if height is not None:
            height = int(height)
        
        weight = profile.get("weight")
        if weight is not None:
            weight = float(weight)
        
        # Підготовка даних для розрахунку
        profile_data = {
            "age": age,
            "gender": profile.get("gender", "male"),
            "height": height,
            "weight": weight,
            "activity_level": profile.get("activity_level", "moderate"),
            "goal": profile.get("goal", "maintain"),
        }
        
        logger.info(f"Processed profile data for calculation: {profile_data}")
        
        # Розраховуємо норму калорій
        daily_calories = nutrition_calculator.calculate_tdee(profile_data)
        logger.info(f"Calculated daily calories: {daily_calories}")
        
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
        
        logger.info(f"Final user data to save: {user_data}")
        
        result = save_user_profile(telegram_id, user_data)
        
        if result:
            logger.info(f"✅ Profile saved successfully for {telegram_id}")
            return JSONResponse(result)
        else:
            logger.error(f"❌ Failed to save profile for {telegram_id}")
            return JSONResponse({"error": "Failed to save profile"}, status_code=500)
            
    except Exception as e:
        logger.error(f"❌ Error updating user: {e}", exc_info=True)
        return JSONResponse({"error": str(e)}, status_code=500)

@app.get("/api/meals/{telegram_id}")
async def get_meals(telegram_id: int, date: Optional[str] = None):
    """Отримати прийоми їжі за день"""
    try:
        logger.info(f"🔍 API: Getting meals for {telegram_id}")
        
        if supabase is None:
            return JSONResponse({"error": "Database not initialized"}, status_code=500)
        
        meals = get_today_meals(telegram_id)
        logger.info(f"Found {len(meals)} meals for {telegram_id}")
        return JSONResponse(meals)
        
    except Exception as e:
        logger.error(f"❌ Error getting meals: {e}", exc_info=True)
        return JSONResponse({"error": str(e)}, status_code=500)

@app.post("/api/analyze")
async def analyze_meal(photo: UploadFile = File(...)):
    """Аналіз фото їжі через Gemini"""
    try:
        logger.info(f"📸 API: Analyzing meal photo: {photo.filename}")
        
        if not gemini_service:
            logger.error("Gemini service not initialized")
            return JSONResponse({"error": "Gemini service not initialized"}, status_code=500)
        
        photo_bytes = await photo.read()
        logger.info(f"Photo size: {len(photo_bytes)} bytes")
        
        analysis = await gemini_service.analyze_meal(photo_bytes, photo.filename)
        logger.info(f"Analysis result: {analysis}")
        
        return JSONResponse(analysis)
        
    except Exception as e:
        logger.error(f"❌ Analysis error: {e}", exc_info=True)
        return JSONResponse({"error": str(e)}, status_code=500)

@app.post("/api/meals")
async def create_meal(meal: dict):
    """Зберегти прийом їжі"""
    try:
        telegram_id = meal.get("telegram_id")
        logger.info(f"📝 API: Saving meal for user {telegram_id}")
        logger.info(f"Meal data: {meal}")
        
        if supabase is None:
            return JSONResponse({"error": "Database not initialized"}, status_code=500)
        
        meal_data = {
            "photo_url": meal.get("photo_url"),
            "name": meal.get("name"),
            "calories": meal.get("calories"),
            "protein": meal.get("protein"),
            "fat": meal.get("fat"),
            "carbs": meal.get("carbs"),
            "feedback": meal.get("feedback"),
            "created_at": datetime.utcnow().isoformat()
        }
        
        result = save_meal(telegram_id, meal_data)
        
        if result:
            logger.info(f"✅ Meal saved for user {telegram_id}")
            return JSONResponse(result)
        else:
            logger.error(f"❌ Failed to save meal for {telegram_id}")
            return JSONResponse({"error": "Failed to save meal"}, status_code=500)
            
    except Exception as e:
        logger.error(f"❌ Error creating meal: {e}", exc_info=True)
        return JSONResponse({"error": str(e)}, status_code=500)

@app.get("/api/daily-summary/{telegram_id}")
async def get_daily_summary(telegram_id: int):
    """Отримати денну статистику"""
    try:
        logger.info(f"📊 API: Getting daily summary for {telegram_id}")
        
        if supabase is None:
            return JSONResponse({"error": "Database not initialized"}, status_code=500)
        
        meals = get_today_meals(telegram_id)
        user_profile = get_user_profile(telegram_id)
        
        if not user_profile:
            logger.info(f"No profile found for {telegram_id}")
            return JSONResponse({"error": "User profile not found"}, status_code=404)
        
        summary = nutrition_calculator.get_daily_summary(meals, user_profile)
        logger.info(f"Summary for {telegram_id}: {summary}")
        
        return JSONResponse(summary)
        
    except Exception as e:
        logger.error(f"❌ Error getting daily summary: {e}", exc_info=True)
        return JSONResponse({"error": str(e)}, status_code=500)

@app.get("/api/weekly-report/{telegram_id}")
async def get_weekly_report(telegram_id: int):
    """Отримати тижневий звіт з AI-аналізом"""
    try:
        logger.info(f"📊 API: Getting weekly report for {telegram_id}")
        
        if supabase is None:
            return JSONResponse({"error": "Database not initialized"}, status_code=500)
        
        meals = get_weekly_meals(telegram_id)
        
        if not meals:
            logger.info(f"No meals found for {telegram_id} in last week")
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
        
        user_profile = get_user_profile(telegram_id)
        
        ai_analysis = "📊 *Тижневий звіт*\n\n"
        
        if gemini_service:
            try:
                logger.info("Generating AI weekly analysis...")
                ai_analysis = await gemini_service.analyze_weekly(meals, avg_per_day, user_profile)
                logger.info("AI analysis generated")
            except Exception as e:
                logger.error(f"Gemini weekly analysis error: {e}")
                ai_analysis = "⚠️ Не вдалося згенерувати AI-аналіз. Спробуйте пізніше."
        
        result = {
            "total": {
                "calories": total_calories,
                "protein": total_protein,
                "fat": total_fat,
                "carbs": total_carbs
            },
            "average_per_day": avg_per_day,
            "meals_count": len(meals),
            "ai_analysis": ai_analysis
        }
        
        logger.info(f"Weekly report generated for {telegram_id}")
        return JSONResponse(result)
        
    except Exception as e:
        logger.error(f"❌ Error getting weekly report: {e}", exc_info=True)
        return JSONResponse({"error": str(e)}, status_code=500)

@app.post("/api/notifications/{telegram_id}")
async def set_notifications(telegram_id: int, times: List[str]):
    """Встановити час нагадувань"""
    try:
        logger.info(f"⏰ API: Setting notifications for {telegram_id}: {times}")
        
        if supabase is None:
            return JSONResponse({"error": "Database not initialized"}, status_code=500)
        
        result = save_notifications(telegram_id, times)
        
        if result:
            logger.info(f"✅ Notifications saved for {telegram_id}")
            return JSONResponse({"status": "success", "times": times})
        else:
            logger.error(f"❌ Failed to save notifications for {telegram_id}")
            return JSONResponse({"error": "Failed to save notifications"}, status_code=500)
            
    except Exception as e:
        logger.error(f"❌ Error setting notifications: {e}", exc_info=True)
        return JSONResponse({"error": str(e)}, status_code=500)

@app.get("/api/notifications/{telegram_id}")
async def get_notifications_endpoint(telegram_id: int):
    """Отримати налаштування нагадувань"""
    try:
        logger.info(f"🔍 API: Getting notifications for {telegram_id}")
        
        if supabase is None:
            return JSONResponse({"error": "Database not initialized"}, status_code=500)
        
        times = get_notifications(telegram_id)
        logger.info(f"Found {len(times)} notifications for {telegram_id}")
        
        return JSONResponse({"times": times})
        
    except Exception as e:
        logger.error(f"❌ Error getting notifications: {e}", exc_info=True)
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
