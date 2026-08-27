import os
from fastapi import FastAPI, HTTPException, UploadFile, File, Form, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, Any

# =====================================================================
# IMPORTS FROM YOUR / GYANI / SHREYA / KARTIK'S PIPELINE
# =====================================================================
# Make sure these files exist in the same directory or adjust package path
try:
    from llm_agent import process_gemini_chat  # Your Gemini 1.5 Flash agent call
    from voice_router import process_sarvam_audio  # Your Sarvam AI Voice router
    from weather import fetch_open_meteo_data  # Your Open-Meteo script
    from db_service import save_chat_to_db, get_chat_history  # DB team's functions
except ImportError as e:
    # Log warning for local standalone boot-up checks
    print(f"[WARNING] Module import issue: {e}. Ensure teammates' scripts are in path.")

# Initialize FastAPI App
app = FastAPI(
    title="Anuman.ai WeatherGPT Backend Router",
    version="2.0.0",
    description="Traffic controller routing Next.js PWA requests to Gemini, Sarvam AI, and PostgreSQL/MongoDB."
)

# Mandatory CORS configuration for Next.js Frontend (Shruti)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Production ready: replace with exact Next.js URL if needed
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------
# SCHEMAS FOR TRAFFIC ROUTING
# ---------------------------------------------------------------------
class ChatPayload(BaseModel):
    session_id: str
    message: str
    location_key: Optional[str] = None

# ---------------------------------------------------------------------
# 1. /api/chat (The Chat Flow)
# ---------------------------------------------------------------------
@app.post("/api/chat", tags=["Chat"])
async def handle_chat(payload: ChatPayload):
    """
    1. Pass prompt to Gemini 1.5 Flash (llm_agent.py)
    2. Stream payload context to DB (save_chat_to_db)
    3. Return AI response and updated chat history to Shruti (Frontend)
    """
    try:
        # Pass user message straight to Gemini engine logic
        ai_response_text = await process_gemini_chat(
            session_id=payload.session_id,
            user_message=payload.message,
            location_key=payload.location_key
        )
        
        # Log & save message to DB (Shreya/Kartik)
        await save_chat_to_db(
            session_id=payload.session_id,
            user_prompt=payload.message,
            ai_response=ai_response_text
        )
        
        # Retrieve context history for frontend sync
        updated_history = await get_chat_history(payload.session_id)
        
        return {
            "status": "success",
            "session_id": payload.session_id,
            "reply": ai_response_text,
            "chat_history": updated_history
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Chat routing failed: {str(e)}")

# ---------------------------------------------------------------------
# 2. /api/voice (The Voice Flow)
# ---------------------------------------------------------------------
@app.post("/api/voice", tags=["Voice"])
async def handle_voice(
    session_id: str = Form(...),
    file: UploadFile = File(...)
):
    """
    1. Accept raw audio file (WAV/MP3) from Shruti
    2. Pass straight to Sarvam AI router (voice_router.py)
    3. Return transcript and optional TTS payload
    """
    try:
        # Pass uploaded binary audio straight into Sarvam AI audio pipeline
        audio_bytes = await file.read()
        sarvam_result = await process_sarvam_audio(
            session_id=session_id,
            audio_data=audio_bytes,
            filename=file.filename
        )
        
        return {
            "status": "success",
            "session_id": session_id,
            "transcription": sarvam_result.get("transcript", ""),
            "audio_response": sarvam_result.get("tts_audio_url", None)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Voice processing failed: {str(e)}")

# ---------------------------------------------------------------------
# 3. /api/weather (The Dashboard Flow)
# ---------------------------------------------------------------------
@app.get("/api/weather", tags=["Dashboard Weather"])
async def handle_weather(
    location_key: str = Query(..., description="Target location (guntur, vit_ap, vijayawada, vizag)")
):
    """
    1. Trigger weather fetcher (weather.py)
    2. Hand over raw weather JSON directly to Shruti to populate UI cards
    """
    try:
        weather_json = await fetch_open_meteo_data(location_key=location_key)
        return {
            "status": "success",
            "location": location_key,
            "data": weather_json
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Weather retrieval failed: {str(e)}")

# Health Check Endpoint
@app.get("/", tags=["Health"])
async def root():
    return {"status": "Traffic Controller Online", "engine": "FastAPI"}