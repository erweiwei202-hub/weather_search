from __future__ import annotations

import unittest

from backend.app.china_cities import PROVINCE_CITIES, PROVINCE_OPTIONS
from backend.app.province_weather import (
    CONDITION_OPTIONS,
    condition_category,
    filter_city_results,
    valid_condition,
    valid_province,
)


class ProvinceWeatherTests(unittest.TestCase):
    def test_weather_codes_are_grouped_into_expected_conditions(self) -> None:
        self.assertEqual(condition_category(0), "晴朗")
        self.assertEqual(condition_category(63), "下雨")
        self.assertEqual(condition_category(73), "下雪")
        self.assertEqual(condition_category(45), "雾")
        self.assertEqual(condition_category(95), "雷雨")
        self.assertIsNone(condition_category(999))

    def test_filter_returns_only_matching_cities(self) -> None:
        cities = [
            {"name": "南京市", "condition_category": "下雨"},
            {"name": "苏州市", "condition_category": "晴朗"},
            {"name": "无锡市", "condition_category": "下雨"},
        ]

        result = filter_city_results(cities, "下雨")

        self.assertEqual([city["name"] for city in result], ["南京市", "无锡市"])

    def test_supported_provinces_and_conditions_are_validated(self) -> None:
        self.assertIn("江苏省", PROVINCE_OPTIONS)
        self.assertGreaterEqual(len(PROVINCE_CITIES["江苏省"]), 13)
        self.assertTrue(valid_province("江苏省"))
        self.assertFalse(valid_province("东京"))
        self.assertTrue(valid_condition("下雨"))
        self.assertFalse(valid_condition("高温"))
        self.assertEqual(len(CONDITION_OPTIONS), 7)


if __name__ == "__main__":
    unittest.main()
