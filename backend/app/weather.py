from __future__ import annotations

import logging
import re
from typing import Any, Dict, Iterable, Optional

import httpx
from pypinyin import lazy_pinyin

from .config import Settings


logger = logging.getLogger(__name__)


WEATHER_CODES: dict[int, tuple[str, str]] = {
    0: ("晴朗", "☀️"),
    1: ("基本晴朗", "🌤️"),
    2: ("局部多云", "⛅"),
    3: ("阴天", "☁️"),
    45: ("有雾", "🌫️"),
    48: ("雾凇", "🌫️"),
    51: ("小毛毛雨", "🌦️"),
    53: ("毛毛雨", "🌦️"),
    55: ("较强毛毛雨", "🌧️"),
    56: ("冻毛毛雨", "🌧️"),
    57: ("较强冻毛毛雨", "🌧️"),
    61: ("小雨", "🌦️"),
    63: ("中雨", "🌧️"),
    65: ("大雨", "🌧️"),
    66: ("冻雨", "🌧️"),
    67: ("强冻雨", "🌧️"),
    71: ("小雪", "🌨️"),
    73: ("中雪", "🌨️"),
    75: ("大雪", "❄️"),
    77: ("雪粒", "❄️"),
    80: ("阵雨", "🌦️"),
    81: ("中阵雨", "🌧️"),
    82: ("强阵雨", "⛈️"),
    85: ("阵雪", "🌨️"),
    86: ("强阵雪", "❄️"),
    95: ("雷雨", "⛈️"),
    96: ("雷雨伴冰雹", "⛈️"),
    99: ("强雷雨伴冰雹", "⛈️"),
}
CITY_SUFFIXES = ("特别行政区", "自治州", "地区", "盟", "市", "县", "区")


def descriptor(code: Optional[int], is_day: int = 1) -> dict[str, Any]:
    label, icon = WEATHER_CODES.get(code or 0, ("天气变化", "🌡️"))
    if not is_day and code in (0, 1):
        icon = "🌙"
    return {"code": code, "label": label, "icon": icon}


def number(value: Any, digits: int = 1) -> Optional[float]:
    if value is None:
        return None
    return round(float(value), digits)


def city_from_result(result: dict[str, Any]) -> dict[str, Any]:
    name = result.get("name", "未知城市")
    country = result.get("country", "")
    admin1 = result.get("admin1", "")
    city_key = f"{name}|{result.get('latitude')}|{result.get('longitude')}".lower()
    return {
        "city_key": city_key,
        "name": name,
        "country": country,
        "country_code": result.get("country_code", ""),
        "admin1": admin1,
        "latitude": result.get("latitude"),
        "longitude": result.get("longitude"),
        "timezone": result.get("timezone", "auto"),
        "population": result.get("population"),
    }


def city_query_candidates(city_query: str) -> list[str]:
    """Return Chinese and pinyin variants for geocoding providers."""
    query = re.sub(r"\s+", "", city_query.strip())
    candidates = [query]
    simplified = query
    for suffix in CITY_SUFFIXES:
        if simplified.endswith(suffix) and len(simplified) > len(suffix):
            simplified = simplified[: -len(suffix)]
            break
    if simplified and simplified != query:
        candidates.append(simplified)

    for variant in (query, simplified):
        pinyin = "".join(lazy_pinyin(variant))
        if pinyin and pinyin.lower() not in {item.lower() for item in candidates}:
            candidates.append(pinyin)
    return candidates


def choose_geocoding_result(results: Iterable[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    chinese_results = [
        item for item in results
        if item.get("country_code", "").upper() == "CN"
    ]
    if not chinese_results:
        return None

    city_results = [
        item for item in chinese_results
        if item.get("feature_code", "").startswith(("PPLA", "PPLC"))
    ]
    candidates = city_results or chinese_results
    return max(candidates, key=lambda item: item.get("population") or 0)


async def geocode_city(
    client: httpx.AsyncClient,
    city_query: str,
    settings: Settings,
) -> Dict[str, Any]:
    for candidate in city_query_candidates(city_query):
        geocode_response = await client.get(
            settings.open_meteo_geocoding_url,
            params={
                "name": candidate,
                "count": 10,
                "language": "zh",
                "countryCode": "CN",
                "format": "json",
            },
        )
        geocode_response.raise_for_status()
        location_result = choose_geocoding_result(geocode_response.json().get("results", []))
        if location_result is not None:
            logger.info("城市定位候选命中 query=%s candidate=%s", city_query, candidate)
            return location_result

    logger.warning("没有找到对应的中国城市 city=%s", city_query)
    raise LookupError(f"没有找到“{city_query}”对应的中国城市")


async def fetch_weather(city_query: str, settings: Settings) -> dict[str, Any]:
    timeout = httpx.Timeout(15.0, connect=8.0)
    logger.info("开始查询天气 city=%s", city_query)
    headers = {"User-Agent": "WeatherAtlas/1.0"}
    async with httpx.AsyncClient(timeout=timeout, headers=headers) as client:
        location_result = await geocode_city(client, city_query, settings)
        location = city_from_result(location_result)
        logger.info(
            "城市定位完成 query=%s location=%s latitude=%s longitude=%s",
            city_query,
            location["name"],
            location["latitude"],
            location["longitude"],
        )
        forecast_response = await client.get(
            settings.open_meteo_forecast_url,
            params={
                "latitude": location["latitude"],
                "longitude": location["longitude"],
                "current": ",".join([
                    "temperature_2m", "relative_humidity_2m", "apparent_temperature", "is_day",
                    "precipitation", "rain", "showers", "snowfall", "weather_code", "cloud_cover",
                    "pressure_msl", "wind_speed_10m", "wind_direction_10m",
                ]),
                "hourly": "temperature_2m,precipitation_probability,weather_code,relative_humidity_2m,wind_speed_10m",
                "daily": ",".join([
                    "weather_code", "temperature_2m_max", "temperature_2m_min", "precipitation_sum",
                    "precipitation_probability_max", "sunrise", "sunset", "wind_speed_10m_max", "uv_index_max",
                ]),
                "forecast_days": 7,
                "timezone": "auto",
                "temperature_unit": "celsius",
                "wind_speed_unit": "kmh",
                "precipitation_unit": "mm",
            },
        )
        forecast_response.raise_for_status()
        forecast = forecast_response.json()

    logger.info("天气数据获取完成 city=%s", location["name"])
    return build_response(location, forecast)


def build_response(location: dict[str, Any], forecast: dict[str, Any]) -> dict[str, Any]:
    current = forecast.get("current", {})
    current_units = forecast.get("current_units", {})
    current_code = current.get("weather_code")
    current_is_day = current.get("is_day", 1)
    hourly = forecast.get("hourly", {})
    daily = forecast.get("daily", {})

    hourly_times = hourly.get("time", [])
    start_index = 0
    if current.get("time") in hourly_times:
        start_index = hourly_times.index(current["time"])
    hours = []
    for index in range(start_index, min(start_index + 24, len(hourly_times))):
        code = hourly.get("weather_code", [None] * len(hourly_times))[index]
        hours.append({
            "time": hourly_times[index],
            "temperature": number(hourly.get("temperature_2m", [None] * len(hourly_times))[index]),
            "precipitation_probability": hourly.get("precipitation_probability", [None] * len(hourly_times))[index],
            "humidity": hourly.get("relative_humidity_2m", [None] * len(hourly_times))[index],
            "wind_speed": number(hourly.get("wind_speed_10m", [None] * len(hourly_times))[index]),
            "condition": descriptor(code, 1),
        })

    days = []
    day_times = daily.get("time", [])
    for index, day in enumerate(day_times):
        code = daily.get("weather_code", [None] * len(day_times))[index]
        days.append({
            "date": day,
            "temperature_max": number(daily.get("temperature_2m_max", [None] * len(day_times))[index]),
            "temperature_min": number(daily.get("temperature_2m_min", [None] * len(day_times))[index]),
            "precipitation": number(daily.get("precipitation_sum", [None] * len(day_times))[index]),
            "precipitation_probability": daily.get("precipitation_probability_max", [None] * len(day_times))[index],
            "sunrise": daily.get("sunrise", [None] * len(day_times))[index],
            "sunset": daily.get("sunset", [None] * len(day_times))[index],
            "wind_speed_max": number(daily.get("wind_speed_10m_max", [None] * len(day_times))[index]),
            "uv_index_max": number(daily.get("uv_index_max", [None] * len(day_times))[index]),
            "condition": descriptor(code, 1),
        })

    return {
        "location": location,
        "timezone": forecast.get("timezone", location.get("timezone", "auto")),
        "utc_offset_seconds": forecast.get("utc_offset_seconds", 0),
        "current": {
            "time": current.get("time"),
            "temperature": number(current.get("temperature_2m")),
            "feels_like": number(current.get("apparent_temperature")),
            "humidity": current.get("relative_humidity_2m"),
            "precipitation": number(current.get("precipitation")),
            "rain": number(current.get("rain")),
            "showers": number(current.get("showers")),
            "snowfall": number(current.get("snowfall")),
            "cloud_cover": current.get("cloud_cover"),
            "pressure": number(current.get("pressure_msl")),
            "wind_speed": number(current.get("wind_speed_10m")),
            "wind_direction": current.get("wind_direction_10m"),
            "is_day": current_is_day,
            "condition": descriptor(current_code, current_is_day),
            "units": {
                "temperature": current_units.get("temperature_2m", "°C"),
                "wind_speed": current_units.get("wind_speed_10m", "km/h"),
                "pressure": current_units.get("pressure_msl", "hPa"),
            },
        },
        "hourly": hours,
        "daily": days,
        "meta": {"provider": "Open-Meteo", "updated_at": current.get("time")},
    }
