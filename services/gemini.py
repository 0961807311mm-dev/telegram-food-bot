# ============================================
# Файл: services/gemini.py
# ============================================
import os
import json
import base64
import logging
import httpx
from typing import Dict, Any, List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

class GeminiService:
    def __init__(self):
        self.api_key = os.getenv("GEMINI_API_KEY")
        self.base_url = "https://generativelanguage.googleapis.com/v1beta"
        self.model = "gemini-2.0-flash-exp"  # Використовуємо 2.0 Flash
        
    async def analyze_meal(self, photo_bytes: bytes, filename: str) -> Dict[str, Any]:
        """Аналіз фото їжі"""
        try:
            # Конвертуємо фото в base64
            base64_image = base64.b64encode(photo_bytes).decode('utf-8')
            
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
            
            # Формуємо запит до Gemini
            url = f"{self.base_url}/models/{self.model}:generateContent?key={self.api_key}"
            
            payload = {
                "contents": [
                    {
                        "parts": [
                            {"text": prompt},
                            {
                                "inline_data": {
                                    "mime_type": self._get_mime_type(filename),
                                    "data": base64_image
                                }
                            }
                        ]
                    }
                ],
                "generationConfig": {
                    "temperature": 0.2,
                    "topK": 1,
                    "topP": 1,
                    "maxOutputTokens": 500
                }
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.post(url, json=payload, timeout=30.0)
                response.raise_for_status()
                result = response.json()
                
                # Парсимо відповідь
                text_response = result["candidates"][0]["content"]["parts"][0]["text"]
                
                # Очищаємо текст від markdown
                text_response = text_response.strip()
                if text_response.startswith("```json"):
                    text_response = text_response[7:]
                if text_response.startswith("```"):
                    text_response = text_response[3:]
                if text_response.endswith("```"):
                    text_response = text_response[:-3]
                
                # Парсимо JSON
                analysis = json.loads(text_response.strip())
                
                # Валідація даних
                analysis["calories"] = max(0, int(analysis.get("calories", 0)))
                analysis["protein"] = max(0, float(analysis.get("protein", 0)))
                analysis["fat"] = max(0, float(analysis.get("fat", 0)))
                analysis["carbs"] = max(0, float(analysis.get("carbs", 0)))
                
                logger.info(f"Meal analyzed: {analysis['name']} - {analysis['calories']} kcal")
                return analysis
                
        except json.JSONDecodeError as e:
            logger.error(f"JSON parsing error: {e}, response: {text_response}")
            return self._get_default_analysis()
        except Exception as e:
            logger.error(f"Gemini API error: {e}")
            return self._get_default_analysis()
    
    async def analyze_weekly(self, meals: List[Dict], averages: Dict, user_profile: Optional[Dict]) -> str:
        """Аналіз тижневого харчування"""
        try:
            # Формуємо детальний звіт про харчування
            meals_summary = []
            for meal in meals[-20:]:  # Останні 20 прийомів для контексту
                meals_summary.append(
                    f"- {meal.get('name')}: {meal.get('calories')} ккал, "
                    f"білки: {meal.get('protein')}г, жири: {meal.get('fat')}г, вуглеводи: {meal.get('carbs')}г"
                )
            
            prompt = f"""
            Ти експерт-нутриціолог. Проаналізуй харчування за тиждень.
            
            Середні показники за день:
            - Калорії: {averages.get('calories', 0):.0f} ккал
            - Білки: {averages.get('protein', 0):.1f} г
            - Жири: {averages.get('fat', 0):.1f} г
            - Вуглеводи: {averages.get('carbs', 0):.1f} г
            
            Останні прийоми їжі:
            {chr(10).join(meals_summary[:10])}
            """
            
            if user_profile:
                prompt += f"""
                
                Дані користувача:
                - Вік: {user_profile.get('age')}
                - Стать: {user_profile.get('gender')}
                - Вага: {user_profile.get('weight')} кг
                - Зріст: {user_profile.get('height')} см
                - Рівень активності: {user_profile.get('activity_level')}
                - Ціль: {user_profile.get('goal')}
                - Рекомендована норма калорій: {user_profile.get('daily_calorie_goal')} ккал
                """
            
            prompt += """
            
            Напиши детальний аналіз українською мовою:
            1. Оцінка загального харчування (що добре, що потребує покращення)
            2. Аналіз макронутрієнтів (білки, жири, вуглеводи) - чи відповідають нормі
            3. Яких мікроелементів може не вистачати (залізо, кальцій, вітаміни тощо)
            4. 3 конкретні рекомендації на наступний тиждень
            
            Відповідай у дружньому, мотивуючому стилі. Використовуй емодзі для візуального оформлення.
            """
            
            url = f"{self.base_url}/models/{self.model}:generateContent?key={self.api_key}"
            
            payload = {
                "contents": [
                    {
                        "parts": [{"text": prompt}]
                    }
                ],
                "generationConfig": {
                    "temperature": 0.7,
                    "topK": 1,
                    "topP": 1,
                    "maxOutputTokens": 1000
                }
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.post(url, json=payload, timeout=30.0)
                response.raise_for_status()
                result = response.json()
                
                analysis = result["candidates"][0]["content"]["parts"][0]["text"]
                logger.info("Weekly analysis generated")
                return analysis
                
        except Exception as e:
            logger.error(f"Weekly analysis error: {e}")
            return "📊 *Аналіз тижня*\n\nНа жаль, не вдалося згенерувати детальний аналіз. Спробуйте пізніше або додайте більше даних про харчування."
    
    def _get_mime_type(self, filename: str) -> str:
        """Визначення MIME типу фото"""
        ext = filename.lower().split('.')[-1] if '.' in filename else 'jpg'
        mime_types = {
            'jpg': 'image/jpeg',
            'jpeg': 'image/jpeg',
            'png': 'image/png',
            'gif': 'image/gif',
            'webp': 'image/webp'
        }
        return mime_types.get(ext, 'image/jpeg')
    
    def _get_default_analysis(self) -> Dict[str, Any]:
        """Повертає стандартний аналіз у разі помилки"""
        return {
            "name": "Нерозпізнана страва",
            "calories": 0,
            "protein": 0,
            "fat": 0,
            "carbs": 0,
            "feedback": "❌ Не вдалося розпізнати страву. Спробуйте сфотографувати краще або додайте дані вручну."
        }
