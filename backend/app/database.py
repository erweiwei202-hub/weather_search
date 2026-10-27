from __future__ import annotations

import logging
from datetime import datetime, timezone
from threading import Lock
from typing import Any, Optional

from pymongo import DESCENDING, MongoClient
from pymongo.errors import PyMongoError

from .config import Settings


logger = logging.getLogger(__name__)


class CityStore:
    """MongoDB-backed city popularity store with a safe in-memory fallback for local UI work."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.client: Optional[MongoClient] = None
        self.collection = None
        self.connected = False
        self._memory: dict[str, dict[str, Any]] = {}
        self._lock = Lock()

    def connect(self) -> None:
        try:
            client = MongoClient(self.settings.mongo_url, serverSelectionTimeoutMS=1800)
            client.admin.command("ping")
            collection = client[self.settings.mongo_db]["cities"]
            collection.create_index("city_key", unique=True)
            collection.create_index([("query_count", DESCENDING), ("last_queried_at", DESCENDING)])
            self.client = client
            self.collection = collection
            self.connected = True
        except PyMongoError as error:
            self.client = None
            self.collection = None
            self.connected = False
            logger.warning("MongoDB 连接失败，将使用内存存储 reason=%s", error)
        else:
            logger.info("MongoDB 连接成功 database=%s", self.settings.mongo_db)

    def close(self) -> None:
        if self.client is not None:
            self.client.close()

    def record_city(self, city: dict[str, Any]) -> None:
        now = datetime.now(timezone.utc)
        logger.info(
            "记录常查城市 city=%s storage=%s",
            city["name"],
            "mongodb" if self.collection is not None else "memory",
        )
        document = {
            "city_key": city["city_key"],
            "name": city["name"],
            "country": city.get("country", ""),
            "country_code": city.get("country_code", ""),
            "admin1": city.get("admin1", ""),
            "latitude": city["latitude"],
            "longitude": city["longitude"],
            "timezone": city.get("timezone", "auto"),
            "last_queried_at": now,
        }
        if self.collection is not None:
            try:
                self.collection.update_one(
                    {"city_key": city["city_key"]},
                    {"$set": document, "$inc": {"query_count": 1}, "$setOnInsert": {"created_at": now}},
                    upsert=True,
                )
                return
            except PyMongoError as error:
                self.connected = False
                logger.warning("MongoDB 写入失败，将切换到内存存储 reason=%s", error)

        with self._lock:
            existing = self._memory.get(city["city_key"], {})
            self._memory[city["city_key"]] = {
                **existing,
                **document,
                "query_count": existing.get("query_count", 0) + 1,
            }

    def popular(self, limit: int = 6) -> list[dict[str, Any]]:
        if self.collection is not None:
            try:
                documents = self.collection.find(
                    {},
                    {"_id": 0, "city_key": 1, "name": 1, "country": 1, "country_code": 1, "admin1": 1,
                     "latitude": 1, "longitude": 1, "timezone": 1, "query_count": 1},
                ).sort([("query_count", DESCENDING), ("last_queried_at", DESCENDING)]).limit(limit)
                return [self._serialize(document) for document in documents]
            except PyMongoError:
                self.connected = False

        with self._lock:
            documents = sorted(self._memory.values(), key=lambda item: item.get("query_count", 0), reverse=True)
            return [self._serialize(document) for document in documents[:limit]]

    @staticmethod
    def _serialize(document: dict[str, Any]) -> dict[str, Any]:
        return {
            "city_key": document.get("city_key", ""),
            "name": document.get("name", ""),
            "country": document.get("country", ""),
            "country_code": document.get("country_code", ""),
            "admin1": document.get("admin1", ""),
            "latitude": document.get("latitude"),
            "longitude": document.get("longitude"),
            "timezone": document.get("timezone", "auto"),
            "query_count": document.get("query_count", 0),
        }
