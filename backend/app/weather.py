import os
import time
import httpx
from typing import Any, Dict, Union

# In-memory cache: { "city_name_lower": { "data": {...}, "timestamp": float } }
_weather_cache: Dict[str, Dict[str, Any]] = {}
_CACHE_TTL = 900       # 15 minutes — fresh cache window
_CACHE_MAX_AGE = 36000 # 10 hours — stale cache + GC threshold

_HEADERS = {"User-Agent": "AnumanAI-Hackathon-Project/1.0"}

# Optional fallback API keys (loaded from .env)
WEATHERAPI_KEY = os.environ.get("WEATHERAPI_KEY", "")
OPENWEATHER_API_KEY = os.environ.get("OPENWEATHER_API_KEY", "")


def _garbage_collect_cache():
    """Delete cache entries older than 10 hours to prevent memory leaks."""
    now = time.time()
    expired_keys = [k for k, v in _weather_cache.items() if (now - v["timestamp"]) > _CACHE_MAX_AGE]
    for k in expired_keys:
        del _weather_cache[k]
    if expired_keys:
        print(f"[CACHE GC] Evicted {len(expired_keys)} stale entries: {expired_keys}")


async def _try_open_meteo(client: httpx.AsyncClient, lookup_name: str) -> Dict[str, Any] | None:
    """Tier 1: Open-Meteo with GFS NWP model."""
    try:
        geo_url = f"https://geocoding-api.open-meteo.com/v1/search?name={lookup_name}&count=1&language=en&format=json"
        geo_res = await client.get(geo_url)
        geo_res.raise_for_status()
        geo_data = geo_res.json()

        if not ("results" in geo_data and len(geo_data["results"]) > 0):
            return None

        lat = geo_data["results"][0]["latitude"]
        lon = geo_data["results"][0]["longitude"]
        resolved_name = geo_data["results"][0].get("name", lookup_name)

        url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current=temperature_2m,relative_humidity_2m,weather_code&timezone=auto&models=gfs_seamless"
        res = await client.get(url)
        res.raise_for_status()
        data = res.json()

        return {
            "location": resolved_name,
            "temperature": data.get("current", {}).get("temperature_2m"),
            "humidity": data.get("current", {}).get("relative_humidity_2m"),
            "conditions": data.get("current", {}).get("weather_code"),
            "source": "open-meteo"
        }
    except Exception as e:
        print(f"[TIER 1 FAIL] Open-Meteo error: {e}")
        return None


async def _try_weatherapi(client: httpx.AsyncClient, lookup_name: str) -> Dict[str, Any] | None:
    """Tier 2: WeatherAPI.com fallback."""
    if not WEATHERAPI_KEY:
        return None
    try:
        url = f"https://api.weatherapi.com/v1/current.json?key={WEATHERAPI_KEY}&q={lookup_name}&aqi=no"
        res = await client.get(url)
        res.raise_for_status()
        data = res.json()
        current = data.get("current", {})

        return {
            "location": data.get("location", {}).get("name", lookup_name),
            "temperature": current.get("temp_c"),
            "humidity": current.get("humidity"),
            "conditions": current.get("condition", {}).get("text", "Unknown"),
            "source": "weatherapi"
        }
    except Exception as e:
        print(f"[TIER 2 FAIL] WeatherAPI error: {e}")
        return None


async def _try_openweathermap(client: httpx.AsyncClient, lookup_name: str) -> Dict[str, Any] | None:
    """Tier 3: OpenWeatherMap fallback."""
    if not OPENWEATHER_API_KEY:
        return None
    try:
        url = f"https://api.openweathermap.org/data/2.5/weather?q={lookup_name}&appid={OPENWEATHER_API_KEY}&units=metric"
        res = await client.get(url)
        res.raise_for_status()
        data = res.json()

        return {
            "location": data.get("name", lookup_name),
            "temperature": data.get("main", {}).get("temp"),
            "humidity": data.get("main", {}).get("humidity"),
            "conditions": data.get("weather", [{}])[0].get("description", "Unknown"),
            "source": "openweathermap"
        }
    except Exception as e:
        print(f"[TIER 3 FAIL] OpenWeatherMap error: {e}")
        return None


async def get_weather(location_name: str) -> Dict[str, Any]:
    lookup_name = location_name.strip()
    cache_key = lookup_name.lower()

    # 1. Fresh cache check (< 15 minutes)
    if cache_key in _weather_cache:
        cached = _weather_cache[cache_key]
        if (time.time() - cached["timestamp"]) < _CACHE_TTL:
            print(f"[CACHE HIT] Returning cached weather for '{lookup_name}'")
            return cached["data"]

    # 2. Garbage collect old entries before writing new ones
    _garbage_collect_cache()

    # 3. Try the 3-tier fallback chain
    result = None
    try:
        async with httpx.AsyncClient(timeout=10.0, headers=_HEADERS) as client:
            result = await _try_open_meteo(client, lookup_name)
            if not result:
                print(f"[FALLBACK] Tier 1 failed for '{lookup_name}', trying WeatherAPI...")
                result = await _try_weatherapi(client, lookup_name)
            if not result:
                print(f"[FALLBACK] Tier 2 failed for '{lookup_name}', trying OpenWeatherMap...")
                result = await _try_openweathermap(client, lookup_name)
    except Exception as e:
        print(f"[WEATHER FATAL] Client-level error: {e}")

    # 4. If we got live data, cache it and return
    if result:
        _weather_cache[cache_key] = {"data": result, "timestamp": time.time()}
        return result

    # 5. STALE CACHE DEGRADATION: All 3 providers failed — try returning old cached data (< 10 hours)
    if cache_key in _weather_cache:
        stale = _weather_cache[cache_key]
        if (time.time() - stale["timestamp"]) < _CACHE_MAX_AGE:
            print(f"[STALE CACHE] All APIs down. Returning stale data for '{lookup_name}'")
            stale_data = dict(stale["data"])  # shallow copy
            stale_data["system_warning"] = "Live APIs down. Showing last known cached data."
            return stale_data

    # 6. Absolute last resort — no data anywhere
    print(f"[TOTAL FAILURE] No data available for '{lookup_name}'")
    return {"error": "All weather APIs are down and no cached data is available."}


# =====================================================================
# BRIDGE FUNCTION FOR HEMANG'S main.py (Dashboard API)
# =====================================================================
async def fetch_open_meteo_data(location_key: str) -> Dict[str, Any]:
    """Wrapper function so Hemang's main.py can call this without errors."""
    return await get_weather(location_key)


async def get_current_weather_by_coords(lat: float, lon: float) -> Dict[str, Any]:
    """
    Calls OpenWeatherMap using lat/lon for the top-bar UI widget.
    Falls back to WeatherAPI if OpenWeatherMap key is missing or fails (e.g. inactive key).
    Returns None on any failure so the endpoint can return a 500.
    """
    async with httpx.AsyncClient(timeout=8.0, headers=_HEADERS) as client:
        # --- ATTEMPT 1: OpenWeatherMap ---
        if OPENWEATHER_API_KEY:
            try:
                url = f"https://api.openweathermap.org/data/2.5/weather?lat={lat}&lon={lon}&appid={OPENWEATHER_API_KEY}&units=metric"
                res = await client.get(url)
                if res.status_code == 200:
                    data = res.json()
                    wind_mps = data.get("wind", {}).get("speed", 0)
                    visibility_m = data.get("visibility", 8000)
                    return {
                        "location": data.get("name", "Unknown"),
                        "region": "",
                        "temp_c": round(data.get("main", {}).get("temp", 0)),
                        "humidity": data.get("main", {}).get("humidity", 0),
                        "wind_kph": round(wind_mps * 3.6, 1),
                        "visibility_km": round(visibility_m / 1000, 1),
                        "condition": data.get("weather", [{}])[0].get("description", "Unknown").title(),
                        "source": "openweathermap"
                    }
                else:
                    print(f"[TOPBAR] OpenWeather failed with {res.status_code}. Falling back...")
            except Exception as e:
                print(f"[TOPBAR] OpenWeather crashed: {e}. Falling back...")
        else:
            print("[TOPBAR] OPENWEATHER_API_KEY not set. Falling back to WeatherAPI...")

        # --- ATTEMPT 2: WeatherAPI ---
        if WEATHERAPI_KEY:
            try:
                url = f"https://api.weatherapi.com/v1/current.json?key={WEATHERAPI_KEY}&q={lat},{lon}&aqi=no"
                res = await client.get(url)
                if res.status_code == 200:
                    data = res.json()
                    loc = data.get("location", {})
                    cur = data.get("current", {})
                    return {
                        "location": loc.get("name", "Unknown"),
                        "region": loc.get("region", ""),
                        "temp_c": cur.get("temp_c"),
                        "humidity": cur.get("humidity"),
                        "wind_kph": cur.get("wind_kph"),
                        "visibility_km": cur.get("vis_km"),
                        "condition": cur.get("condition", {}).get("text", "Unknown"),
                        "source": "weatherapi"
                    }
            except Exception as e:
                print(f"[TOPBAR] WeatherAPI crashed: {e}")

    return None


async def get_rain_report_by_coords(lat: float, lon: float) -> Dict[str, Any]:
    """
    Fetches 7 days past and 7 days future precipitation data.
    """
    url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&daily=precipitation_sum,precipitation_probability_max,weather_code&past_days=7&forecast_days=7&timezone=auto"
    try:
        async with httpx.AsyncClient(timeout=10.0, headers=_HEADERS) as client:
            res = await client.get(url)
            res.raise_for_status()
            data = res.json()
            
            daily = data.get("daily", {})
            dates = daily.get("time", [])
            rain_sums = daily.get("precipitation_sum", [])
            rain_probs = daily.get("precipitation_probability_max", [])
            weather_codes = daily.get("weather_code", [])
            
            report = []
            for i in range(len(dates)):
                report.append({
                    "date": dates[i],
                    "rain_mm": rain_sums[i] if rain_sums and i < len(rain_sums) else 0,
                    "rain_prob": rain_probs[i] if rain_probs and i < len(rain_probs) else 0,
                    "code": weather_codes[i] if weather_codes and i < len(weather_codes) else 0
                })
                
            return {"status": "success", "report": report}
    except Exception as e:
        print(f"[REPORT ERROR] {e}")
        return {"status": "error", "message": str(e)}