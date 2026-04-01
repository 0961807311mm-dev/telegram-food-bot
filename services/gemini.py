import os
import logging
import google.generativeai as genai
from PIL import Image
import io
from typing import Dict, Any

logger = logging.getLogger(__name__)

class GeminiService:
    def __init__(self):
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY not set")
        
        genai.configure(api_key=api_key)
        # Використовуємо Gemini 2.0 Flash (найновіший)
        self.model = genai.GenerativeModel('gemini-2.0-flash-exp')
        logger.info("Gemini 2.0 Flash initialized")
    
    async def analyze_meal(self, photo_bytes: bytes, filename: str) -> Dict[str, Any]:
        """Аналіз фото їжі через Gemini"""
        try:
            # Відкриваємо фото
            image = Image.open(io.BytesIO(photo_bytes))
            
            # Промпт для Gemini
            prompt = """
            Ти експерт-нутриціолог. Проаналізуй фото їжі та визнач:
            1. Назву страви
            2. Приблизну кількість калорій
            3. Кількість білків (г)
            4. Кількість жирів (г)
            5. Кількість вуглеводів (г)
            6. Коротку рекомендацію (1-2 речення)
            
            Відповідай ТІЛЬКИ в форматі JSON:
            {
                "name": "назва страви",
                "calories": число,
                "protein": число,
                "fat": число,
                "carbs": число,
                "feedback": "рекомендація українською мовою"
            }
            
            Якщо на фото не видно їжу чітко, встанови значення 0 та напиши відповідну рекомендацію.
            """
            
            # Запит до Gemini
            response = self.model.generate_content([prompt, image])
            
            # Парсимо відповідь
            import json
            import re
            
            text = response.text.strip()
            
            # Очищаємо від markdown
            if text.startswith("```json"):
                text = text[7:]
            if text.startswith("```"):
                text = text[3:]
            if text.endswith("```"):
                text = text[:-3]
            
            analysis = json.loads(text.strip())
            
            # Валідація даних
            analysis["calories"] = max(0, int(analysis.get("calories", 0)))
            analysis["protein"] = max(0, float(analysis.get("protein", 0)))
            analysis["fat"] = max(0, float(analysis.get("fat", 0)))
            analysis["carbs"] = max(0, float(analysis.get("carbs", 0)))
            
            logger.info(f"Meal analyzed: {analysis['name']} - {analysis['calories']} kcal")
            return analysis
            
        except Exception as e:
            logger.error(f"Gemini API error: {e}")
            return {
                "name": "Нерозпізнана страва",
                "calories": 0,
                "protein": 0,
                "fat": 0,
                "carbs": 0,
                "feedback": "❌ Не вдалося розпізнати страву. Спробуйте сфотографувати краще."
            }
