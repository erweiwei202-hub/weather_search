from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Weather Atlas API"
    environment: str = "development"
    mongo_url: str = "mongodb://localhost:27017"
    mongo_db: str = "weather_atlas"
    frontend_origin: str = "http://localhost:5173"
    session_cookie_name: str = "weather_session"
    session_ttl_days: int = 30
    ai_config_encryption_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    news_rss_url: str = "https://news.google.com/rss/search"
    open_meteo_forecast_url: str = "https://api.open-meteo.com/v1/forecast"
    open_meteo_geocoding_url: str = "https://geocoding-api.open-meteo.com/v1/search"

    model_config = SettingsConfigDict(
        env_file=("backend/.env", ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
