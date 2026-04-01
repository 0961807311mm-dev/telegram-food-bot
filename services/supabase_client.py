# ============================================
# Файл: services/supabase_client.py (ПОВНИЙ З ЛОГУВАННЯМ)
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
    
    logger.info(f"SUPABASE_URL: {url}")
    logger.info(f"SUPABASE_KEY present: {bool(key)}")
    
    if not url or not key:
        logger.error("SUPABASE_URL or SUPABASE_KEY not set!")
        return None
    
    try:
        supabase = create_client(url, key)
        # Перевіряємо з'єднання
        test = supabase.table("users").select("*").limit(1).execute()
        logger.info(f"✅ Supabase connection test successful: {test.data}")
        logger.info("✅ Supabase client initialized successfully")
    except Exception as e:
        logger.error(f"❌ Supabase connection error: {e}")
        logger.error("Check that SUPABASE_KEY is the ANON/PUBLIC key, not SERVICE_ROLE")
        supabase = None
    
    return supabase

def save_user_profile(telegram_id: int, profile: dict):
    """Зберегти профіль користувача"""
    try:
        if supabase is None:
            logger.error("Supabase not initialized")
            return None
        
        logger.info(f"📝 Saving profile for user {telegram_id}")
        logger.info(f"Profile data: {profile}")
        
        # Перевіряємо чи існує користувач
        existing = supabase.table("users").select("*").eq("telegram_id", telegram_id).execute()
        logger.info(f"Existing user query result: {existing.data}")
        
        if existing.data:
            logger.info(f"Updating existing user {telegram_id}")
            response = supabase.table("users").update(profile).eq("telegram_id", telegram_id).execute()
            logger.info(f"Update response: {response.data}")
        else:
            logger.info(f"Creating new user {telegram_id}")
            profile["telegram_id"] = telegram_id
            response = supabase.table("users").insert(profile).execute()
            logger.info(f"Insert response: {response.data}")
        
        if response.data:
            logger.info(f"✅ Profile saved successfully for {telegram_id}")
            return response.data[0]
        else:
            logger.error(f"❌ No data returned from Supabase")
            return None
            
    except Exception as e:
        logger.error(f"❌ Error saving user profile: {e}", exc_info=True)
        return None

def get_user_profile(telegram_id: int):
    """Отримати профіль користувача"""
    try:
        if supabase is None:
            logger.error("Supabase not initialized")
            return None
        
        logger.info(f"🔍 Fetching profile for user {telegram_id}")
        response = supabase.table("users").select("*").eq("telegram_id", telegram_id).execute()
        logger.info(f"Profile query result: {response.data}")
        
        if response.data:
            logger.info(f"✅ Profile found for {telegram_id}")
            return response.data[0]
        else:
            logger.info(f"ℹ️ No profile found for {telegram_id}")
            return None
            
    except Exception as e:
        logger.error(f"❌ Error getting user profile: {e}", exc_info=True)
        return None

def save_meal(telegram_id: int, meal_data: dict):
    """Зберегти прийом їжі"""
    try:
        if supabase is None:
            logger.error("Supabase not initialized")
            return None
        
        logger.info(f"📝 Saving meal for user {telegram_id}")
        logger.info(f"Meal data: {meal_data}")
        
        meal_data["telegram_id"] = telegram_id
        response = supabase.table("meals").insert(meal_data).execute()
        logger.info(f"Insert response: {response.data}")
        
        if response.data:
            logger.info(f"✅ Meal saved successfully for {telegram_id}")
            return response.data[0]
        else:
            logger.error(f"❌ No data returned from Supabase")
            return None
            
    except Exception as e:
        logger.error(f"❌ Error saving meal: {e}", exc_info=True)
        return None

def get_today_meals(telegram_id: int):
    """Отримати прийоми їжі за сьогодні"""
    try:
        if supabase is None:
            logger.error("Supabase not initialized")
            return []
        
        from datetime import datetime
        today = datetime.now().date().isoformat()
        start = f"{today}T00:00:00"
        end = f"{today}T23:59:59"
        
        logger.info(f"🔍 Fetching today's meals for {telegram_id} ({start} - {end})")
        
        response = supabase.table("meals").select("*").eq("telegram_id", telegram_id).gte("created_at", start).lte("created_at", end).order("created_at", desc=True).execute()
        logger.info(f"Found {len(response.data)} meals today")
        
        return response.data
        
    except Exception as e:
        logger.error(f"❌ Error getting today's meals: {e}", exc_info=True)
        return []

def get_weekly_meals(telegram_id: int):
    """Отримати прийоми за тиждень"""
    try:
        if supabase is None:
            logger.error("Supabase not initialized")
            return []
        
        from datetime import datetime, timedelta
        week_ago = (datetime.now() - timedelta(days=7)).isoformat()
        
        logger.info(f"🔍 Fetching weekly meals for {telegram_id} (since {week_ago})")
        
        response = supabase.table("meals").select("*").eq("telegram_id", telegram_id).gte("created_at", week_ago).order("created_at", desc=True).execute()
        logger.info(f"Found {len(response.data)} meals in last week")
        
        return response.data
        
    except Exception as e:
        logger.error(f"❌ Error getting weekly meals: {e}", exc_info=True)
        return []

def save_notifications(telegram_id: int, times: list):
    """Зберегти налаштування нагадувань"""
    try:
        if supabase is None:
            logger.error("Supabase not initialized")
            return False
        
        logger.info(f"📝 Saving notifications for {telegram_id}: {times}")
        
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
        
        logger.info(f"✅ Notifications saved for {telegram_id}")
        return True
        
    except Exception as e:
        logger.error(f"❌ Error saving notifications: {e}", exc_info=True)
        return False

def get_notifications(telegram_id: int):
    """Отримати налаштування нагадувань"""
    try:
        if supabase is None:
            logger.error("Supabase not initialized")
            return []
        
        logger.info(f"🔍 Fetching notifications for {telegram_id}")
        
        response = supabase.table("notifications").select("*").eq("telegram_id", telegram_id).eq("is_active", True).execute()
        times = [n.get("notification_time") for n in response.data]
        
        logger.info(f"Found {len(times)} notifications: {times}")
        return times
        
    except Exception as e:
        logger.error(f"❌ Error getting notifications: {e}", exc_info=True)
        return []
