import time
import httpx
from typing import Any, Dict, Union

# In-memory cache: { "city_name_lower": { "data": {...}, "timestamp": float } }
_weather_cache: Dict[str, Dict[str, Any]] = {}
_CACHE_TTL = 900  # 15 minutes in seconds

_HEADERS = {"User-Agent": "AnumanAI-Hackathon-Project/1.0"}

async def get_weather(location_name: str) -> Union[Dict[str, Any], str]:
    lookup_name = location_name.strip()
    cache_key = lookup_name.lower()

    # 1. Check cache first
    if cache_key in _weather_cache:
        cached = _weather_cache[cache_key]
        if (time.time() - cached["timestamp"]) < _CACHE_TTL:
            print(f"[CACHE HIT] Returning cached weather for '{lookup_name}'")
            return cached["data"]

    try:
        async with httpx.AsyncClient(timeout=10.0, headers=_HEADERS) as client:
            # 2. Geocode the location name to get lat, lon
            geo_url = f"https://geocoding-api.open-meteo.com/v1/search?name={lookup_name}&count=1&language=en&format=json"
            geo_res = await client.get(geo_url)
            geo_res.raise_for_status()
            geo_data = geo_res.json()

            if not ("results" in geo_data and len(geo_data["results"]) > 0):
                return "ERROR: LIVE_DATA_UNAVAILABLE"

            lat = geo_data["results"][0]["latitude"]
            lon = geo_data["results"][0]["longitude"]
            resolved_name = geo_data["results"][0].get("name", lookup_name)

            # 3. Fetch weather with GFS NWP model and auto timezone
            url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current=temperature_2m,relative_humidity_2m,weather_code&timezone=auto&models=gfs_seamless"

            res = await client.get(url)
            res.raise_for_status()
            data = res.json()

            result = {
                "location": resolved_name,
                "temperature": data.get("current", {}).get("temperature_2m"),
                "humidity": data.get("current", {}).get("relative_humidity_2m"),
                "conditions": data.get("current", {}).get("weather_code")
            }

            # 4. Store in cache
            _weather_cache[cache_key] = {"data": result, "timestamp": time.time()}

            return result

    except httpx.HTTPStatusError as e:
        print(f"[WEATHER HTTP ERROR] {e.response.status_code}: {str(e)}")
        return "ERROR: WEATHER_SERVER_OVERLOADED"
    except Exception as e:
        print(f"[WEATHER ERROR] {str(e)}")
        return "ERROR: LIVE_DATA_UNAVAILABLE"

# =====================================================================
# BRIDGE FUNCTION FOR HEMANG'S main.py (Dashboard API)
# =====================================================================
async def fetch_open_meteo_data(location_key: str) -> Union[Dict[str, Any], str]:
    """Wrapper function so Hemang's main.py can call this without errors."""
    return await get_weather(location_key)