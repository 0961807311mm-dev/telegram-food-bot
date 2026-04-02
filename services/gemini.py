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
            logger.error("No Gemini model available!")
            raise ValueError("No Gemini model available")
    
    async def analyze_meal(self, photo_bytes: bytes, filename: str) -> Dict[str, Any]:
        """Аналіз фото їжі через Gemini"""
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
            
            # Промпт
            prompt = """Analyze this food image. Return ONLY valid JSON (no markdown, no extra text):
{
    "name": "dish name in Ukrainian",
    "calories": estimated calories (number),
    "protein": protein in grams (number),
    "fat": fat in grams (number),
    "carbs": carbohydrates in grams (number),
    "feedback": "short recommendation in Ukrainian (1 sentence)"
}

If unclear, return: {"name": "Невідомо", "calories": 0, "protein": 0, "fat": 0, "carbs": 0, "feedback": "Не вдалося розпізнати"}

Be specific about the dish name."""
            
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
            return {"name": "Помилка", "calories": 0, "protein": 0, "fat": 0, "carbs": 0, "feedback": "⏰ Час очікування вичерпано"}
        except Exception as e:
            logger.error(f"Gemini API error: {e}")
            return {"name": "Помилка", "calories": 0, "protein": 0, "fat": 0, "carbs": 0, "feedback": f"❌ Помилка: {str(e)[:50]}"}
    
    async def analyze_weekly(self, meals: List[Dict], averages: Dict, user_profile: Dict) -> str:
        """Аналіз тижневого харчування"""
        try:
            prompt = f"""Analyze weekly nutrition (in Ukrainian):
Daily averages: {averages.get('calories', 0):.0f} kcal, protein {averages.get('protein', 0):.1f}g, fat {averages.get('fat', 0):.1f}g, carbs {averages.get('carbs', 0):.1f}g.
Give short analysis with recommendations (3-5 sentences)."""
            
            loop = asyncio.get_event_loop()
            response = await asyncio.wait_for(
                loop.run_in_executor(None, lambda: self.model.generate_content(prompt)),
                timeout=30.0
            )
            return response.text
        except Exception as e:
            logger.error(f"Weekly analysis error: {e}")
            return "📊 Не вдалося згенерувати аналіз."
