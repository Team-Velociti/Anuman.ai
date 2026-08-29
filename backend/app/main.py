import os
import uvicorn
from fastapi import FastAPI, HTTPException, UploadFile, File, Form, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional

from app.llm_agent import process_gemini_chat
from app.voice_router import process_sarvam_audio
from app.weather import fetch_open_meteo_data
from app.database import save_chat_to_db, get_chat_history

app = FastAPI(title="Anuman.ai Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ChatPayload(BaseModel):
    session_id: str
    message: str
    location_key: Optional[str] = None

@app.post("/api/chat", tags=["Chat"])
async def handle_chat(payload: ChatPayload):
    try:
        ai_response_text = await process_gemini_chat(
            session_id=payload.session_id,
            user_message=payload.message,
            location_key=payload.location_key
        )
        
        await save_chat_to_db(payload.session_id, payload.message, ai_response_text)
        updated_history = await get_chat_history(payload.session_id)
        
        return {
            "status": "success",
            "session_id": payload.session_id,
            "reply": ai_response_text,
            "chat_history": updated_history
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Chat routing failed: {str(e)}")

@app.post("/api/voice", tags=["Voice"])
async def handle_voice(session_id: str = Form(...), file: UploadFile = File(...)):
    try:
        audio_bytes = await file.read()
        sarvam_result = await process_sarvam_audio(session_id, audio_bytes, file.filename)
        return {
            "status": "success",
            "session_id": session_id,
            "transcription": sarvam_result.get("transcript", ""),
            "audio_response": sarvam_result.get("tts_audio_url", None)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Voice processing failed: {str(e)}")

@app.get("/api/weather")
async def handle_weather(location_key: str):
    try:
        weather_json = await fetch_open_meteo_data(location_key=location_key)
        return {"status": "success", "location": location_key, "data": weather_json}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/")
async def root():
    return {"status": "Traffic Controller Online"}

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)