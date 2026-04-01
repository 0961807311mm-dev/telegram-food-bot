async def analyze_weekly(self, meals: list, averages: dict, user_profile: dict) -> str:
    """Аналіз тижневого харчування"""
    try:
        prompt = f"""
        Ти експерт-нутриціолог. Проаналізуй харчування за тиждень.
        
        Середні показники за день:
        - Калорії: {averages.get('calories', 0):.0f} ккал
        - Білки: {averages.get('protein', 0):.1f} г
        - Жири: {averages.get('fat', 0):.1f} г
        - Вуглеводи: {averages.get('carbs', 0):.1f} г
        """
        
        if user_profile:
            prompt += f"""
            
            Ваші дані:
            - Вік: {user_profile.get('age')}
            - Стать: {user_profile.get('gender')}
            - Вага: {user_profile.get('weight')} кг
            - Зріст: {user_profile.get('height')} см
            - Ціль: {user_profile.get('goal')}
            - Норма калорій: {user_profile.get('daily_calorie_goal')} ккал
            """
        
        prompt += """
        
        Напиши детальний аналіз українською мовою:
        1. Оцінка загального харчування
        2. Аналіз макронутрієнтів
        3. Яких мікроелементів може не вистачати
        4. 3 конкретні рекомендації на наступний тиждень
        
        Використовуй емодзі та дружній стиль.
        """
        
        response = await self._generate_content(prompt)
        return response
    except Exception as e:
        logger.error(f"Weekly analysis error: {e}")
        return "📊 Не вдалося згенерувати аналіз. Спробуйте пізніше."
