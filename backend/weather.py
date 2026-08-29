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
    # Normalize the location string to match exact dictionary keys
    lookup_name = location_name
    if location_name.lower() in KEY_MAP:
        lookup_name = KEY_MAP[location_name.lower()]
        
    if lookup_name not in LOCATIONS:
        raise ValueError(f"Invalid location. Allowed: {', '.join(LOCATIONS.keys())}")

    lat, lon = LOCATIONS[lookup_name]
    url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current=temperature_2m,relative_humidity_2m,weather_code&daily=weather_code,temperature_2m_max,temperature_2m_min"

    try:
        async with httpx.AsyncClient() as client:
            res = await client.get(url)
            res.raise_for_status()
            data = res.json()

            return {
                "location": lookup_name,
                "temperature": data.get("current", {}).get("temperature_2m"),
                "humidity": data.get("current", {}).get("relative_humidity_2m"),
                "conditions": data.get("current", {}).get("weather_code"),
                "daily_forecast": data.get("daily", {})
            }
    except httpx.HTTPError as e:
        return {"error": f"Failed to fetch weather: {str(e)}"}

# =====================================================================
# BRIDGE FUNCTION FOR HEMANG'S main.py (Dashboard API)
# =====================================================================
async def fetch_open_meteo_data(location_key: str) -> Dict[str, Any]:
    """Wrapper function so Hemang's main.py can call this without errors."""
    return await get_weather(location_key)