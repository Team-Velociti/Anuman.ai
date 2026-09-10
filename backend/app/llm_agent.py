import os
import re
import random
import httpx

from app.weather import get_weather
from app.database import get_chat_history

# ============================================================
# API KEY ROTATION (Untouched)
# ============================================================
API_KEYS = [
    os.environ.get("GEMINI_API_KEY_1"),
    os.environ.get("GEMINI_API_KEY_2"),
    os.environ.get("GEMINI_API_KEY_3"),
    os.environ.get("GEMINI_API_KEY_4")
]
VALID_KEYS = [key for key in API_KEYS if key]

if not VALID_KEYS:
    print("WARNING: No Gemini API keys found!")

# ============================================================
# GEMINI REST API CONFIG (No SDK, No Protobuf)
# ============================================================
GEMINI_MODEL = "gemini-3.6-flash"
GEMINI_API_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"

# Tool definition in REST API camelCase format
TOOLS = [
    {
        "functionDeclarations": [
            {
                "name": "get_weather",
                "description": "Fetches current weather and daily forecast for any city globally.",
                "parameters": {
                    "type": "OBJECT",
                    "properties": {
                        "location_name": {
                            "type": "STRING",
                            "description": "The specific location to fetch weather for."
                        }
                    },
                    "required": ["location_name"]
                }
            }
        ]
    }
]

SYSTEM_INSTRUCTION = {
    "parts": [
        {
            "text": (
                "You are Anuman.ai, a global weather assistant. "
                "1. If the user explicitly asks for the weather in a specific location (e.g., 'weather in Bokaro'), you MUST fetch and return the weather for that specific location, ignoring the background context. "
                "2. If the user asks a general question without specifying a location (e.g., 'how is the weather?'), ONLY THEN use the location provided in the '(Context: User is currently in [City])' string attached to the prompt. "
                "3. Never say a location is unsupported. You support global weather tracking. "
                "CRITICAL RULES FOR RESPONDING: "
                "4. NEVER output your internal reasoning, thought process, or mention 'tool calls', 'dicts', or data structures. "
                "5. NEVER say words like 'Wait', 'Let me check', 'Let's summarize', or 'Ah'. "
                "6. DIRECTLY and IMMEDIATELY answer the user's question using the weather data provided. "
                "7. Keep your answers extremely concise, natural, and to-the-point. "
                "8. Provide 1-2 lines of highly actionable advice (e.g., for farmers, students or commuters) based on the weather. "
                "9. CRITICAL RULE FOR ALL OUTPUTS: You must ONLY output text using the Roman script (English alphabet) for ALL languages, including Hindi and Telugu. NEVER use native scripts like Devanagari, Telugu, Tamil, etc. If a user asks for a response in Hindi or Telugu, you MUST provide the translation using ONLY the Romanized English alphabet (e.g., 'Bokaro mein aaj barish hogi' or 'Guntur lo varsham padutundi'). "
                "Speak clearly like a professional news anchor."
            )
        }
    ]
}

# ============================================================
# HELPERS
# ============================================================
MAX_HISTORY_CONTEXT = 10

def _sanitize(text: str) -> str:
    """Strip emojis, regional scripts, zero-width chars. Keep ASCII + Devanagari."""
    if not text or not isinstance(text, str):
        return ""
    text = text.replace('\u200c', '').replace('\u200d', '').replace('\u200b', '').replace('\ufeff', '')
    text = re.sub(r'[^\x20-\x7E\u0900-\u097F\n]', '', text)
    text = re.sub(r'\n{3,}', '\n\n', text).strip()
    return text


def _build_history_context(past_history: list) -> str:
    """Convert DB history into a plain text block for prompt injection."""
    if not past_history:
        return ""
    recent = past_history[-MAX_HISTORY_CONTEXT:]
    lines = []
    for msg in recent:
        role = msg.get("role", "user")
        if role not in ("user", "model"):
            continue
        parts = msg.get("parts", [])
        text = ""
        for p in parts:
            if isinstance(p, str):
                text = p
            elif isinstance(p, dict) and "text" in p:
                text = str(p["text"])
        clean = _sanitize(text)
        if not clean:
            continue
        label = "User" if role == "user" else "Anuman"
        lines.append(f"{label}: {clean[:500]}")
    return "\n".join(lines)


async def _call_gemini(contents: list, api_key: str) -> dict:
    """Direct HTTP POST to Gemini REST API. Zero protobuf."""
    url = f"{GEMINI_API_URL}?key={api_key}"
    body = {
        "contents": contents,
        "tools": TOOLS,
        "systemInstruction": SYSTEM_INSTRUCTION,
    }
    async with httpx.AsyncClient(timeout=30.0) as client:
        res = await client.post(url, json=body, headers={"Content-Type": "application/json"})
        res.raise_for_status()
        return res.json()


async def _call_gemini_with_retry(contents: list) -> dict:
    """Try all available API keys on 429/503 errors before giving up."""
    import asyncio
    keys = list(VALID_KEYS)
    random.shuffle(keys)

    last_error = None
    for i, key in enumerate(keys):
        try:
            return await _call_gemini(contents, key)
        except httpx.HTTPStatusError as e:
            status = e.response.status_code
            last_error = e
            if status in (429, 503) and i < len(keys) - 1:
                print(f"[RETRY] Key {i+1}/{len(keys)} got {status}, trying next key in 2s...")
                await asyncio.sleep(2)
                continue
            raise
        except Exception:
            raise

    raise last_error


# ============================================================
# MAIN CHAT PROCESSOR
# ============================================================
async def process_gemini_chat(session_id: str, user_message: str, location_key: str = None, client_weather_context: str = None) -> str:
    try:
        if not VALID_KEYS:
            return "API keys are not configured. Please set GEMINI_API_KEY in your environment."

        # 1. Build history context as plain text
        past_history = await get_chat_history(session_id)
        history_text = _build_history_context(past_history)

        # 2. Build the full user prompt
        full_message = user_message
        if history_text:
            full_message = (
                "[Previous conversation for context - do not repeat this section]\n"
                f"{history_text}\n\n"
                f"[Current query - respond to this]\n{user_message}"
            )

        if client_weather_context:
            full_message += (
                f"\n\nSystem Note: The frontend has already fetched the live weather "
                f"for the user: {client_weather_context}. Prioritize this data to "
                f"answer the user's query and AVOID calling the backend weather tool."
            )

        # 3. Build contents as plain JSON (no SDK, no protos)
        contents = [
            {"role": "user", "parts": [{"text": full_message}]}
        ]

        print(f"[DEBUG] Calling Gemini REST API ({len(full_message)} chars)")

        # 4. First API call
        result = await _call_gemini_with_retry(contents)

        # 5. Parse response
        candidate = result.get("candidates", [{}])[0]
        content = candidate.get("content", {})
        parts = content.get("parts", [])

        if not parts:
            return "I couldn't generate a response. Please try again."

        first_part = parts[0]

        # 6. Check if it's a direct text response
        if "text" in first_part:
            return first_part["text"]

        # 7. Handle function call
        if "functionCall" in first_part:
            fc = first_part["functionCall"]
            function_name = fc.get("name", "get_weather")
            args = fc.get("args", {})
            location_arg = args.get("location_name", "VIT-AP")

            print(f"[DEBUG] Tool call: {function_name}(location_name='{location_arg}')")

            # Fetch weather data
            weather_data = await get_weather(location_name=location_arg)
            weather_str = str(weather_data)

            # Append model's function call to the conversation
            contents.append(content)  # The model's response with functionCall

            # Append function response
            contents.append({
                "role": "user",
                "parts": [
                    {
                        "functionResponse": {
                            "name": function_name,
                            "response": {"result": weather_str}
                        }
                    }
                ]
            })

            # Second API call with the complete conversation
            result2 = await _call_gemini_with_retry(contents)

            candidate2 = result2.get("candidates", [{}])[0]
            parts2 = candidate2.get("content", {}).get("parts", [])

            if parts2 and "text" in parts2[0]:
                return parts2[0]["text"]

            return "I got the weather data but couldn't format a response. Please try again."

        return "I couldn't understand the response format. Please try again."

    except httpx.HTTPStatusError as e:
        print(f"[ERROR] Gemini API HTTP error: {e.response.status_code} - {e.response.text}")
        return "Sorry, the weather service is temporarily unavailable. Please try again in a moment."
    except Exception as e:
        import traceback
        print(f"[ERROR] Gemini Agent failed: {type(e).__name__}: {e}")
        traceback.print_exc()
        return "Sorry, I am facing some issues connecting to the weather servers right now. Please try again in a moment."