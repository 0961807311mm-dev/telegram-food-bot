import os
import logging
from typing import Optional, Dict, List

logger = logging.getLogger(__name__)

# Тимчасове сховище в пам'яті (для тесту)
_memory_db = {
    "users": {},
    "meals": {},
    "notifications": {}
}

supabase = None

def init_supabase():
    """Ініціалізація (тимчасово без реальної бази)"""
    logger.info("⚠️ Running in memory-only mode (no Supabase)")
    return None

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
    return _memory_db["meals"].get(telegram_id, [])

def save_notifications(telegram_id: int, times: list):
    """Зберегти нагадування в пам'яті"""
    _memory_db["notifications"][telegram_id] = times
    return True

def get_notifications(telegram_id: int):
    """Отримати нагадування з пам'яті"""
    return _memory_db["notifications"].get(telegram_id, [])
