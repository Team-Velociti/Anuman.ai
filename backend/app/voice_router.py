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

def _detect_language(text: str) -> str:
    """Detect if text is Romanized Hindi, Telugu, or English based on common keywords."""
    text_lower = text.lower()
    
    # Common Romanized Hindi words
    hindi_keywords = {"hai", "mein", "aur", "ka", "ki", "ke", "se", "yeh", "woh", "aaj", "hogi", "tapman", "barish", "salah", "kare", "raha"}
    
    # Common Romanized Telugu words
    telugu_keywords = {"undi", "lo", "mariyu", "nundi", "ki", "ku", "varsham", "vediga", "roju", "eeroju", "cheyandi", "padutundi"}
    
    words = set(re.findall(r'\b[a-z]+\b', text_lower))
    
    hindi_match = len(words.intersection(hindi_keywords))
    telugu_match = len(words.intersection(telugu_keywords))
    
    if hindi_match > 1 and hindi_match > telugu_match:
        return "hi-IN"
    elif telugu_match > 1:
        return "te-IN"
        
    return "en-IN"


def _preprocess_for_tts(text: str, lang: str) -> str:
    """Expand symbols and abbreviations so TTS reads them naturally."""
    text = re.sub(r'\*+', '', text)
    text = re.sub(r'#+\s*', '', text)
    text = text.replace('_', '')

    if lang == "hi-IN":
        text = text.replace('°C', ' डिग्री सेल्सियस')
        text = text.replace('°F', ' डिग्री फारेनहाइट')
        text = re.sub(r'(\d+)\s*%', r'\1 प्रतिशत', text)
        text = text.replace('km/h', ' किलोमीटर प्रति घंटा')
    else:
        text = text.replace('°C', ' degrees Celsius')
        text = text.replace('°F', ' degrees Fahrenheit')
        text = re.sub(r'(\d+)\s*%', r'\1 percent', text)
        text = text.replace('km/h', ' kilometers per hour')

    # Remove non-speakable chars, keep Devanagari + Latin + punctuation
    text = re.sub(r'[^\w\s.,!?\'\"-\u0900-\u097F]', '', text)
    text = re.sub(r'\s{2,}', ' ', text).strip()
    return text


# Initialize Sarvam SDK client
import asyncio
from sarvamai import SarvamAI

_sarvam_client = None
if SARVAM_API_KEY:
    _sarvam_client = SarvamAI(api_subscription_key=SARVAM_API_KEY)
else:
    print("[WARNING] SARVAM_API_KEY missing. TTS will not work.")


async def text_to_speech(text: str) -> str:
    """
    Uses Sarvam SDK convert_stream (same as their website demo).
    Returns base64-encoded audio string. Returns None on failure.
    """
    if not _sarvam_client:
        print("[WARNING] Sarvam client not initialized.")
        return None

    lang_code = _detect_language(text)
    clean_text = _preprocess_for_tts(text, lang_code)

    print(f"[TTS] lang={lang_code}, speaker=ritu, chars={len(clean_text)}")

    try:
        # Run the synchronous SDK call in a thread (FastAPI is async)
        audio_iter = await asyncio.to_thread(
            _sarvam_client.text_to_speech.convert_stream,
            text=clean_text,
            language_code=lang_code,
            speaker="ritu",
            model="bulbul:v3",
            pace=1.0,
            speech_sample_rate=22050,
            enable_preprocessing=True,
        )

        # convert_stream returns Iterator[bytes] — join all chunks
        audio_bytes = b"".join(audio_iter)

        if audio_bytes:
            audio_b64 = base64.b64encode(audio_bytes).decode("utf-8")
            print(f"[TTS] Success! Audio size: {len(audio_bytes)} bytes")
            return audio_b64
        else:
            print("[TTS ERROR] SDK returned empty audio.")
            return None

    except Exception as e:
        print(f"[TTS ERROR] Sarvam SDK failed: {e}")
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