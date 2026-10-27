from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List, Optional, Set

import httpx

from .china_cities import PROVINCE_CITIES, PROVINCE_OPTIONS
from .config import Settings
from .weather import city_from_result, descriptor, number


logger = logging.getLogger(__name__)

CONDITION_CODES: Dict[str, Set[int]] = {
    "晴朗": {0, 1},
    "多云": {2},
    "阴天": {3},
    "下雨": {51, 53, 55, 56, 57, 61, 63, 65, 66, 67, 80, 81, 82},
    "下雪": {71, 73, 75, 77, 85, 86},
    "雾": {45, 48},
    "雷雨": {95, 96, 99},
}
CONDITION_OPTIONS = tuple(CONDITION_CODES.keys())
CURRENT_FIELDS = ",".join([
    "temperature_2m",
    "relative_humidity_2m",
    "apparent_temperature",
    "is_day",
    "precipitation",
    "weather_code",
    "cloud_cover",
    "pressure_msl",
    "wind_speed_10m",
    "wind_direction_10m",
])


class ProvinceWeatherUnavailableError(RuntimeError):
    """Raised when none of the cities could be queried from the provider."""


def condition_category(code: Optional[int]) -> Optional[str]:
    if code is None:
        return None
    for category, codes in CONDITION_CODES.items():
        if code in codes:
            return category
    return None


def valid_province(province: str) -> bool:
    return province.strip() in PROVINCE_OPTIONS


def valid_condition(condition: str) -> bool:
    return condition.strip() in CONDITION_OPTIONS


def filter_city_results(results: List[Dict[str, Any]], condition: str) -> List[Dict[str, Any]]:
    return [item for item in results if item.get("condition_category") == condition]


async def _fetch_city_current(
    client: httpx.AsyncClient,
    province: str,
    city: str,
    settings: Settings,
) -> Dict[str, Any]:
    geocode_response = await client.get(
        settings.open_meteo_geocoding_url,
        params={
            "name": city,
            "count": 5,
            "language": "zh",
            "countryCode": "CN",
            "format": "json",
        },
    )
    geocode_response.raise_for_status()
    results = geocode_response.json().get("results", [])
    result = next(
        (item for item in results if item.get("country_code", "").upper() == "CN"),
        None,
    )
    if result is None:
        raise LookupError(f"没有找到“{city}”对应的中国城市")

    location = city_from_result(result)
    forecast_response = await client.get(
        settings.open_meteo_forecast_url,
        params={
            "latitude": location["latitude"],
            "longitude": location["longitude"],
            "current": CURRENT_FIELDS,
            "timezone": "auto",
            "temperature_unit": "celsius",
            "wind_speed_unit": "kmh",
            "precipitation_unit": "mm",
        },
    )
    forecast_response.raise_for_status()
    current = forecast_response.json().get("current", {})
    code = current.get("weather_code")
    return {
        "city_key": location["city_key"],
        "province": province,
        "name": location.get("name") or city,
        "country": location.get("country", "中国"),
        "temperature": number(current.get("temperature_2m")),
        "feels_like": number(current.get("apparent_temperature")),
        "humidity": current.get("relative_humidity_2m"),
        "wind_speed": number(current.get("wind_speed_10m")),
        "wind_direction": current.get("wind_direction_10m"),
        "cloud_cover": current.get("cloud_cover"),
        "time": current.get("time"),
        "weather_code": code,
        "condition": descriptor(code, current.get("is_day", 1)),
        "condition_category": condition_category(code),
    }


async def fetch_province_weather(
    province: str,
    condition: str,
    settings: Settings,
) -> Dict[str, Any]:
    province = province.strip()
    condition = condition.strip()
    if not valid_province(province):
        raise LookupError(f"暂不支持省份“{province}”")
    if not valid_condition(condition):
        raise LookupError(f"暂不支持天气状态“{condition}”")

    cities = PROVINCE_CITIES[province]
    timeout = httpx.Timeout(15.0, connect=8.0)
    semaphore = asyncio.Semaphore(5)

    async with httpx.AsyncClient(timeout=timeout, headers={"User-Agent": "WeatherAtlas/1.0"}) as client:
        async def fetch_one(city: str) -> Optional[Dict[str, Any]]:
            async with semaphore:
                try:
                    return await _fetch_city_current(client, province, city, settings)
                except (httpx.HTTPError, LookupError, ValueError) as error:
                    logger.warning("省份天气查询失败 province=%s city=%s reason=%s", province, city, error)
                    return None

        results: List[Optional[Dict[str, Any]]] = await asyncio.gather(
            *(fetch_one(city) for city in cities)
        )

    valid_results = [item for item in results if item is not None]
    if not valid_results:
        raise ProvinceWeatherUnavailableError(f"暂时无法获取“{province}”的天气数据")

    matched = filter_city_results(valid_results, condition)
    updated_times = [item["time"] for item in valid_results if item.get("time")]
    logger.info(
        "省份天气查询完成 province=%s condition=%s total=%s matched=%s failed=%s",
        province,
        condition,
        len(cities),
        len(matched),
        len(cities) - len(valid_results),
    )
    return {
        "province": province,
        "condition": condition,
        "total": len(cities),
        "matched_count": len(matched),
        "failed_count": len(cities) - len(valid_results),
        "updated_at": max(updated_times) if updated_times else None,
        "items": matched,
    }
