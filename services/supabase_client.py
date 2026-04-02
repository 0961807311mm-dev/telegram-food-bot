import os
import logging
from typing import Optional, Dict, List
from datetime import datetime

logger = logging.getLogger(__name__)

# Тимчасове сховище в пам'яті (для тесту)
_memory_db = {
    "users": {},
    "meals": {},
    "notifications": {}
}

# Заглушка для supabase (щоб не було помилок імпорту)
supabase = None

def init_supabase():
    """Ініціалізація (тимчасово без реальної бази)"""
    logger.info("⚠️ Running in memory-only mode (no Supabase)")
    return None

def save_user_profile(telegram_id: int, profile: dict):
    """Зберегти профіль в пам'яті"""
    try:
        _memory_db["users"][telegram_id] = profile
        logger.info(f"✅ Profile saved in memory for {telegram_id}")
        return profile
    except Exception as e:
        logger.error(f"Error saving profile: {e}")
        return None

def get_user_profile(telegram_id: int):
    """Отримати профіль з пам'яті"""
    try:
        profile = _memory_db["users"].get(telegram_id)
        logger.info(f"🔍 Retrieved profile for {telegram_id}: {profile is not None}")
        return profile
    except Exception as e:
        logger.error(f"Error getting profile: {e}")
        return None

def save_meal(telegram_id: int, meal_data: dict):
    """Зберегти прийом в пам'яті"""
    try:
        if telegram_id not in _memory_db["meals"]:
            _memory_db["meals"][telegram_id] = []
        # Додаємо ID та час
        meal_data["id"] = len(_memory_db["meals"][telegram_id]) + 1
        meal_data["created_at"] = datetime.now().isoformat()
        _memory_db["meals"][telegram_id].append(meal_data)
        logger.info(f"✅ Meal saved in memory for {telegram_id}")
        return meal_data
    except Exception as e:
        logger.error(f"Error saving meal: {e}")
        return None

def get_today_meals(telegram_id: int):
    """Отримати прийоми з пам'яті"""
    try:
        meals = _memory_db["meals"].get(telegram_id, [])
        logger.info(f"📋 Retrieved {len(meals)} meals for {telegram_id}")
        return meals
    except Exception as e:
        logger.error(f"Error getting meals: {e}")
        return []

def get_weekly_meals(telegram_id: int):
    """Отримати прийоми за тиждень з пам'яті"""
    try:
        meals = _memory_db["meals"].get(telegram_id, [])
        # Фільтруємо за останні 7 днів
        week_ago = datetime.now().timestamp() - (7 * 24 * 3600)
        filtered = []
        for meal in meals:
            if meal.get("created_at"):
                try:
                    meal_time = datetime.fromisoformat(meal["created_at"]).timestamp()
                    if meal_time >= week_ago:
                        filtered.append(meal)
                except:
                    filtered.append(meal)
        logger.info(f"📋 Retrieved {len(filtered)} weekly meals for {telegram_id}")
        return filtered
    except Exception as e:
        logger.error(f"Error getting weekly meals: {e}")
        return []

def save_notifications(telegram_id: int, times: list):
    """Зберегти нагадування в пам'яті"""
    try:
        _memory_db["notifications"][telegram_id] = times
        logger.info(f"✅ Notifications saved in memory for {telegram_id}: {times}")
        return True
    except Exception as e:
        logger.error(f"Error saving notifications: {e}")
        return False

def get_notifications(telegram_id: int):
    """Отримати нагадування з пам'яті"""
    try:
        times = _memory_db["notifications"].get(telegram_id, [])
        logger.info(f"🔔 Retrieved {len(times)} notifications for {telegram_id}")
        return times
    except Exception as e:
        logger.error(f"Error getting notifications: {e}")
        return []
