from __future__ import annotations

import unittest
from uuid import uuid4

from fastapi.testclient import TestClient

from backend.app.auth import hash_password, verify_password
from backend.app.config import Settings
from backend.app.database import AuthStore, CityStore
from backend.app.main import app


class AuthStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.settings = Settings(mongo_url="mongodb://localhost:27017")
        self.auth_store = AuthStore(self.settings)

    def test_password_hash_can_be_verified_without_storing_plaintext(self) -> None:
        password = "correct-horse-battery"
        password_hash = hash_password(password)

        self.assertNotEqual(password_hash, password)
        self.assertTrue(verify_password(password, password_hash))
        self.assertFalse(verify_password("wrong-password", password_hash))

    def test_session_resolves_to_user_and_can_be_deleted(self) -> None:
        user = self.auth_store.register_user("zhangsan", hash_password("password-123"))
        self.assertIsNotNone(user)
        assert user is not None

        token = self.auth_store.create_session(user["user_id"], ttl_days=1)
        resolved = self.auth_store.get_user_by_session(token)

        self.assertEqual(resolved["user_id"], user["user_id"])
        self.auth_store.delete_session(token)
        self.assertIsNone(self.auth_store.get_user_by_session(token))

    def test_last_city_is_saved_on_the_user(self) -> None:
        user = self.auth_store.register_user("zhangsan", hash_password("password-123"))
        assert user is not None
        city = {"city_key": "wenzhou", "name": "温州市", "admin1": "浙江省"}

        self.auth_store.update_last_city(user["user_id"], city)

        self.assertEqual(self.auth_store.get_last_city(user["user_id"])["name"], "温州市")

    def test_duplicate_username_is_rejected(self) -> None:
        password_hash = hash_password("password-123")

        self.assertIsNotNone(self.auth_store.register_user("zhangsan", password_hash))
        self.assertIsNone(self.auth_store.register_user("zhangsan", password_hash))


class UserCityStoreTests(unittest.TestCase):
    def test_city_history_is_isolated_by_user(self) -> None:
        store = CityStore(Settings(mongo_url="mongodb://localhost:27017"))
        city = {
            "city_key": "cn-zhejiang-wenzhou",
            "name": "温州市",
            "country": "中国",
            "country_code": "CN",
            "admin1": "浙江省",
            "latitude": 28.0,
            "longitude": 120.7,
            "timezone": "Asia/Shanghai",
        }

        store.record_city(city, user_id="user-a")
        store.record_city(city, user_id="user-a")
        store.record_city(city, user_id="user-b")

        self.assertEqual(store.popular(user_id="user-a")[0]["query_count"], 2)
        self.assertEqual(store.popular(user_id="user-b")[0]["query_count"], 1)
        self.assertEqual(store.popular(user_id="user-c"), [])


class AuthApiTests(unittest.TestCase):
    def test_register_me_and_logout_use_the_session_cookie(self) -> None:
        username = f"user_{uuid4().hex[:10]}"
        with TestClient(app) as client:
            register_response = client.post(
                "/api/auth/register",
                json={"username": username, "password": "password-123"},
            )
            self.assertEqual(register_response.status_code, 201)
            self.assertEqual(register_response.json()["user"]["username"], username)
            self.assertIn("weather_session", register_response.cookies)

            me_response = client.get("/api/auth/me")
            self.assertEqual(me_response.status_code, 200)
            self.assertEqual(me_response.json()["user"]["username"], username)

            logout_response = client.post("/api/auth/logout")
            self.assertEqual(logout_response.status_code, 200)
            self.assertEqual(client.get("/api/auth/me").status_code, 401)

    def test_ai_config_is_saved_per_user_and_key_is_masked(self) -> None:
        username = f"ai_user_{uuid4().hex[:10]}"
        api_key = "secret-api-key-1234"
        with TestClient(app) as client:
            register_response = client.post(
                "/api/auth/register",
                json={"username": username, "password": "password-123"},
            )
            self.assertEqual(register_response.status_code, 201)

            save_response = client.put(
                "/api/ai-config",
                json={
                    "base_url": "https://example.com/v1",
                    "model": "weather-model",
                    "api_key": api_key,
                },
            )
            self.assertEqual(save_response.status_code, 200)
            saved = save_response.json()
            self.assertTrue(saved["api_key_configured"])
            self.assertEqual(saved["api_key_masked"], "••••1234")
            self.assertNotIn(api_key, save_response.text)

            update_response = client.put(
                "/api/ai-config",
                json={"base_url": "https://example.com/v2", "model": "new-model"},
            )
            self.assertEqual(update_response.status_code, 200)
            updated = update_response.json()
            self.assertEqual(updated["base_url"], "https://example.com/v2")
            self.assertEqual(updated["model"], "new-model")
            self.assertEqual(updated["api_key_masked"], "••••1234")


if __name__ == "__main__":
    unittest.main()
