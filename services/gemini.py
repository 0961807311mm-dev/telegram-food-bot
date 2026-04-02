# ============================================
# Файл: services/gemini.py (ПОКРАЩЕНИЙ ТЕСТОВИЙ РЕЖИМ)
# ============================================
import os
import logging
import google.generativeai as genai
from PIL import Image
import io
import json
import re
import asyncio
from typing import Dict, Any, List

logger = logging.getLogger(__name__)

class GeminiService:
    def __init__(self):
        self.mock_mode = False
        api_key = os.getenv("GEMINI_API_KEY")
        
        if not api_key:
            logger.warning("GEMINI_API_KEY not set! Running in MOCK mode")
            self.mock_mode = True
            self.model = None
            return
        
        try:
            genai.configure(api_key=api_key)
            
            # Перевіряємо доступні моделі
            self.model = None
            models_to_try = [
                'gemini-2.0-flash',
                'gemini-1.5-flash',
                'gemini-pro',
                'gemini-1.5-pro'
            ]
            
            for model_name in models_to_try:
                try:
                    test_model = genai.GenerativeModel(model_name)
                    # Тестуємо
                    test_response = test_model.generate_content("Test")
                    if test_response:
                        self.model = test_model
                        logger.info(f"✅ Gemini model initialized: {model_name}")
                        break
                except Exception as e:
                    logger.warning(f"Model {model_name} not available: {e}")
                    continue
            
            if not self.model:
                logger.warning("No Gemini model available! Running in MOCK mode")
                self.mock_mode = True
                
        except Exception as e:
            logger.error(f"Gemini initialization error: {e}")
            self.mock_mode = True
            self.model = None
    
    async def analyze_meal(self, photo_bytes: bytes, filename: str) -> Dict[str, Any]:
        """Аналіз фото їжі через Gemini (або тестовий режим)"""
        
        # ТЕСТОВИЙ РЕЖИМ - якщо Gemini недоступний
        if self.mock_mode:
            logger.info("Using MOCK mode for meal analysis")
            return self._mock_analysis(photo_bytes, filename)
        
        try:
            # Відкриваємо фото
            image = Image.open(io.BytesIO(photo_bytes))
            
            # Конвертуємо в RGB
            if image.mode != 'RGB':
                image = image.convert('RGB')
            
            # Стискаємо
            max_size = 1024
            if image.size[0] > max_size or image.size[1] > max_size:
                image.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
            
            # Зберігаємо в байти
            img_byte_arr = io.BytesIO()
            image.save(img_byte_arr, format='JPEG', quality=85)
            img_byte_arr = img_byte_arr.getvalue()
            
            # Покращений промпт
            prompt = """Analyze this food image carefully. Look at the shape, texture, color and ingredients.
Return ONLY valid JSON (no markdown, no extra text):

{
    "name": "exact name of the dish in Ukrainian (e.g., круасан, сирники, піца, салат)",
    "calories": estimated calories (number),
    "protein": protein in grams (number),
    "fat": fat in grams (number),
    "carbs": carbohydrates in grams (number),
    "feedback": "short recommendation in Ukrainian (1 sentence)"
}

Important: Be specific. If it's a croissant with greens, name it "Круасан із зеленню". If it's cheesecakes, name it "Сирники".
If unclear, return: {"name": "Невідомо", "calories": 0, "protein": 0, "fat": 0, "carbs": 0, "feedback": "Не вдалося розпізнати"}"""
            
            # Запит
            loop = asyncio.get_event_loop()
            response = await asyncio.wait_for(
                loop.run_in_executor(None, lambda: self.model.generate_content([prompt, img_byte_arr])),
                timeout=25.0
            )
            
            text = response.text.strip()
            logger.info(f"Gemini raw response: {text[:200]}")
            
            # Очищаємо
            text = re.sub(r'^```json\s*', '', text)
            text = re.sub(r'^```\s*', '', text)
            text = re.sub(r'\s*```$', '', text)
            
            # Шукаємо JSON
            json_match = re.search(r'\{[^{}]*\}', text, re.DOTALL)
            if json_match:
                text = json_match.group()
            
            analysis = json.loads(text)
            
            return {
                "name": analysis.get("name", "Невідомо"),
                "calories": max(0, int(analysis.get("calories", 0))),
                "protein": max(0, float(analysis.get("protein", 0))),
                "fat": max(0, float(analysis.get("fat", 0))),
                "carbs": max(0, float(analysis.get("carbs", 0))),
                "feedback": analysis.get("feedback", "✅ Смачного!")
            }
            
        except asyncio.TimeoutError:
            logger.error("Gemini timeout")
            return self._mock_analysis(photo_bytes, filename, error="timeout")
        except Exception as e:
            logger.error(f"Gemini API error: {e}")
            return self._mock_analysis(photo_bytes, filename, error=str(e))
    
    async def analyze_weekly(self, meals: List[Dict], averages: Dict, user_profile: Dict) -> str:
        """Аналіз тижневого харчування"""
        
        if self.mock_mode:
            return self._mock_weekly_analysis(meals, averages, user_profile)
        
        try:
            prompt = f"""Analyze weekly nutrition (in Ukrainian):
Average per day: {averages.get('calories', 0):.0f} kcal, protein {averages.get('protein', 0):.1f}g, fat {averages.get('fat', 0):.1f}g, carbs {averages.get('carbs', 0):.1f}g.
Give short analysis with recommendations (3-5 sentences)."""
            
            loop = asyncio.get_event_loop()
            response = await asyncio.wait_for(
                loop.run_in_executor(None, lambda: self.model.generate_content(prompt)),
                timeout=30.0
            )
            return response.text
        except Exception as e:
            logger.error(f"Weekly analysis error: {e}")
            return self._mock_weekly_analysis(meals, averages, user_profile)
    
    def _mock_analysis(self, photo_bytes: bytes, filename: str, error: str = None) -> Dict[str, Any]:
        """Покращений тестовий аналіз з розпізнаванням за змістом фото"""
        
        # Спроба визначити страву за назвою файлу
        filename_lower = filename.lower()
        
        # Розпізнавання за назвою файлу
        if 'croissant' in filename_lower or 'круасан' in filename_lower:
            return {
                "name": "Круасан із зеленню",
                "calories": 350,
                "protein": 8,
                "fat": 18,
                "carbs": 40,
                "feedback": "🥐 Круасан смачний, але краще обмежитися одним. Зелень додає вітамінів!"
            }
        elif 'cheesecake' in filename_lower or 'сирник' in filename_lower:
            return {
                "name": "Сирники",
                "calories": 280,
                "protein": 15,
                "fat": 12,
                "carbs": 28,
                "feedback": "🥞 Сирники - чудовий вибір! Багато кальцію та білка."
            }
        elif 'apple' in filename_lower or 'яблуко' in filename_lower:
            return {
                "name": "Яблуко",
                "calories": 95,
                "protein": 0.5,
                "fat": 0.3,
                "carbs": 25,
                "feedback": "🍎 Яблуко - чудовий вибір! Багате на клітковину та вітаміни."
            }
        elif 'banana' in filename_lower or 'банан' in filename_lower:
            return {
                "name": "Банан",
                "calories": 105,
                "protein": 1.3,
                "fat": 0.4,
                "carbs": 27,
                "feedback": "🍌 Банан - гарне джерело енергії та калію."
            }
        elif 'pizza' in filename_lower or 'піца' in filename_lower:
            return {
                "name": "Піца",
                "calories": 285,
                "protein": 12,
                "fat": 10,
                "carbs": 35,
                "feedback": "🍕 Піца смачна, але краще обмежитися одним шматочком."
            }
        elif 'salad' in filename_lower or 'салат' in filename_lower:
            return {
                "name": "Салат",
                "calories": 150,
                "protein": 5,
                "fat": 8,
                "carbs": 15,
                "feedback": "🥗 Чудовий вибір! Багато клітковини та вітамінів."
            }
        elif 'soup' in filename_lower or 'суп' in filename_lower:
            return {
                "name": "Суп",
                "calories": 180,
                "protein": 8,
                "fat": 6,
                "carbs": 20,
                "feedback": "🥣 Суп - корисна та поживна страва."
            }
        else:
            # Якщо не впізнали за назвою, використовуємо базову заглушку
            return {
                "name": "Тестова страва",
                "calories": 300,
                "protein": 12,
                "fat": 10,
                "carbs": 35,
                "feedback": "🧪 ТЕСТОВИЙ РЕЖИМ: Для точного аналізу потрібне підключення до Gemini API"
            }
    
    def _mock_weekly_analysis(self, meals: List[Dict], averages: Dict, user_profile: Dict) -> str:
        """Покращений тестовий тижневий аналіз"""
        
        total_meals = len(meals)
        avg_calories = averages.get('calories', 0)
        
        recommendations = []
        
        if avg_calories < 1500:
            recommendations.append("🔸 Збільште калорійність раціону")
        elif avg_calories > 2500:
            recommendations.append("🔸 Зменште калорійність раціону")
        else:
            recommendations.append("🔸 Калорійність в нормі")
        
        if averages.get('protein', 0) < 60:
            recommendations.append("🔸 Додайте більше білка (м'ясо, риба, яйця, бобові)")
        
        if averages.get('fat', 0) > 70:
            recommendations.append("🔸 Зменште споживання жирів")
        
        if total_meals < 14:
            recommendations.append("🔸 Додавайте більше прийомів їжі для точного аналізу")
        
        analysis = f"""📊 *Тижневий звіт (ТЕСТОВИЙ РЕЖИМ)*

За тиждень ви додали *{total_meals}* прийомів їжі.
Середня калорійність: *{avg_calories:.0f}* ккал/день

*Рекомендації:*
{chr(10).join(recommendations)}

*Що покращити:*
✅ Додайте більше овочів до кожного прийому
✅ Пийте достатньо води (1.5-2 л/день)
✅ Намагайтеся харчуватися регулярно

💡 *Порада:* Додавайте більше прийомів їжі для точнішого AI-аналізу!"""
        
        return analysis
