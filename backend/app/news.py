from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from typing import Any, Optional
from xml.etree import ElementTree

import httpx

from .config import Settings


logger = logging.getLogger(__name__)
CHINA_TIMEZONE = timezone(timedelta(hours=8), name="Asia/Shanghai")


class NewsUnavailableError(RuntimeError):
    """Raised when the external news source cannot be read or parsed."""


def _text(item: ElementTree.Element, tag: str) -> str:
    value = item.findtext(tag)
    return (value or "").strip()


def _parse_published_at(value: str) -> Optional[datetime]:
    if not value:
        return None
    try:
        parsed = parsedate_to_datetime(value)
    except (TypeError, ValueError, OverflowError):
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def parse_news_rss(xml_content: bytes, today: Optional[date] = None) -> list[dict[str, Any]]:
    """Parse only today's Google News RSS items and preserve source metadata."""
    try:
        root = ElementTree.fromstring(xml_content)
    except ElementTree.ParseError as error:
        raise NewsUnavailableError("新闻源返回了无法解析的 XML") from error

    china_today = today or datetime.now(CHINA_TIMEZONE).date()
    items: list[dict[str, Any]] = []
    seen_urls: set[str] = set()
    for item in root.findall("./channel/item"):
        published_at = _parse_published_at(_text(item, "pubDate"))
        url = _text(item, "link")
        if published_at is None or not url or url in seen_urls:
            continue
        if published_at.astimezone(CHINA_TIMEZONE).date() != china_today:
            continue
        source_element = item.find("source")
        source = (source_element.text or "").strip() if source_element is not None else ""
        title = _text(item, "title")
        if not title:
            continue
        seen_urls.add(url)
        items.append(
            {
                "title": title,
                "source": source or "Google News",
                "url": url,
                "published_at": published_at.isoformat(),
            }
        )
    return items[:8]


async def fetch_city_news(city: str, settings: Settings) -> list[dict[str, Any]]:
    timeout = httpx.Timeout(10.0, connect=5.0)
    params = {
        "q": city,
        "hl": "zh-CN",
        "gl": "CN",
        "ceid": "CN:zh-Hans",
    }
    try:
        async with httpx.AsyncClient(
            timeout=timeout,
            headers={"User-Agent": "WeatherAtlas/1.0"},
            follow_redirects=True,
        ) as client:
            response = await client.get(settings.news_rss_url, params=params)
            response.raise_for_status()
        news = parse_news_rss(response.content)
        logger.info("城市新闻获取完成 city=%s count=%s", city, len(news))
        return news
    except (httpx.HTTPError, NewsUnavailableError) as error:
        logger.warning("城市新闻获取失败 city=%s reason=%s", city, error)
        raise NewsUnavailableError("当天新闻暂时无法获取") from error
