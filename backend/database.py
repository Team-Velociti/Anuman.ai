import os
import firebase_admin
from firebase_admin import credentials, firestore
from datetime import datetime, timedelta, timezone

# 1. Initialize Firebase (Ensure it only initializes once)
if not firebase_admin._apps:
    cred_path = os.getenv("FIREBASE_CRED_PATH")
    if not cred_path or not os.path.exists(cred_path):
        print("[WARNING] Firebase credentials JSON not found! DB will not work.")
    else:
        cred = credentials.Certificate(cred_path)
        firebase_admin.initialize_app(cred)

db = firestore.client() if firebase_admin._apps else None

# ==========================================
# CHAT HISTORY FUNCTIONS
# ==========================================
async def save_chat_to_db(session_id: str, user_prompt: str, ai_response: str):
    """Saves the user and AI messages to Firestore."""
    if not db: return
    # TODO: Implement Firestore push to 'chat_sessions' collection
    pass

async def get_chat_history(session_id: str) -> list:
    """Fetches chat history and formats it for Gemini: [{'role': '...', 'parts': ['...']}]"""
    if not db: return []
    # TODO: Fetch from Firestore and format it
    return []

# ==========================================
# WEATHER CACHE FUNCTIONS
# ==========================================
async def get_cached_weather(location_key: str):
    """Returns weather data from Firestore IF it is less than 60 mins old. Else returns None."""
    if not db: return None
    # TODO: Check 'weather_cache' collection and validate timestamp
    return None

async def update_weather_cache(location_key: str, new_data: dict):
    """Overwrites the location document in 'weather_cache' with new_data and current timestamp."""
    if not db: return
    # TODO: Update Firestore document
    pass