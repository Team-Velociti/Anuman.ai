import os
import base64
# pyrefly: ignore [missing-import]
import httpx

SARVAM_API_KEY = os.getenv("SARVAM_API_KEY")

async def speech_to_text(audio_bytes: bytes) -> str:
    """
    Sends audio data to Sarvam's STT endpoint and returns the transcribed text.

    Args:
        audio_bytes (bytes): The raw audio file bytes.

    Returns:
        str: The transcribed text. Returns an empty string if an error occurs.
    """
    if not SARVAM_API_KEY:
        raise ValueError("SARVAM_API_KEY environment variable is not set.")

    url = "https://api.sarvam.ai/speech-to-text"
    headers = {"api-subscription-key": SARVAM_API_KEY}
    
    # We send the raw audio bytes as a file.
    files = {"file": ("audio.wav", audio_bytes, "audio/wav")}
    data = {"model": "saaras:v3"}

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            res = await client.post(url, headers=headers, files=files, data=data)
            res.raise_for_status()
            
            payload = res.json()
            # Extract transcript (falling back to text just in case)
            return payload.get("transcript") or payload.get("text", "")
            
    except httpx.HTTPStatusError as e:
        print(f"STT API returned an error: {e.response.status_code} - {e.response.text}")
    except httpx.RequestError as e:
        print(f"STT API request failed: {e}")
    except Exception as e:
        print(f"Unexpected error in STT: {e}")
        
    return ""

async def text_to_speech(text: str) -> bytes:
    """
    Sends a text string to Sarvam's TTS endpoint and returns the generated audio bytes.

    Args:
        text (str): The text to synthesize into speech.

    Returns:
        bytes: The synthesized audio data. Returns empty bytes if an error occurs.
    """
    if not SARVAM_API_KEY:
        raise ValueError("SARVAM_API_KEY environment variable is not set.")

    url = "https://api.sarvam.ai/text-to-speech"
    headers = {
        "api-subscription-key": SARVAM_API_KEY,
        "Content-Type": "application/json"
    }
    
    payload = {
        "text": text,
        "language_code": "en-IN",  # Defaulting to English-India
        "model": "bulbul:v3"
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            res = await client.post(url, headers=headers, json=payload)
            res.raise_for_status()
            
            data = res.json()
            # The API returns a list of base64 encoded audio strings
            audios = data.get("audios", [])
            
            if audios:
                return base64.b64decode(audios[0])
            else:
                print("TTS API returned no audio data.")
                
    except httpx.HTTPStatusError as e:
        print(f"TTS API returned an error: {e.response.status_code} - {e.response.text}")
    except httpx.RequestError as e:
        print(f"TTS API request failed: {e}")
    except Exception as e:
        print(f"Unexpected error in TTS: {e}")
        
    return b""

# =====================================================================
# BRIDGE FUNCTION FOR HEMANG'S main.py
# =====================================================================
async def process_sarvam_audio(session_id: str, audio_data: bytes, filename: str) -> dict:
    """
    Wrapper function that Hemang's main.py calls.
    It takes the raw audio, gets the transcript via Sarvam STT, and returns it.
    """
    print(f"[INFO] Processing voice upload for session: {session_id}, file: {filename}")
    
    try:
        # Step 1: Convert uploaded audio to text
        transcript = await speech_to_text(audio_data)
        
        # Step 2: Return dictionary format that Hemang's API expects
        return {
            "transcript": transcript,
            # Note: Right now we are just returning STT. 
            # If we want the AI to speak back, we can integrate text_to_speech here later 
            # and return the base64 string or URL.
            "tts_audio_url": None 
        }
        
    except Exception as e:
        print(f"[ERROR] Voice routing failed for {session_id}: {str(e)}")
        return {
            "transcript": "",
            "tts_audio_url": None
        }