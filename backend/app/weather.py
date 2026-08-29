import httpx
from typing import Any, Dict

LOCATIONS: Dict[str, tuple[float, float]] = {
    "Inavalu": (16.5022, 80.5222),
    "VIT-AP": (16.4971, 80.5086),
    "Vijayawada": (16.5062, 80.6480),
    "Vizag": (17.6868, 83.2185)
}

# Helper mapping to handle inputs from Frontend/Hemang vs Gemini
KEY_MAP = {
    "guntur": "Inavalu",
    "inavalu": "Inavalu",
    "vit_ap": "VIT-AP",
    "vit-ap": "VIT-AP",
    "vijayawada": "Vijayawada",
    "vizag": "Vizag"
}

async def get_weather(location_name: str) -> Dict[str, Any]:
    lookup_name = location_name.strip()
    if lookup_name.lower() in KEY_MAP:
        lookup_name = KEY_MAP[lookup_name.lower()]
        
    if lookup_name not in LOCATIONS:
        lookup_name = "VIT-AP" # Default fallback if AI hallucinates a random name

    lat, lon = LOCATIONS[lookup_name]
    url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current=temperature_2m,relative_humidity_2m,weather_code&daily=weather_code,temperature_2m_max,temperature_2m_min"

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            res = await client.get(url)
            res.raise_for_status()
            data = res.json()

            return {
                "location": lookup_name,
                "temperature": data.get("current", {}).get("temperature_2m", 30),
                "humidity": data.get("current", {}).get("relative_humidity_2m", 70),
                "conditions": data.get("current", {}).get("weather_code", 0),
                "daily_forecast": data.get("daily", {})
            }
    except Exception as e:
        print(f"[WEATHER ERROR] {str(e)}")
        # Fallback safe dictionary so AI never crashes
        return {
            "location": lookup_name,
            "temperature": 32.0,
            "humidity": 65,
            "conditions": 1,
            "daily_forecast": {}
        }

# =====================================================================
# BRIDGE FUNCTION FOR HEMANG'S main.py (Dashboard API)
# =====================================================================
async def fetch_open_meteo_data(location_key: str) -> Dict[str, Any]:
    """Wrapper function so Hemang's main.py can call this without errors."""
    return await get_weather(location_key)