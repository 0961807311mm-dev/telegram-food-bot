import os
import logging
import google.generativeai as genai
from PIL import Image
import io
import json
import re
import asyncio
from typing import Dict, Any

logger = logging.getLogger(__name__)

class GeminiService:
    def __init__(self):
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY not set")
        
        genai.configure(api_key=api_key)
        
        # Gemini 2.5 Flash (актуальна назва)
        self.model = genai.GenerativeModel('gemini-2.5-flash')
        logger.info("Gemini 2.5 Flash initialized")
    
    async def analyze_meal(self, photo_bytes: bytes, filename: str) -> Dict[str, Any]:
        """Аналіз фото їжі через Gemini 2.5 Flash"""
        try:
            # Відкриваємо та стискаємо фото
            image = Image.open(io.BytesIO(photo_bytes))
            
            # Стискаємо для швидкості
            if image.size[0] > 1024:
                ratio = 1024 / image.size[0]
                new_size = (1024, int(image.size[1] * ratio))
                image = image.resize(new_size, Image.Resampling.LANCZOS)
            
            # Промпт для Gemini 2.5 Flash
            prompt = """
            Ти експерт-нутриціолог. Проаналізуй фото їжі.
            
            Відповідай ТІЛЬКИ в форматі JSON (без markdown, без пояснень):
            {"name": "назва страви", "calories": число, "protein": число, "fat": число, "carbs": число, "feedback": "коротка рекомендація українською"}
            
            Якщо страву не видно: calories=0, feedback="Не вдалося розпізнати страву"
            """
            
            # Запит до Gemini з таймаутом
            loop = asyncio.get_event_loop()
            response = await asyncio.wait_for(
                loop.run_in_executor(None, lambda: self.model.generate_content([prompt, image])),
                timeout=15.0
            )
            
            # Парсимо відповідь
            text = response.text.strip()
            logger.info(f"Gemini response: {text[:200]}")  # Лог для відладки
            
            # Очищаємо від markdown
            if text.startswith("```json"):
                text = text[7:]
            if text.startswith("```"):
                text = text[3:]
            if text.endswith("```"):
                text = text[:-3]
            
            # Знаходимо JSON
            json_match = re.search(r'\{.*\}', text, re.DOTALL)
            if json_match:
                text = json_match.group()
            
            analysis = json.loads(text)
            
            # Валідація
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
        except json.JSONDecodeError as e:
            logger.error(f"JSON parse error: {e}, response: {text[:200]}")
            return self._get_default_analysis()
        except Exception as e:
            logger.error(f"Gemini API error: {e}")
            return self._get_default_analysis()
    
    def _get_default_analysis(self) -> Dict[str, Any]:
        return {
            "name": "Нерозпізнана страва",
            "calories": 0,
            "protein": 0,
            "fat": 0,
            "carbs": 0,
            "feedback": "❌ Не вдалося розпізнати страву. Спробуйте сфотографувати краще."
        }
