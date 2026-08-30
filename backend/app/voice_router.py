import os
import base64
import re
# pyrefly: ignore [missing-import]
import httpx

SARVAM_API_KEY = os.getenv("SARVAM_API_KEY")

async def speech_to_text(audio_bytes: bytes) -> str:
    """Sends audio data to Sarvam's STT endpoint and returns the transcribed text."""
    if not SARVAM_API_KEY:
        raise ValueError("SARVAM_API_KEY environment variable is not set.")

    url = "https://api.sarvam.ai/speech-to-text"
    headers = {"api-subscription-key": SARVAM_API_KEY}
    
    files = {"file": ("audio.wav", audio_bytes, "audio/wav")}
    data = {"model": "saaras:v3"}

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            res = await client.post(url, headers=headers, files=files, data=data)
            res.raise_for_status()
            
            payload = res.json()
            return payload.get("transcript") or payload.get("text", "")
            
    except Exception as e:
        print(f"[STT ERROR] Failed to convert speech to text: {e}")
        return ""

async def text_to_speech(text: str) -> str:
    """
    Sends a text string to Sarvam's TTS endpoint and returns Base64 audio string.
    Returns None if it fails.
    """
    if not SARVAM_API_KEY:
        print("[WARNING] SARVAM_API_KEY missing. Cannot use TTS.")
        return None

    # AI response se emojis aur markdown characters (**, *, #, ~) hatao, sirf text/punctuation rakho
    clean_text = re.sub(r'[^\w\s.,!?\'"-]', '', text)
    clean_text = clean_text.replace('_', '')

    url = "https://api.sarvam.ai/text-to-speech"
    headers = {
        "api-subscription-key": SARVAM_API_KEY,
        "Content-Type": "application/json"
    }
    
    payload = {
        "inputs": [clean_text], # Naye API endpoints usually 'inputs' array lete hain
        "target_language_code": "hi-IN", # Sarvam Indian languages mein better hai
        "speaker": "meera", # Default speaker
        "pitch": 0,
        "pace": 1.1,
        "loudness": 1.5,
        "speech_sample_rate": 8000,
        "enable_preprocessing": True,
        "model": "bulbul:v1"
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            res = await client.post(url, headers=headers, json=payload)
            res.raise_for_status()
            
            data = res.json()
            audios = data.get("audios", [])
            
            if audios:
                # Return direct base64 string so frontend can play it easily
                return audios[0] 
            else:
                print("[TTS ERROR] API returned no audio data.")
                
    except Exception as e:
        print(f"[TTS ERROR] Failed to convert text to speech: {e}")
        
    return None

# =====================================================================
# BRIDGE FUNCTION FOR AUDIO UPLOADS (If you use it later)
# =====================================================================
async def process_sarvam_audio(session_id: str, audio_data: bytes, filename: str) -> dict:
    print(f"[INFO] Processing voice upload for session: {session_id}, file: {filename}")
    try:
        transcript = await speech_to_text(audio_data)
        return {
            "transcript": transcript,
            "tts_audio_url": None 
        }
    except Exception as e:
        print(f"[ERROR] Voice routing failed for {session_id}: {str(e)}")
        return {"transcript": "", "tts_audio_url": None}