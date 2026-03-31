# ============================================
# Файл: services/nutrition.py
# ============================================
from typing import Dict, Any

class NutritionCalculator:
    """Розрахунок норм харчування"""
    
    def __init__(self):
        pass
    
    def calculate_tdee(self, profile: Dict[str, Any]) -> float:
        """Розрахунок денної норми калорій (TDEE)"""
        age = profile.get("age", 25)
        gender = profile.get("gender", "male")
        height = profile.get("height", 170)
        weight = profile.get("weight", 70)
        activity_level = profile.get("activity_level", "moderate")
        goal = profile.get("goal", "maintain")
        
        # Розрахунок BMR (базальний метаболізм)
        if gender == "male":
            bmr = 10 * weight + 6.25 * height - 5 * age + 5
        else:
            bmr = 10 * weight + 6.25 * height - 5 * age - 161
        
        # Коефіцієнт активності
        activity_multipliers = {
            "sedentary": 1.2,      # Сидячий спосіб життя
            "light": 1.375,        # Легка активність 1-3 рази на тиждень
            "moderate": 1.55,      # Помірна активність 3-5 разів на тиждень
            "active": 1.725,       # Висока активність 6-7 разів на тиждень
            "very_active": 1.9     # Дуже висока активність (фізична робота)
        }
        
        tdee = bmr * activity_multipliers.get(activity_level, 1.55)
        
        # Коригування залежно від цілі
        goal_multipliers = {
            "lose": 0.85,      # Дефіцит 15% для схуднення
            "maintain": 1.0,    # Підтримка ваги
            "gain": 1.15       # Профіцит 15% для набору маси
        }
        
        daily_calories = tdee * goal_multipliers.get(goal, 1.0)
        
        return round(daily_calories, 0)
    
    def calculate_macros(self, calories: float, weight: float, goal: str) -> Dict[str, float]:
        """Розрахунок БЖУ"""
        # Білок: 1.6-2.2 г на кг ваги залежно від цілі
        if goal == "gain":
            protein_per_kg = 2.0
        elif goal == "lose":
            protein_per_kg = 2.2
        else:
            protein_per_kg = 1.8
        
        protein_grams = weight * protein_per_kg
        protein_calories = protein_grams * 4
        
        # Жири: 25-30% від загальної калорійності
        fat_percent = 0.28
        fat_calories = calories * fat_percent
        fat_grams = fat_calories / 9
        
        # Вуглеводи: залишок
        carbs_calories = calories - protein_calories - fat_calories
        carbs_grams = carbs_calories / 4
        
        return {
            "protein": round(protein_grams, 1),
            "fat": round(fat_grams, 1),
            "carbs": round(carbs_grams, 1)
        }
