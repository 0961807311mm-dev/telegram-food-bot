# ============================================
# Файл: services/supabase_client.py (виправлений)
# ============================================
import os
import logging
from supabase import create_client, Client

logger = logging.getLogger(__name__)

supabase: Client = None

def init_supabase():
    """Ініціалізація клієнта Supabase"""
    global supabase
    
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")
    
    if not url or not key:
        logger.error("SUPABASE_URL or SUPABASE_KEY not set")
        return None
    
    supabase = create_client(url, key)
    logger.info("Supabase client initialized")
    
    return supabase
