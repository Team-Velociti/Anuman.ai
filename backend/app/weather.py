import httpx
from typing import Any, Dict

LOCATIONS: Dict[str, tuple[float, float]] = {
    "Inavalu": (16.5022, 80.5222),
    "VIT-AP": (16.4971, 80.5086),
    "Vijayawada": (16.5062, 80.6480),
    "Vizag": (17.6868, 83.2185)
}

async def get_weather(location_name: str) -> Dict[str, Any]:
    if location_name not in LOCATIONS:
        raise ValueError(f"Invalid location. Allowed: {', '.join(LOCATIONS.keys())}")

    lat, lon = LOCATIONS[location_name]
    url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current=temperature_2m,relative_humidity_2m,weather_code&daily=weather_code,temperature_2m_max,temperature_2m_min"

    try:
        async with httpx.AsyncClient() as client:
            res = await client.get(url)
            res.raise_for_status()
            data = res.json()

            return {
                "location": location_name,
                "temperature": data.get("current", {}).get("temperature_2m"),
                "humidity": data.get("current", {}).get("relative_humidity_2m"),
                "conditions": data.get("current", {}).get("weather_code"),
                "daily_forecast": data.get("daily", {})
            }
    except httpx.HTTPError as e:
        return {"error": f"Failed to fetch weather: {str(e)}"}
