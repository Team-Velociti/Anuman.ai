import os
import google.generativeai as genai

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
                        "enum": ["Inavalu", "VIT-AP", "Vijayawada", "Guntur", "Vizag"]
                    }
                },
                "required": ["location_name"]
            }
        }
    ]
}

model = genai.GenerativeModel(
    model_name="gemini-3.6-flash", 
    tools=[weather_tool],
    system_instruction="You are Anuman.ai, an intelligent conversational weather assistant built for the Ministry of Earth Sciences. You help farmers, commuters, and citizens in India. Keep your answers concise, natural, and highly actionable. Support Hindi and English."
)

async def process_gemini_chat(session_id: str, user_message: str, location_key: str = None) -> str:
    try:
        # 1. Fetch History & Start Chat
        past_history = await get_chat_history(session_id)
        chat = model.start_chat(history=past_history if past_history else [])
        
        # 2. Send User Message
        response = await chat.send_message_async(user_message)

        # 3. Robust Tool Call Check
        try:
            return response.text
        except ValueError:
            pass # ValueError means Gemini returned a Function Call!

        # 4. Handle Function Call
        if response.candidates and response.candidates[0].content.parts:
            fc = response.candidates[0].content.parts[0].function_call
            function_name = fc.name
            
            if function_name in ["get_weather", "fetch_open_meteo_data"]:
                
                # Safely extract location using broad try-except
                location_arg = "VIT-AP"
                try:
                    location_arg = fc.args["location_name"]
                except Exception:
                    pass
                
                # Fetch Weather Data
                weather_data = await get_weather(location_name=location_arg)
                
                # MAGIC BULLET: Convert complex dictionary to string!
                # Gemini SDK crashes if you send raw nested JSON.
                weather_str = str(weather_data)
                
                # Send data back to Gemini
                second_response = await chat.send_message_async(
                    [{
                        "function_response": {
                            "name": function_name,
                            "response": {"result": weather_str}
                        }
                    }]
                )
                
                return second_response.text

    except Exception as e:
        print(f"[ERROR] Gemini Agent failed: {str(e)}")
        return "Sorry, I am facing some issues connecting to the weather servers right now. Please try again in a moment."