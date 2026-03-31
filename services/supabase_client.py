# ============================================
# Файл: services/supabase_client.py
# ============================================
import os
import logging
from supabase import create_client, Client

logger = logging.getLogger(__name__)

supabase: Client = None

def init_supabase():
    """Ініціалізація клієнта Supabase"""
    global supabase
    
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")
    
    if not url or not key:
        logger.error("SUPABASE_URL or SUPABASE_KEY not set")
        return None
    
    supabase = create_client(url, key)
    logger.info("Supabase client initialized")
    
    # Створюємо таблиці, якщо їх немає
    create_tables()
    
    return supabase

def create_tables():
    """Створення таблиць в Supabase (через raw SQL)"""
    try:
        # Таблиця users
        supabase.table("users").select("*").limit(1).execute()
        logger.info("Tables already exist")
    except Exception as e:
        logger.warning(f"Tables may not exist yet. Please create them in Supabase SQL editor:")
        logger.warning("""
        -- SQL для створення таблиць:
        
        CREATE TABLE IF NOT EXISTS users (
            id BIGSERIAL PRIMARY KEY,
            telegram_id BIGINT UNIQUE NOT NULL,
            age INTEGER,
            gender TEXT,
            height INTEGER,
            weight FLOAT,
            activity_level TEXT,
            goal TEXT,
            daily_calorie_goal FLOAT,
            created_at TIMESTAMP DEFAULT NOW(),
            updated_at TIMESTAMP DEFAULT NOW()
        );
        
        CREATE TABLE IF NOT EXISTS meals (
            id BIGSERIAL PRIMARY KEY,
            telegram_id BIGINT NOT NULL,
            photo_url TEXT,
            name TEXT NOT NULL,
            calories INTEGER,
            protein FLOAT,
            fat FLOAT,
            carbs FLOAT,
            feedback TEXT,
            created_at TIMESTAMP DEFAULT NOW()
        );
        
        CREATE TABLE IF NOT EXISTS notifications (
            id BIGSERIAL PRIMARY KEY,
            telegram_id BIGINT NOT NULL,
            notification_time TIME NOT NULL,
            is_active BOOLEAN DEFAULT true,
            created_at TIMESTAMP DEFAULT NOW()
        );
        
        CREATE INDEX idx_meals_telegram_id ON meals(telegram_id);
        CREATE INDEX idx_meals_created_at ON meals(created_at);
        CREATE INDEX idx_notifications_telegram_id ON notifications(telegram_id);
        CREATE INDEX idx_notifications_time ON notifications(notification_time);
        """)
