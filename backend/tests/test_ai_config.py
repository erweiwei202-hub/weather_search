import unittest

from cryptography.fernet import Fernet

from backend.app.auth import hash_password
from backend.app.config import Settings
from backend.app.database import AuthStore


class UserAIConfigTests(unittest.TestCase):
    def setUp(self):
        settings = Settings(
            mongo_url="mongodb://localhost:27017",
            ai_config_encryption_key=Fernet.generate_key().decode("utf-8"),
        )
        self.store = AuthStore(settings)
        self.user = self.store.register_user("weather-user", hash_password("password-123"))

    def test_save_update_and_read_ai_config_without_exposing_key(self):
        saved = self.store.save_ai_config(
            self.user["user_id"],
            "https://example.com/v1",
            "weather-model",
            api_key="secret-api-key-1234",
        )

        self.assertTrue(saved["api_key_configured"])
        self.assertEqual(saved["api_key_masked"], "••••1234")
        self.assertNotIn("secret-api-key-1234", str(self.store._users))
        self.assertEqual(
            self.store.get_ai_config(self.user["user_id"]),
            {
                "base_url": "https://example.com/v1",
                "model": "weather-model",
                "api_key": "secret-api-key-1234",
            },
        )

        updated = self.store.save_ai_config(
            self.user["user_id"],
            "https://example.com/v2",
            "new-weather-model",
        )

        self.assertEqual(updated["base_url"], "https://example.com/v2")
        self.assertEqual(updated["model"], "new-weather-model")
        self.assertEqual(self.store.get_ai_config(self.user["user_id"])["api_key"], "secret-api-key-1234")

    def test_clear_api_key(self):
        self.store.save_ai_config(
            self.user["user_id"],
            "https://example.com/v1",
            "weather-model",
            api_key="secret-api-key-1234",
        )
        cleared = self.store.save_ai_config(
            self.user["user_id"],
            "https://example.com/v1",
            "weather-model",
            clear_api_key=True,
        )

        self.assertFalse(cleared["api_key_configured"])
        self.assertEqual(self.store.get_ai_config(self.user["user_id"])["api_key"], "")


if __name__ == "__main__":
    unittest.main()
