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
    
    logger.info(f"SUPABASE_URL: {url}")
    logger.info(f"SUPABASE_KEY present: {bool(key)}")
    
    if not url or not key:
        logger.error("SUPABASE_URL or SUPABASE_KEY not set!")
        return None
    
    try:
        # Спрощене створення клієнта
        supabase = create_client(url, key)
        
        # Перевіряємо з'єднання простим запитом
        try:
            # Спробуємо отримати список таблиць
            result = supabase.table("users").select("*").limit(1).execute()
            logger.info(f"✅ Supabase connection test successful")
        except Exception as e:
            # Можливо таблиці ще немає, але з'єднання працює
            logger.info(f"⚠️ Supabase connected, but users table may not exist: {e}")
        
        logger.info("✅ Supabase client initialized successfully")
        
    except Exception as e:
        logger.error(f"❌ Supabase connection error: {e}")
        logger.error("Check SUPABASE_URL and SUPABASE_KEY")
        supabase = None
    
    return supabase

def save_user_profile(telegram_id: int, profile: dict):
    """Зберегти профіль користувача"""
    try:
        if supabase is None:
            logger.error("Supabase not initialized")
            return None
        
        logger.info(f"📝 Saving profile for user {telegram_id}")
        
        # Перевіряємо чи існує користувач
        existing = supabase.table("users").select("*").eq("telegram_id", telegram_id).execute()
        
        if existing.data:
            response = supabase.table("users").update(profile).eq("telegram_id", telegram_id).execute()
        else:
            profile["telegram_id"] = telegram_id
            response = supabase.table("users").insert(profile).execute()
        
        logger.info(f"✅ Profile saved for {telegram_id}")
        return response.data[0] if response.data else None
        
    except Exception as e:
        logger.error(f"❌ Error saving user profile: {e}")
        return None

def get_user_profile(telegram_id: int):
    """Отримати профіль користувача"""
    try:
        if supabase is None:
            logger.error("Supabase not initialized")
            return None
        
        response = supabase.table("users").select("*").eq("telegram_id", telegram_id).execute()
        return response.data[0] if response.data else None
        
    except Exception as e:
        logger.error(f"❌ Error getting user profile: {e}")
        return None

def save_meal(telegram_id: int, meal_data: dict):
    """Зберегти прийом їжі"""
    try:
        if supabase is None:
            logger.error("Supabase not initialized")
            return None
        
        meal_data["telegram_id"] = telegram_id
        response = supabase.table("meals").insert(meal_data).execute()
        
        return response.data[0] if response.data else None
        
    except Exception as e:
        logger.error(f"❌ Error saving meal: {e}")
        return None

def get_today_meals(telegram_id: int):
    """Отримати прийоми їжі за сьогодні"""
    try:
        if supabase is None:
            return []
        
        from datetime import datetime
        today = datetime.now().date().isoformat()
        start = f"{today}T00:00:00"
        end = f"{today}T23:59:59"
        
        response = supabase.table("meals").select("*").eq("telegram_id", telegram_id).gte("created_at", start).lte("created_at", end).order("created_at", desc=True).execute()
        return response.data
        
    except Exception as e:
        logger.error(f"❌ Error getting today's meals: {e}")
        return []

def get_weekly_meals(telegram_id: int):
    """Отримати прийоми за тиждень"""
    try:
        if supabase is None:
            return []
        
        from datetime import datetime, timedelta
        week_ago = (datetime.now() - timedelta(days=7)).isoformat()
        
        response = supabase.table("meals").select("*").eq("telegram_id", telegram_id).gte("created_at", week_ago).order("created_at", desc=True).execute()
        return response.data
        
    except Exception as e:
        logger.error(f"❌ Error getting weekly meals: {e}")
        return []

def save_notifications(telegram_id: int, times: list):
    """Зберегти налаштування нагадувань"""
    try:
        if supabase is None:
            return False
        
        # Видаляємо старі
        supabase.table("notifications").delete().eq("telegram_id", telegram_id).execute()
        
        # Додаємо нові
        for time_str in times:
            data = {
                "telegram_id": telegram_id,
                "notification_time": time_str,
                "is_active": True
            }
            supabase.table("notifications").insert(data).execute()
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Error saving notifications: {e}")
        return False

def get_notifications(telegram_id: int):
    """Отримати налаштування нагадувань"""
    try:
        if supabase is None:
            return []
        
        response = supabase.table("notifications").select("*").eq("telegram_id", telegram_id).eq("is_active", True).execute()
        return [n.get("notification_time") for n in response.data]
        
    except Exception as e:
        logger.error(f"❌ Error getting notifications: {e}")
        return []
