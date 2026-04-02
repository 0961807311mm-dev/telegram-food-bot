# ============================================
# Файл: services/gemini.py (ПОВНИЙ З ДІАГНОСТИКОЮ)
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
        api_key = os.getenv("GEMINI_API_KEY")
        
        logger.info(f"🔑 GEMINI_API_KEY present: {bool(api_key)}")
        
        if not api_key:
            logger.error("❌ GEMINI_API_KEY not set! Please add your API key in Render environment variables.")
            raise ValueError("GEMINI_API_KEY not set")
        
        try:
            genai.configure(api_key=api_key)
            logger.info("✅ Gemini configured successfully")
            
            # Спробуємо різні моделі
            models_to_try = [
                'gemini-2.0-flash',
                'gemini-1.5-flash',
                'gemini-pro'
            ]
            
            self.model = None
            for model_name in models_to_try:
                try:
                    logger.info(f"🔄 Trying model: {model_name}")
                    test_model = genai.GenerativeModel(model_name)
                    # Короткий тест
                    test_response = test_model.generate_content("Test")
                    if test_response and test_response.text:
                        self.model = test_model
                        logger.info(f"✅ Gemini model initialized: {model_name}")
                        break
                except Exception as e:
                    logger.warning(f"⚠️ Model {model_name} failed: {e}")
                    continue
            
            if not self.model:
                raise Exception("No available Gemini model found")
            
            # Тестовий запит для перевірки
            test_response = self.model.generate_content("Say 'API works'")
            logger.info(f"✅ Gemini test successful: {test_response.text[:50]}")
                
        except Exception as e:
            logger.error(f"❌ Gemini initialization error: {e}")
            raise ValueError(f"Gemini initialization failed: {e}")
    
    async def analyze_meal(self, photo_bytes: bytes, filename: str) -> Dict[str, Any]:
        """Аналіз фото їжі через Gemini"""
        try:
            logger.info(f"📸 Starting analysis for: {filename}")
            logger.info(f"📏 Photo size: {len(photo_bytes)} bytes")
            
            # Відкриваємо фото
            image = Image.open(io.BytesIO(photo_bytes))
            logger.info(f"🖼️ Image mode: {image.mode}, size: {image.size}")
            
            # Конвертуємо в RGB
            if image.mode != 'RGB':
                image = image.convert('RGB')
                logger.info("🔄 Converted to RGB")
            
            # Стискаємо для швидкості
            max_size = 1024
            original_size = image.size
            if image.size[0] > max_size or image.size[1] > max_size:
                image.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
                logger.info(f"📐 Resized from {original_size} to {image.size}")
            
            # Зберігаємо в байти
            img_byte_arr = io.BytesIO()
            image.save(img_byte_arr, format='JPEG', quality=85)
            img_byte_arr = img_byte_arr.getvalue()
            logger.info(f"📦 Compressed size: {len(img_byte_arr)} bytes")
            
            # Покращений промпт
            prompt = """Ти професійний нутриціолог. Уважно проаналізуй це фото їжі.
Визнач страву якомога точніше. Зверни увагу на форму, текстуру, колір, інгредієнти.

Поверни ТІЛЬКИ JSON (без markdown, без додаткового тексту):

{
    "name": "точна назва страви українською мовою",
    "calories": число (приблизна калорійність),
    "protein": число (білки в грамах),
    "fat": число (жири в грамах),
    "carbs": число (вуглеводи в грамах),
    "feedback": "коротка корисна рекомендація українською (1 речення)"
}

Будь уважним та точним. Якщо це круасан - напиши "Круасан", якщо сирники - "Сирники", якщо яблуко - "Яблуко"."""
            
            # Запит до Gemini
            logger.info("🚀 Sending request to Gemini API...")
            loop = asyncio.get_event_loop()
            response = await asyncio.wait_for(
                loop.run_in_executor(None, lambda: self.model.generate_content([prompt, img_byte_arr])),
                timeout=30.0
            )
            
            text = response.text.strip()
            logger.info(f"📝 Gemini response received: {text[:200]}")
            
            # Очищаємо від markdown
            text = re.sub(r'^```json\s*', '', text)
            text = re.sub(r'^```\s*', '', text)
            text = re.sub(r'\s*```$', '', text)
            
            # Шукаємо JSON
            json_match = re.search(r'\{[^{}]*\}', text, re.DOTALL)
            if json_match:
                text = json_match.group()
            
            analysis = json.loads(text)
            
            result = {
                "name": analysis.get("name", "Невідомо"),
                "calories": max(0, int(analysis.get("calories", 0))),
                "protein": max(0, float(analysis.get("protein", 0))),
                "fat": max(0, float(analysis.get("fat", 0))),
                "carbs": max(0, float(analysis.get("carbs", 0))),
                "feedback": analysis.get("feedback", "✅ Смачного!")
            }
            
            logger.info(f"✅ Analyzed: {result['name']} - {result['calories']} kcal")
            return result
            
        except asyncio.TimeoutError:
            logger.error("❌ Gemini timeout after 30 seconds")
            return {
                "name": "Помилка аналізу",
                "calories": 0,
                "protein": 0,
                "fat": 0,
                "carbs": 0,
                "feedback": "⏰ Час очікування вичерпано. Спробуйте ще раз."
            }
        except json.JSONDecodeError as e:
            logger.error(f"❌ JSON parse error: {e}")
            logger.error(f"Raw response: {text[:500] if 'text' in locals() else 'no text'}")
            return {
                "name": "Помилка формату",
                "calories": 0,
                "protein": 0,
                "fat": 0,
                "carbs": 0,
                "feedback": "❌ Помилка аналізу. Спробуйте інше фото."
            }
        except Exception as e:
            logger.error(f"❌ Gemini API error: {e}", exc_info=True)
            return {
                "name": "Помилка",
                "calories": 0,
                "protein": 0,
                "fat": 0,
                "carbs": 0,
                "feedback": f"❌ Помилка: {str(e)[:100]}. Перевірте API ключ."
            }
    
    async def analyze_weekly(self, meals: List[Dict], averages: Dict, user_profile: Dict) -> str:
        """Аналіз тижневого харчування через Gemini"""
        try:
            logger.info("📊 Starting weekly analysis")
            
            prompt = f"""Проаналізуй харчування за тиждень (українською мовою):

Середні показники за день:
- Калорії: {averages.get('calories', 0):.0f} ккал
- Білки: {averages.get('protein', 0):.1f} г
- Жири: {averages.get('fat', 0):.1f} г
- Вуглеводи: {averages.get('carbs', 0):.1f} г

Кількість прийомів їжі: {len(meals)}"""

            if user_profile:
                prompt += f"""

Дані користувача:
- Вік: {user_profile.get('age')}
- Стать: {user_profile.get('gender')}
- Вага: {user_profile.get('weight')} кг
- Зріст: {user_profile.get('height')} см
- Ціль: {user_profile.get('goal')}
- Норма калорій: {user_profile.get('daily_calorie_goal')} ккал"""

            prompt += """

Напиши детальний аналіз українською мовою (5-7 речень):
1. Оцінка загального харчування
2. Аналіз балансу БЖУ
3. Що можна покращити
4. 2-3 конкретні рекомендації на наступний тиждень

Будь дружнім та мотивуючим, використовуй емодзі."""
            
            logger.info("🚀 Sending weekly analysis request to Gemini...")
            loop = asyncio.get_event_loop()
            response = await asyncio.wait_for(
                loop.run_in_executor(None, lambda: self.model.generate_content(prompt)),
                timeout=40.0
            )
            
            logger.info("✅ Weekly analysis generated")
            return response.text
            
        except asyncio.TimeoutError:
            logger.error("❌ Weekly analysis timeout")
            return "📊 Не вдалося згенерувати аналіз. Спробуйте пізніше."
        except Exception as e:
            logger.error(f"❌ Weekly analysis error: {e}", exc_info=True)
            return f"📊 Помилка: {str(e)[:100]}"

# Для тестування API ключа окремо
def test_gemini_api():
    """Функція для тестування API ключа"""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("❌ GEMINI_API_KEY not set")
        return False
    
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-2.0-flash')
        response = model.generate_content("Say 'API works'")
        print(f"✅ API test successful: {response.text}")
        return True
    except Exception as e:
        print(f"❌ API test failed: {e}")
        return False

# Якщо запустити файл окремо для тесту
if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    test_gemini_api()
