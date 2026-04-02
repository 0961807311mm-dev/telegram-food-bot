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
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            logger.error("GEMINI_API_KEY not set!")
            raise ValueError("GEMINI_API_KEY not set")
        
        genai.configure(api_key=api_key)
        
        # Використовуємо правильну модель
        try:
            self.model = genai.GenerativeModel('gemini-1.5-flash')
            # Тестуємо модель
            test_response = self.model.generate_content("Test")
            logger.info("✅ Gemini 1.5 Flash initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Gemini: {e}")
            raise
    
    async def analyze_meal(self, photo_bytes: bytes, filename: str) -> Dict[str, Any]:
        """Аналіз фото їжі через Gemini"""
        try:
            # Відкриваємо фото
            image = Image.open(io.BytesIO(photo_bytes))
            
            # Конвертуємо в RGB
            if image.mode != 'RGB':
                image = image.convert('RGB')
            
            # Стискаємо для швидкості
            max_size = 1024
            if image.size[0] > max_size or image.size[1] > max_size:
                image.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
            
            # Промпт українською
            prompt = """Проаналізуй фото їжі. Відповідай ТІЛЬКИ в форматі JSON (без додаткового тексту):
{
    "name": "назва страви українською",
    "calories": число (калорії),
    "protein": число (білки в грамах),
    "fat": число (жири в грамах),
    "carbs": число (вуглеводи в грамах),
    "feedback": "коротка рекомендація українською (1 речення)"
}

Якщо не впізнаєш страву, поверни:
{
    "name": "Невідомо",
    "calories": 0,
    "protein": 0,
    "fat": 0,
    "carbs": 0,
    "feedback": "Не вдалося розпізнати страву. Спробуйте краще освітлення."
}"""
            
            # Запит до Gemini
            loop = asyncio.get_event_loop()
            response = await asyncio.wait_for(
                loop.run_in_executor(None, lambda: self.model.generate_content([prompt, image])),
                timeout=30.0
            )
            
            text = response.text.strip()
            logger.info(f"Gemini response: {text[:200]}")
            
            # Очищаємо від markdown
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
            return {
                "name": "Помилка",
                "calories": 0,
                "protein": 0,
                "fat": 0,
                "carbs": 0,
                "feedback": "⏰ Час очікування вичерпано. Спробуйте ще раз."
            }
        except json.JSONDecodeError as e:
            logger.error(f"JSON parse error: {e}")
            return {
                "name": "Помилка",
                "calories": 0,
                "protein": 0,
                "fat": 0,
                "carbs": 0,
                "feedback": "❌ Помилка аналізу. Спробуйте ще раз."
            }
        except Exception as e:
            logger.error(f"Gemini API error: {e}")
            return {
                "name": "Помилка",
                "calories": 0,
                "protein": 0,
                "fat": 0,
                "carbs": 0,
                "feedback": f"❌ Помилка: {str(e)[:50]}"
            }
    
    async def analyze_weekly(self, meals: List[Dict], averages: Dict, user_profile: Dict) -> str:
        """Аналіз тижневого харчування"""
        try:
            prompt = f"""Проаналізуй харчування за тиждень.
            
Середні показники за день:
- Калорії: {averages.get('calories', 0):.0f} ккал
- Білки: {averages.get('protein', 0):.1f} г
- Жири: {averages.get('fat', 0):.1f} г
- Вуглеводи: {averages.get('carbs', 0):.1f} г"""

            if user_profile:
                prompt += f"""
                
Дані користувача:
- Вік: {user_profile.get('age')}
- Стать: {user_profile.get('gender')}
- Вага: {user_profile.get('weight')} кг
- Ціль: {user_profile.get('goal')}
- Норма калорій: {user_profile.get('daily_calorie_goal')} ккал"""

            prompt += """
            
Напиши короткий аналіз українською (3-5 речень) з рекомендаціями. Використовуй емодзі."""
            
            loop = asyncio.get_event_loop()
            response = await asyncio.wait_for(
                loop.run_in_executor(None, lambda: self.model.generate_content(prompt)),
                timeout=30.0
            )
            return response.text
        except Exception as e:
            logger.error(f"Weekly analysis error: {e}")
            return "📊 Не вдалося згенерувати аналіз. Спробуйте пізніше."
