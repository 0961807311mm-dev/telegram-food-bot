# Замість помилки, повертайте тестові дані
if not self.model:
    logger.warning("Gemini not available, using mock mode")
    self.model = None

async def analyze_meal(self, photo_bytes: bytes, filename: str):
    if self.model is None:
        return {
            "name": "Тестова страва",
            "calories": 350,
            "protein": 20,
            "fat": 12,
            "carbs": 35,
            "feedback": "✅ Тестовий режим (Gemini недоступний)"
        }
    # ... інший код
