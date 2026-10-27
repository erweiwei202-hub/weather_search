from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Dict, Union

import httpx
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .china_cities import PROVINCE_CITIES, PROVINCE_OPTIONS
from .database import CityStore
from .province_weather import (
    CONDITION_OPTIONS,
    ProvinceWeatherUnavailableError,
    fetch_province_weather,
)
from .weather import fetch_weather


settings = get_settings()
city_store = CityStore(settings)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    await asyncio.to_thread(city_store.connect)
    logger.info(
        "应用启动完成 database=%s",
        "mongodb" if city_store.connected else "memory",
    )
    yield
    await asyncio.to_thread(city_store.close)
    logger.info("应用已关闭")


app = FastAPI(title=settings.app_name, version="1.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin, "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
async def health() -> Dict[str, Union[str, bool]]:
    return {"status": "ok", "database": "mongodb" if city_store.connected else "memory"}


@app.get("/api/weather")
async def weather(city: str = Query(..., min_length=2, max_length=80)) -> dict:
    city = city.strip()
    if not city:
        raise HTTPException(status_code=422, detail="请输入城市名称")
    logger.info("收到天气查询请求 city=%s", city)
    try:
        payload = await fetch_weather(city, settings)
        await asyncio.to_thread(city_store.record_city, payload["location"])
        logger.info(
            "天气查询完成 city=%s location=%s",
            city,
            payload["location"]["name"],
        )
        return payload
    except LookupError as error:
        logger.warning("城市查询失败 city=%s reason=%s", city, error)
        raise HTTPException(status_code=404, detail=str(error)) from error
    except (httpx.HTTPError, ValueError) as error:
        logger.exception("天气服务请求失败 city=%s", city)
        raise HTTPException(status_code=502, detail="天气服务暂时不可用，请稍后重试") from error


@app.get("/api/cities")
async def popular_cities(limit: int = Query(6, ge=1, le=20)) -> dict:
    cities = await asyncio.to_thread(city_store.popular, limit)
    logger.info("读取常查城市 limit=%s count=%s", limit, len(cities))
    return {"items": cities, "database": "mongodb" if city_store.connected else "memory"}


@app.get("/api/provinces")
async def provinces() -> dict:
    return {
        "items": [
            {"name": province, "city_count": len(PROVINCE_CITIES[province])}
            for province in PROVINCE_OPTIONS
        ],
        "conditions": list(CONDITION_OPTIONS),
    }


@app.get("/api/province-weather")
async def province_weather(
    province: str = Query(..., min_length=2, max_length=20),
    condition: str = Query(..., min_length=2, max_length=10),
) -> dict:
    logger.info("收到省份天气查询请求 province=%s condition=%s", province, condition)
    try:
        return await fetch_province_weather(province, condition, settings)
    except LookupError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    except ProvinceWeatherUnavailableError as error:
        logger.exception("省份天气服务不可用 province=%s condition=%s", province, condition)
        raise HTTPException(status_code=502, detail=str(error)) from error
