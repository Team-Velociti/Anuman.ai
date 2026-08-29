import os
import google.generativeai as genai

# FIXED: Removed 'app.' since all files are in the same folder
from app.weather import get_weather
from app.database import get_chat_history 

genai.configure(api_key=os.environ.get("GEMINI_API_KEY", ""))

weather_tool = {
    "function_declarations": [
        {
            "name": "get_weather",
            "description": "Fetches current weather and daily forecast.",
            "parameters": {
                "type": "OBJECT",
                "properties": {
                    "location_name": {
                        "type": "STRING",
                        "description": "The specific location to fetch weather for.",
                        "enum": ["Inavalu", "VIT-AP", "Vijayawada", "Vizag"]
                    }
                },
                "required": ["location_name"]
            }
        }
    ]
}

model = genai.GenerativeModel(
    model_name="gemini-1.5-flash",
    tools=[weather_tool],
    system_instruction="You are Anuman.ai, an intelligent conversational weather assistant built for the Ministry of Earth Sciences. You help farmers, commuters, and citizens in India. Keep your answers concise, natural, and highly actionable (e.g., crop advice for farmers). Support Hindi and English."
)

async def process_gemini_chat(session_id: str, user_message: str, location_key: str = None) -> str:
    try:
        past_history = await get_chat_history(session_id)
        chat = model.start_chat(history=past_history if past_history else [])
        response = await chat.send_message_async(user_message)

        if response.function_call:
            fc = response.function_call
            if fc.name == "get_weather":
                location = fc.args["location_name"]
                weather_data = await get_weather(location_name=location)
                response = await chat.send_message_async(
                    [{
                        "function_response": {
                            "name": "get_weather",
                            "response": weather_data
                        }
                    }]
                )

        return response.text
    except Exception as e:
        print(f"[ERROR] Gemini Agent failed: {str(e)}")
        return "Sorry, I am facing some issues connecting to the weather servers right now. Please try again in a moment."