from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Dict, Optional, Union

import httpx
from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from .assistant import (
    AssistantConfigurationError,
    AssistantUnavailableError,
    ask_weather_assistant,
)
from .auth import (
    clear_session_cookie,
    get_current_user,
    get_optional_user,
    hash_password,
    set_session_cookie,
    verify_password,
)
from .config import get_settings
from .china_cities import PROVINCE_CITIES, PROVINCE_OPTIONS
from .database import AuthStore, CityStore
from .news import NewsUnavailableError, fetch_city_news
from .province_weather import (
    CONDITION_OPTIONS,
    ProvinceWeatherUnavailableError,
    fetch_province_weather,
)
from .weather import fetch_weather


settings = get_settings()
city_store = CityStore(settings)
auth_store = AuthStore(settings)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    await asyncio.to_thread(city_store.connect)
    await asyncio.to_thread(auth_store.connect)
    logger.info(
        "应用启动完成 database=%s",
        "mongodb" if city_store.connected and auth_store.connected else "memory",
    )
    yield
    await asyncio.to_thread(auth_store.close)
    await asyncio.to_thread(city_store.close)
    logger.info("应用已关闭")


app = FastAPI(title=settings.app_name, version="1.0.0", lifespan=lifespan)
app.state.settings = settings
app.state.auth_store = auth_store
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin, "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class AuthRequest(BaseModel):
    username: str = Field(min_length=3, max_length=32)
    password: str = Field(min_length=8, max_length=128)


class AssistantMessage(BaseModel):
    role: str
    content: str = Field(min_length=1, max_length=2000)


class AssistantRequest(BaseModel):
    message: str = Field(min_length=1, max_length=1000)
    history: list[AssistantMessage] = Field(default_factory=list, max_length=8)


def public_user(user: dict) -> dict:
    return {"user_id": user["user_id"], "username": user["username"]}


async def create_login_session(response: Response, user_id: str) -> None:
    token = await asyncio.to_thread(auth_store.create_session, user_id, settings.session_ttl_days)
    set_session_cookie(response, settings, token)


@app.post("/api/auth/register", status_code=201)
async def register(payload: AuthRequest, response: Response) -> dict:
    username = payload.username.strip()
    if len(username) < 3:
        raise HTTPException(status_code=422, detail="用户名至少需要 3 个字符")

    password_hash = await asyncio.to_thread(hash_password, payload.password)
    user = await asyncio.to_thread(auth_store.register_user, username, password_hash)
    if user is None:
        raise HTTPException(status_code=409, detail="用户名已存在")

    await create_login_session(response, user["user_id"])
    logger.info("用户注册成功 username=%s", username)
    return {"user": public_user(user)}


@app.post("/api/auth/login")
async def login(payload: AuthRequest, response: Response) -> dict:
    username = payload.username.strip()
    user = await asyncio.to_thread(auth_store.find_user, username)
    if user is None or not await asyncio.to_thread(verify_password, payload.password, user["password_hash"]):
        logger.warning("用户登录失败 username=%s", username)
        raise HTTPException(status_code=401, detail="用户名或密码错误")

    await asyncio.to_thread(auth_store.update_last_login, user["user_id"])
    await create_login_session(response, user["user_id"])
    logger.info("用户登录成功 username=%s", username)
    return {"user": public_user(user)}


@app.get("/api/auth/me")
async def current_user(user: dict = Depends(get_current_user)) -> dict:
    return {"user": public_user(user)}


@app.post("/api/auth/logout")
async def logout(
    request: Request,
    response: Response,
    user: Optional[dict] = Depends(get_optional_user),
) -> dict:
    token = request.cookies.get(settings.session_cookie_name)
    if token:
        await asyncio.to_thread(auth_store.delete_session, token)
    if user is not None:
        logger.info("用户退出登录 username=%s", user["username"])
    clear_session_cookie(response, settings)
    return {"ok": True}


async def enrich_with_news(payload: dict) -> dict:
    try:
        payload["news"] = await fetch_city_news(payload["location"]["name"], settings)
        payload["news_status"] = "ok"
    except NewsUnavailableError:
        payload["news"] = []
        payload["news_status"] = "unavailable"
    return payload


@app.post("/api/assistant/chat")
async def assistant_chat(
    payload: AssistantRequest,
    user: dict = Depends(get_current_user),
) -> dict:
    last_city = await asyncio.to_thread(auth_store.get_last_city, user["user_id"])
    if last_city is None:
        raise HTTPException(status_code=400, detail="请先查询一个城市，再向天气助手提问")

    try:
        weather_payload = await fetch_weather(last_city["name"], settings)
        try:
            today_news = await fetch_city_news(last_city["name"], settings)
        except NewsUnavailableError:
            today_news = []
        answer = await ask_weather_assistant(
            settings=settings,
            question=payload.message,
            city=last_city,
            weather=weather_payload,
            news=today_news,
            history=[item.model_dump() for item in payload.history],
        )
    except AssistantConfigurationError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    except AssistantUnavailableError as error:
        raise HTTPException(status_code=502, detail=str(error)) from error
    except (httpx.HTTPError, LookupError) as error:
        logger.exception("天气助手上下文获取失败 user_id=%s", user["user_id"])
        raise HTTPException(status_code=502, detail="天气助手暂时无法获取最新天气数据") from error

    return {
        "answer": answer,
        "city": last_city,
        "news": today_news,
    }


@app.get("/api/health")
async def health() -> Dict[str, Union[str, bool]]:
    return {
        "status": "ok",
        "database": "mongodb" if city_store.connected and auth_store.connected else "memory",
        "ai_configured": bool(settings.openai_api_key.strip() and settings.openai_model.strip()),
    }


@app.get("/api/weather")
async def weather(
    city: str = Query(..., min_length=2, max_length=80),
    user: Optional[dict] = Depends(get_optional_user),
) -> dict:
    city = city.strip()
    if not city:
        raise HTTPException(status_code=422, detail="请输入城市名称")
    logger.info("收到天气查询请求 city=%s", city)
    try:
        payload = await fetch_weather(city, settings)
        payload = await enrich_with_news(payload)
        user_id = user["user_id"] if user is not None else None
        await asyncio.to_thread(city_store.record_city, payload["location"], user_id)
        if user_id is not None:
            await asyncio.to_thread(auth_store.update_last_city, user_id, payload["location"])
        logger.info(
            "天气查询完成 city=%s location=%s user_id=%s",
            city,
            payload["location"]["name"],
            user_id or "anonymous",
        )
        return payload
    except LookupError as error:
        logger.warning("城市查询失败 city=%s reason=%s", city, error)
        raise HTTPException(status_code=404, detail=str(error)) from error
    except (httpx.HTTPError, ValueError) as error:
        logger.exception("天气服务请求失败 city=%s", city)
        raise HTTPException(status_code=502, detail="天气服务暂时不可用，请稍后重试") from error


@app.get("/api/cities")
async def popular_cities(
    limit: int = Query(6, ge=1, le=20),
    user: Optional[dict] = Depends(get_optional_user),
) -> dict:
    user_id = user["user_id"] if user is not None else None
    cities = await asyncio.to_thread(city_store.popular, limit, user_id)
    logger.info("读取常查城市 limit=%s count=%s user_id=%s", limit, len(cities), user_id or "anonymous")
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
