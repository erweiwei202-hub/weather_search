from __future__ import annotations

import hashlib
import logging
import secrets
from datetime import datetime, timedelta, timezone
from threading import Lock
from typing import Any, Optional
from uuid import uuid4

from pymongo import DESCENDING, MongoClient
from pymongo.errors import DuplicateKeyError, PyMongoError

from .config import Settings


logger = logging.getLogger(__name__)


class CityStore:
    """MongoDB-backed city popularity store with an in-memory fallback."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.client: Optional[MongoClient] = None
        self.collection = None
        self.user_collection = None
        self.connected = False
        self._memory: dict[str, dict[str, Any]] = {}
        self._user_memory: dict[str, dict[str, dict[str, Any]]] = {}
        self._lock = Lock()

    def connect(self) -> None:
        client: Optional[MongoClient] = None
        try:
            client = MongoClient(self.settings.mongo_url, serverSelectionTimeoutMS=1800)
            client.admin.command("ping")
            database = client[self.settings.mongo_db]
            collection = database["cities"]
            user_collection = database["user_city_history"]
            collection.create_index("city_key", unique=True)
            collection.create_index([("query_count", DESCENDING), ("last_queried_at", DESCENDING)])
            user_collection.create_index([("user_id", 1), ("city_key", 1)], unique=True)
            user_collection.create_index(
                [("user_id", 1), ("query_count", DESCENDING), ("last_queried_at", DESCENDING)]
            )
            self.client = client
            self.collection = collection
            self.user_collection = user_collection
            self.connected = True
        except PyMongoError as error:
            if client is not None:
                client.close()
            self.client = None
            self.collection = None
            self.user_collection = None
            self.connected = False
            logger.warning("MongoDB 连接失败，将使用内存存储 reason=%s", error)
        else:
            logger.info("MongoDB 连接成功 database=%s", self.settings.mongo_db)

    def close(self) -> None:
        if self.client is not None:
            self.client.close()

    def record_city(self, city: dict[str, Any], user_id: Optional[str] = None) -> None:
        now = datetime.now(timezone.utc)
        logger.info(
            "记录常查城市 city=%s user_id=%s storage=%s",
            city["name"],
            user_id or "anonymous",
            "mongodb"
            if (self.user_collection if user_id is not None else self.collection) is not None
            else "memory",
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
        if user_id is not None and self.user_collection is not None:
            document["user_id"] = user_id
            try:
                self.user_collection.update_one(
                    {"user_id": user_id, "city_key": city["city_key"]},
                    {
                        "$set": document,
                        "$inc": {"query_count": 1},
                        "$setOnInsert": {"created_at": now},
                    },
                    upsert=True,
                )
                return
            except PyMongoError as error:
                self.connected = False
                logger.warning("MongoDB 用户城市写入失败，将切换到内存存储 reason=%s", error)

        if user_id is None and self.collection is not None:
            try:
                self.collection.update_one(
                    {"city_key": city["city_key"]},
                    {
                        "$set": document,
                        "$inc": {"query_count": 1},
                        "$setOnInsert": {"created_at": now},
                    },
                    upsert=True,
                )
                return
            except PyMongoError as error:
                self.connected = False
                logger.warning("MongoDB 写入失败，将切换到内存存储 reason=%s", error)

        with self._lock:
            if user_id is None:
                existing = self._memory.get(city["city_key"], {})
                self._memory[city["city_key"]] = {
                    **existing,
                    **document,
                    "query_count": existing.get("query_count", 0) + 1,
                }
            else:
                user_cities = self._user_memory.setdefault(user_id, {})
                existing = user_cities.get(city["city_key"], {})
                user_cities[city["city_key"]] = {
                    **existing,
                    **document,
                    "user_id": user_id,
                    "query_count": existing.get("query_count", 0) + 1,
                }

    def popular(self, limit: int = 6, user_id: Optional[str] = None) -> list[dict[str, Any]]:
        collection = self.user_collection if user_id is not None else self.collection
        if collection is not None:
            try:
                query = {"user_id": user_id} if user_id is not None else {}
                documents = collection.find(
                    query,
                    {
                        "_id": 0,
                        "city_key": 1,
                        "name": 1,
                        "country": 1,
                        "country_code": 1,
                        "admin1": 1,
                        "latitude": 1,
                        "longitude": 1,
                        "timezone": 1,
                        "query_count": 1,
                    },
                ).sort([("query_count", DESCENDING), ("last_queried_at", DESCENDING)]).limit(limit)
                return [self._serialize(document) for document in documents]
            except PyMongoError:
                self.connected = False

        with self._lock:
            source = self._user_memory.get(user_id, {}) if user_id is not None else self._memory
            documents = sorted(source.values(), key=lambda item: item.get("query_count", 0), reverse=True)
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


class AuthStore:
    """MongoDB-backed users and sessions with an in-memory fallback."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.client: Optional[MongoClient] = None
        self.users = None
        self.sessions = None
        self.connected = False
        self._users: dict[str, dict[str, Any]] = {}
        self._sessions: dict[str, dict[str, Any]] = {}
        self._lock = Lock()

    def connect(self) -> None:
        client: Optional[MongoClient] = None
        try:
            client = MongoClient(self.settings.mongo_url, serverSelectionTimeoutMS=1800)
            client.admin.command("ping")
            database = client[self.settings.mongo_db]
            users = database["users"]
            sessions = database["sessions"]
            users.create_index("user_id", unique=True)
            users.create_index("username", unique=True)
            sessions.create_index("token_hash", unique=True)
            sessions.create_index("expires_at", expireAfterSeconds=0)
            self.client = client
            self.users = users
            self.sessions = sessions
            self.connected = True
        except PyMongoError as error:
            if client is not None:
                client.close()
            self.client = None
            self.users = None
            self.sessions = None
            self.connected = False
            logger.warning("MongoDB 认证存储连接失败，将使用内存存储 reason=%s", error)
        else:
            logger.info("MongoDB 认证存储连接成功 database=%s", self.settings.mongo_db)

    def close(self) -> None:
        if self.client is not None:
            self.client.close()

    def register_user(self, username: str, password_hash: str) -> Optional[dict[str, Any]]:
        now = datetime.now(timezone.utc)
        user = {
            "user_id": uuid4().hex,
            "username": username,
            "password_hash": password_hash,
            "created_at": now,
            "last_login_at": now,
            "last_city": None,
            "status": "active",
        }
        if self.users is not None:
            try:
                self.users.insert_one(user)
            except DuplicateKeyError:
                return None
            return self._public_user(user)

        with self._lock:
            if any(item["username"] == username for item in self._users.values()):
                return None
            self._users[user["user_id"]] = user
            return self._public_user(user)

    def find_user(self, username: str) -> Optional[dict[str, Any]]:
        if self.users is not None:
            document = self.users.find_one({"username": username, "status": "active"})
            return self._public_user(document, include_password=True) if document else None

        with self._lock:
            for user in self._users.values():
                if user["username"] == username and user.get("status") == "active":
                    return self._public_user(user, include_password=True)
        return None

    def update_last_login(self, user_id: str) -> None:
        now = datetime.now(timezone.utc)
        if self.users is not None:
            self.users.update_one({"user_id": user_id}, {"$set": {"last_login_at": now}})
            return
        with self._lock:
            if user_id in self._users:
                self._users[user_id]["last_login_at"] = now

    def update_last_city(self, user_id: str, city: dict[str, Any]) -> None:
        last_city = {
            "city_key": city.get("city_key", ""),
            "name": city.get("name", ""),
            "country": city.get("country", ""),
            "country_code": city.get("country_code", ""),
            "admin1": city.get("admin1", ""),
            "latitude": city.get("latitude"),
            "longitude": city.get("longitude"),
            "timezone": city.get("timezone", "auto"),
        }
        if self.users is not None:
            self.users.update_one({"user_id": user_id}, {"$set": {"last_city": last_city}})
            return
        with self._lock:
            if user_id in self._users:
                self._users[user_id]["last_city"] = last_city

    def get_last_city(self, user_id: str) -> Optional[dict[str, Any]]:
        if self.users is not None:
            document = self.users.find_one({"user_id": user_id}, {"_id": 0, "last_city": 1})
            return document.get("last_city") if document else None
        with self._lock:
            city = self._users.get(user_id, {}).get("last_city")
            return dict(city) if city else None

    def create_session(self, user_id: str, ttl_days: int) -> str:
        raw_token = secrets.token_urlsafe(32)
        token_hash = self._hash_token(raw_token)
        now = datetime.now(timezone.utc)
        document = {
            "token_hash": token_hash,
            "user_id": user_id,
            "created_at": now,
            "expires_at": now + timedelta(days=ttl_days),
        }
        if self.sessions is not None:
            self.sessions.insert_one(document)
        else:
            with self._lock:
                self._sessions[token_hash] = document
        return raw_token

    def get_user_by_session(self, raw_token: str) -> Optional[dict[str, Any]]:
        token_hash = self._hash_token(raw_token)
        now = datetime.now(timezone.utc)
        if self.sessions is not None:
            session = self.sessions.find_one({"token_hash": token_hash, "expires_at": {"$gt": now}})
            if session is None:
                return None
            user = self.users.find_one({"user_id": session["user_id"], "status": "active"})
            return self._public_user(user) if user else None

        with self._lock:
            session = self._sessions.get(token_hash)
            if session is None or session["expires_at"] <= now:
                return None
            user = self._users.get(session["user_id"])
            return self._public_user(user) if user and user.get("status") == "active" else None

    def delete_session(self, raw_token: str) -> None:
        token_hash = self._hash_token(raw_token)
        if self.sessions is not None:
            self.sessions.delete_one({"token_hash": token_hash})
            return
        with self._lock:
            self._sessions.pop(token_hash, None)

    @staticmethod
    def _hash_token(raw_token: str) -> str:
        return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()

    @staticmethod
    def _public_user(
        document: Optional[dict[str, Any]], include_password: bool = False
    ) -> Optional[dict[str, Any]]:
        if document is None:
            return None
        user = {
            "user_id": document["user_id"],
            "username": document["username"],
        }
        if include_password:
            user["password_hash"] = document["password_hash"]
        return user
