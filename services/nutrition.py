class NutritionCalculator:
    def calculate_tdee(self, profile: dict) -> float:
        age = profile.get("age", 25)
        gender = profile.get("gender", "male")
        height = profile.get("height", 170)
        weight = profile.get("weight", 70)
        activity_level = profile.get("activity_level", "moderate")
        goal = profile.get("goal", "maintain")
        
        if gender == "male":
            bmr = 10 * weight + 6.25 * height - 5 * age + 5
        else:
            bmr = 10 * weight + 6.25 * height - 5 * age - 161
        
        multipliers = {
            "sedentary": 1.2,
            "light": 1.375,
            "moderate": 1.55,
            "active": 1.725,
            "very_active": 1.9
        }
        
        tdee = bmr * multipliers.get(activity_level, 1.55)
        
        goal_multipliers = {
            "lose": 0.85,
            "maintain": 1.0,
            "gain": 1.15
        }
        
        return round(tdee * goal_multipliers.get(goal, 1.0), 0)
    
    def get_daily_summary(self, meals: list, user_profile: dict) -> dict:
        total_calories = sum(m.get("calories", 0) for m in meals)
        goal_calories = user_profile.get("daily_calorie_goal", 2000) if user_profile else 2000
        remaining = max(0, goal_calories - total_calories)
        progress = (total_calories / goal_calories) * 100 if goal_calories > 0 else 0
        
        return {
            "total": {"calories": total_calories},
            "goal": {"calories": goal_calories, "remaining": remaining},
            "progress": min(progress, 100),
            "meals_count": len(meals)
        }
