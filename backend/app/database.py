import os
import firebase_admin
from firebase_admin import credentials, firestore
from datetime import datetime, timezone

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
    try:
        doc_ref = db.collection('chat_sessions').document(session_id)
        # Using ArrayUnion to safely append messages to history
        doc_ref.set({
            'history': firestore.ArrayUnion([
                {'role': 'user', 'parts': [user_prompt]},
                {'role': 'model', 'parts': [ai_response]} # Gemini API uses 'model' instead of 'ai'
            ])
        }, merge=True)
    except Exception as e:
        print(f"[DB ERROR] Failed to save chat: {e}")

async def get_chat_history(session_id: str) -> list:
    """Fetches chat history and formats it for Gemini: [{'role': '...', 'parts': ['...']}]"""
    if not db: return []
    try:
        doc_ref = db.collection('chat_sessions').document(session_id)
        doc = doc_ref.get()
        if doc.exists:
            data = doc.to_dict()
            return data.get('history', [])
    except Exception as e:
        print(f"[DB ERROR] Failed to fetch chat history: {e}")
    return []

# ==========================================
# WEATHER CACHE FUNCTIONS
# ==========================================
async def get_cached_weather(location_key: str):
    """Returns weather data from Firestore IF it is less than 60 mins old. Else returns None."""
    if not db: return None
    try:
        doc_ref = db.collection('weather_cache').document(location_key)
        doc = doc_ref.get()
        if doc.exists:
            data = doc.to_dict()
            saved_time = data.get('timestamp')
            
            # Check if cache is older than 60 minutes
            if saved_time:
                now = datetime.now(timezone.utc)
                diff = now - saved_time
                if diff.total_seconds() < 3600: # 3600 seconds = 60 mins
                    return data.get('weather_data')
    except Exception as e:
        print(f"[DB ERROR] Failed to fetch cache: {e}")
    return None

async def update_weather_cache(location_key: str, new_data: dict):
    """Overwrites the location document in 'weather_cache' with new_data and current timestamp."""
    if not db: return
    try:
        doc_ref = db.collection('weather_cache').document(location_key)
        doc_ref.set({
            'weather_data': new_data,
            'timestamp': datetime.now(timezone.utc)
        })
    except Exception as e:
        print(f"[DB ERROR] Failed to update cache: {e}")