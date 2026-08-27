import os
# pyrefly: ignore [missing-import]
import google.generativeai as genai
from app.weather import get_weather

# Import DB function to get past context (Kartik ka function)
from app.database import get_chat_history 

# Configure SDK strictly using the environment variable
genai.configure(api_key=os.environ.get("GEMINI_API_KEY", ""))

# Define get_weather as a tool with strict Enum constraint
weather_tool = genai.types.Tool(
    function_declarations=[
        genai.types.FunctionDeclaration(
            name="get_weather",
            description="Fetches current weather and daily forecast.",
            parameters=genai.types.Schema(
                type=genai.types.Type.OBJECT,
                properties={
                    "location_name": genai.types.Schema(
                        type=genai.types.Type.STRING,
                        description="The specific location to fetch weather for.",
                        enum=["Inavalu", "VIT-AP", "Vijayawada", "Vizag"]
                    )
                },
                required=["location_name"]
            )
        )
    ]
)

# Initialize the model explicitly with a Persona (System Instruction)
model = genai.GenerativeModel(
    model_name="gemini-1.5-flash",
    tools=[weather_tool],
    system_instruction="You are Anuman.ai, an intelligent conversational weather assistant built for the Ministry of Earth Sciences. You help farmers, commuters, and citizens in India. Keep your answers concise, natural, and highly actionable (e.g., crop advice for farmers). Support Hindi and English."
)

# FIXED: Renamed to match Hemang's main.py and added session_id parameter
async def process_gemini_chat(session_id: str, user_message: str, location_key: str = None) -> str:
    """Starts/Resumes a chat session, processes tools, and returns the AI response."""
    try:
        # 1. Fetch previous chat history from DB so Gemini remembers context
        past_history = await get_chat_history(session_id)
        
        # 2. Start chat WITH history (fixes the amnesia bug)
        chat = model.start_chat(history=past_history if past_history else [])
        
        # 3. Send the new message
        response = await chat.send_message_async(user_message)

        # 4. Handle Function Calling (if Gemini decides to check weather)
        if response.function_call:
            fc = response.function_call
            
            if fc.name == "get_weather":
                # Extract arguments safely
                location = fc.args["location_name"]
                
                # Automatically execute your async Python function
                weather_data = await get_weather(location_name=location)
                
                # Return the JSON response back to the model so it can generate a final answer
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