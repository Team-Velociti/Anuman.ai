import os
# pyrefly: ignore [missing-import]
import google.generativeai as genai
from app.weather import get_weather

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

# Initialize the model explicitly
model = genai.GenerativeModel(
    model_name="gemini-1.5-flash",
    tools=[weather_tool]
)

async def process_user_query(user_input: str) -> str:
    """Starts a chat session, processes tools, and returns the natural language response."""
    try:
        chat = model.start_chat()
        response = await chat.send_message_async(user_input)

        if response.function_call:
            fc = response.function_call
            
            if fc.name == "get_weather":
                # Extract arguments safely
                location = fc.args["location_name"]
                
                # Automatically execute the async Python function
                weather_data = await get_weather(location_name=location)
                
                # Return the JSON response to the model
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
        return f"Error processing query: {str(e)}"
