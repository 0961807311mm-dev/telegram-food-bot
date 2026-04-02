# Додай ці ендпоінти в main.py для роботи з вітамінами

@app.post("/api/supplements")
async def create_supplement(supplement: dict):
    """Зберегти вітамін/добавку"""
    try:
        telegram_id = supplement.get("telegram_id")
        logger.info(f"📝 API: Saving supplement for user {telegram_id}")
        
        # Тимчасово зберігаємо в пам'яті
        if telegram_id not in _memory_db["supplements"]:
            _memory_db["supplements"][telegram_id] = []
        
        supplement_data = {
            "name": supplement.get("name"),
            "created_at": datetime.utcnow().isoformat()
        }
        _memory_db["supplements"][telegram_id].append(supplement_data)
        
        return JSONResponse(supplement_data)
    except Exception as e:
        logger.error(f"Error saving supplement: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)

@app.get("/api/supplements/{telegram_id}")
async def get_supplements(telegram_id: int):
    """Отримати вітаміни/добавки"""
    try:
        supplements = _memory_db["supplements"].get(telegram_id, [])
        return JSONResponse(supplements)
    except Exception as e:
        logger.error(f"Error getting supplements: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)

@app.post("/api/water/{telegram_id}")
async def save_water(telegram_id: int, data: dict):
    """Зберегти кількість води"""
    try:
        amount = data.get("amount", 0)
        _memory_db["water"][telegram_id] = _memory_db["water"].get(telegram_id, 0) + amount
        return JSONResponse({"total": _memory_db["water"][telegram_id]})
    except Exception as e:
        logger.error(f"Error saving water: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)

@app.get("/api/water/{telegram_id}")
async def get_water(telegram_id: int):
    """Отримати кількість води"""
    try:
        total = _memory_db["water"].get(telegram_id, 0)
        return JSONResponse({"total": total})
    except Exception as e:
        logger.error(f"Error getting water: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)
