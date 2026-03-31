import os
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Form, UploadFile, File
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv
from datetime import datetime, timedelta
from typing import Optional, List
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Імпорт наших модулів
from bot.handlers import get_application, setup_handlers
from services.supabase_client import supabase, init_supabase
from services.gemini import GeminiService
from services.nutrition import NutritionCalculator
from models.schemas import UserProfile

gemini_service = GeminiService()
nutrition_calculator = NutritionCalculator()
scheduler = AsyncIOScheduler()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
webapp_dir = os.path.join(BASE_DIR, "webapp")
static_dir = os.path.join(webapp_dir, "static")
os.makedirs(webapp_dir, exist_ok=True)
os.makedirs(static_dir, exist_ok=True)

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting bot application...")
    
    init_supabase()
    
    try:
        bot = get_application()
        setup_handlers(bot)
        
        webhook_url = f"{os.getenv('WEBAPP_URL')}/webhook"
        await bot.bot.set_webhook(webhook_url)
        logger.info(f"Webhook set to {webhook_url}")
    except Exception as e:
        logger.error(f"Failed to setup bot: {e}")
    
    scheduler.add_job(
        check_notifications,
        CronTrigger(minute="*/5"),
        id="notifications",
        replace_existing=True
    )
    scheduler.start()
    logger.info("Scheduler started")
    
    yield
    
    logger.info("Shutting down...")
    scheduler.shutdown()
    try:
        bot = get_application()
        await bot.bot.delete_webhook()
    except Exception as e:
        logger.error(f"Error during shutdown: {e}")

app = FastAPI(lifespan=lifespan)
app.mount("/static", StaticFiles(directory=static_dir), name="static")

# ... (решта API ендпоінтів залишається без змін, як у попередній версії main.py)
