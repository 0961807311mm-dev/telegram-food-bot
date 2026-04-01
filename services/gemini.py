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
            raise ValueError("GEMINI_API_KEY not set")
        
        genai.configure(api_key=api_key)
        
        # Використовуємо правильні назви моделей
        self.model_names = [
            'gemini-2.0-flash',
            'gemini-1.5-flash',
            'gemini-pro'
        ]
        self.model = None
        
        # Знаходимо доступну модель
        for name in self.model_names:
            try:
                self.model = genai.GenerativeModel(name)
                # Тестуємо модель
                test_response = self.model.generate_content("Test")
                if test_response:
                    logger.info(f"✅ Using Gemini model: {name}")
                    break
            except Exception as e:
                logger.warning(f"Model {name} not available: {e}")
                continue
        
        if not self.model:
            logger.error("No Gemini model available!")
            raise ValueError("No Gemini model available")
    
    async def analyze_meal(self, photo_bytes: bytes, filename: str) -> Dict[str, Any]:
        """Аналіз фото їжі через Gemini"""
        try:
            # Відкриваємо фото
            image = Image.open(io.BytesIO(photo_bytes))
            
            # Конвертуємо в RGB якщо потрібно
            if image.mode != 'RGB':
                image = image.convert('RGB')
            
            # Стискаємо
            max_size = 1024
            if image.size[0] > max_size or image.size[1] > max_size:
                image.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
            
            # Промпт
            prompt = """Analyze this food photo. Return ONLY valid JSON:
{
    "name": "dish name in Ukrainian",
    "calories": number,
    "protein": number,
    "fat": number,
    "carbs": number,
    "feedback": "recommendation in Ukrainian"
}"""
            
            # Запит до Gemini
            loop = asyncio.get_event_loop()
            response = await asyncio.wait_for(
                loop.run_in_executor(None, lambda: self.model.generate_content([prompt, image])),
                timeout=20.0
            )
            
            text = response.text.strip()
            
            # Очищаємо від markdown
            text = re.sub(r'^```json\s*', '', text)
            text = re.sub(r'^```\s*', '', text)
            text = re.sub(r'\s*```$', '', text)
            
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
            return self._get_default_analysis()
        except Exception as e:
            logger.error(f"Gemini API error: {e}")
            return self._get_default_analysis()
    
    async def analyze_weekly(self, meals: List[Dict], averages: Dict, user_profile: Dict) -> str:
        """Аналіз тижневого харчування"""
        try:
            prompt = f"""
            Проаналізуй харчування за тиждень.
            
            Середні показники за день:
            - Калорії: {averages.get('calories', 0):.0f} ккал
            - Білки: {averages.get('protein', 0):.1f} г
            - Жири: {averages.get('fat', 0):.1f} г
            - Вуглеводи: {averages.get('carbs', 0):.1f} г
            """
            
            if user_profile:
                prompt += f"""
                Дані користувача:
                - Вага: {user_profile.get('weight')} кг, Ціль: {user_profile.get('goal')}
                - Норма калорій: {user_profile.get('daily_calorie_goal')} ккал
                """
            
            prompt += """
            Напиши короткий аналіз українською (3-5 речень) з рекомендаціями.
            """
            
            loop = asyncio.get_event_loop()
            response = await asyncio.wait_for(
                loop.run_in_executor(None, lambda: self.model.generate_content(prompt)),
                timeout=30.0
            )
            
            return response.text
            
        except Exception as e:
            logger.error(f"Weekly analysis error: {e}")
            return "📊 Не вдалося згенерувати аналіз."
    
    def _get_default_analysis(self) -> Dict[str, Any]:
        return {
            "name": "Нерозпізнана страва",
            "calories": 0,
            "protein": 0,
            "fat": 0,
            "carbs": 0,
            "feedback": "❌ Не вдалося розпізнати страву. Спробуйте краще освітлення."
        }
