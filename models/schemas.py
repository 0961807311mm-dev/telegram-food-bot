# ============================================
# Файл: models/schemas.py
# ============================================
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class UserProfile(BaseModel):
    age: int
    gender: str
    height: int
    weight: float
    activity_level: str
    goal: str  # lose, maintain, gain

class MealCreate(BaseModel):
    telegram_id: int
    photo_url: Optional[str] = None
    name: str
    calories: int
    protein: float
    fat: float
    carbs: float
    feedback: Optional[str] = None

class MealResponse(BaseModel):
    id: int
    telegram_id: int
    photo_url: Optional[str]
    name: str
    calories: int
    protein: float
    fat: float
    carbs: float
    feedback: Optional[str]
    created_at: datetime

class NotificationSettings(BaseModel):
    telegram_id: int
    times: list[str]  # ["09:00", "14:00", "19:00"]

class WeeklyReport(BaseModel):
    total_calories: int
    total_protein: float
    total_fat: float
    total_carbs: float
    meals_count: int
    ai_analysis: str
