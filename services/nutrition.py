class NutritionCalculator:
    """Розрахунок норм харчування"""
    
    def calculate_tdee(self, profile: dict) -> float:
        """Розрахунок денної норми калорій (TDEE)"""
        age = profile.get("age", 25)
        gender = profile.get("gender", "male")
        height = profile.get("height", 170)
        weight = profile.get("weight", 70)
        activity_level = profile.get("activity_level", "moderate")
        goal = profile.get("goal", "maintain")
        
        # BMR (базальний метаболізм)
        if gender == "male":
            bmr = 10 * weight + 6.25 * height - 5 * age + 5
        else:
            bmr = 10 * weight + 6.25 * height - 5 * age - 161
        
        # Коефіцієнт активності
        multipliers = {
            "sedentary": 1.2,
            "light": 1.375,
            "moderate": 1.55,
            "active": 1.725,
            "very_active": 1.9
        }
        
        tdee = bmr * multipliers.get(activity_level, 1.55)
        
        # Коригування за ціллю
        goal_multipliers = {
            "lose": 0.85,
            "maintain": 1.0,
            "gain": 1.15
        }
        
        return round(tdee * goal_multipliers.get(goal, 1.0), 0)
    
    def calculate_macros(self, calories: float, weight: float, goal: str) -> dict:
        """Розрахунок БЖУ"""
        if goal == "gain":
            protein_ratio = 2.0
        elif goal == "lose":
            protein_ratio = 2.2
        else:
            protein_ratio = 1.8
        
        protein = round(weight * protein_ratio, 1)
        protein_cal = protein * 4
        
        fat = round((calories * 0.28) / 9, 1)
        fat_cal = fat * 9
        
        carbs = round((calories - protein_cal - fat_cal) / 4, 1)
        
        return {"protein": protein, "fat": fat, "carbs": carbs}
    
    def get_daily_summary(self, meals: list, user_profile: dict) -> dict:
        """Отримати денну статистику"""
        total_calories = sum(m.get("calories", 0) for m in meals)
        total_protein = sum(m.get("protein", 0) for m in meals)
        total_fat = sum(m.get("fat", 0) for m in meals)
        total_carbs = sum(m.get("carbs", 0) for m in meals)
        
        goal_calories = user_profile.get("daily_calorie_goal", 2000) if user_profile else 2000
        remaining = max(0, goal_calories - total_calories)
        progress = (total_calories / goal_calories) * 100 if goal_calories > 0 else 0
        
        return {
            "total": {
                "calories": total_calories,
                "protein": total_protein,
                "fat": total_fat,
                "carbs": total_carbs
            },
            "goal": {
                "calories": goal_calories,
                "remaining": remaining
            },
            "progress": min(progress, 100),
            "meals_count": len(meals)
        }
