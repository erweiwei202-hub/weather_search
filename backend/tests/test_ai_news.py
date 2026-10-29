from __future__ import annotations

import unittest
from datetime import date

from backend.app.assistant import build_assistant_messages
from backend.app.news import parse_news_rss


class NewsParsingTests(unittest.TestCase):
    def test_parser_keeps_only_today_and_preserves_source_metadata(self) -> None:
        xml = """
        <rss><channel>
          <item>
            <title>温州今日新闻</title>
            <link>https://news.google.com/rss/articles/today</link>
            <pubDate>Thu, 29 Oct 2026 06:43:39 GMT</pubDate>
            <source url="https://example.com">温州新闻</source>
          </item>
          <item>
            <title>温州昨日新闻</title>
            <link>https://news.google.com/rss/articles/yesterday</link>
            <pubDate>Wed, 28 Oct 2026 06:43:39 GMT</pubDate>
            <source>旧新闻</source>
          </item>
        </channel></rss>
        """.encode("utf-8")

        result = parse_news_rss(xml, today=date(2026, 10, 29))

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["title"], "温州今日新闻")
        self.assertEqual(result[0]["source"], "温州新闻")
        self.assertEqual(result[0]["url"], "https://news.google.com/rss/articles/today")


class AssistantPromptTests(unittest.TestCase):
    def test_prompt_contains_last_city_and_verified_news_context(self) -> None:
        messages = build_assistant_messages(
            question="今天适合出门吗？",
            city={"name": "温州市", "admin1": "浙江省"},
            weather={"current": {"temperature": 25}, "daily": [{"precipitation_probability": 20}]},
            news=[{"title": "温州今日新闻", "source": "温州新闻", "url": "https://example.com"}],
            history=[{"role": "user", "content": "你好"}],
        )

        self.assertIn("温州市", messages[0]["content"])
        self.assertIn("温州今日新闻", messages[0]["content"])
        self.assertEqual(messages[-2], {"role": "user", "content": "你好"})
        self.assertEqual(messages[-1], {"role": "user", "content": "今天适合出门吗？"})


if __name__ == "__main__":
    unittest.main()
