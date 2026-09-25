"""Crypto news, with two sources:

1. CryptoCompare / CoinDesk Data news API - used automatically if you've
   set CRYPTOCOMPARE_API_KEY in .env. Requires a free key from
   https://developers.coindesk.com/ since ~May 2026.

2. RSS feeds from major crypto news outlets (Cointelegraph, Decrypt,
   BeInCrypto) - used automatically as a fallback if no key is configured,
   or if the CryptoCompare call fails for any reason. Needs NO API key or
   signup at all - this is the default path for a fresh setup.

You don't need to choose between these - if CRYPTOCOMPARE_API_KEY is set
and working, you get that; otherwise the app just works anyway via RSS.
"""

import hashlib
import logging
import time
from datetime import datetime, timezone
from typing import Optional

import feedparser
import httpx

from app.config import settings

logger = logging.getLogger("news_service")

CRYPTOCOMPARE_NEWS_URL = "https://min-api.cryptocompare.com/data/v2/news/"

RSS_FEEDS = {
    "Cointelegraph": "https://cointelegraph.com/rss",
    "Decrypt": "https://decrypt.co/feed",
    "BeInCrypto": "https://beincrypto.com/feed",
}


# ---------- CryptoCompare / CoinDesk Data path (needs a key) ----------

async def _get_news_from_cryptocompare(category: Optional[str], limit: int) -> list[dict]:
    params = {"lang": "EN"}
    if category:
        params["categories"] = category

    headers = {"Authorization": f"Apikey {settings.cryptocompare_api_key}"}

    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(CRYPTOCOMPARE_NEWS_URL, params=params, headers=headers)
        resp.raise_for_status()
        data = resp.json()

    articles = []
    for item in data.get("Data", [])[:limit]:
        articles.append(
            {
                "id": str(item.get("id")),
                "title": item.get("title"),
                "body": item.get("body"),
                "url": item.get("url"),
                "source": item.get("source_info", {}).get("name") or item.get("source"),
                "image_url": item.get("imageurl"),
                "published_at": datetime.fromtimestamp(
                    item.get("published_on", 0), tz=timezone.utc
                ),
                "tags": item.get("categories"),
            }
        )
    return articles


# ---------- Free RSS path (no key needed) ----------

async def _fetch_one_feed(client: httpx.AsyncClient, source_name: str, url: str) -> list[dict]:
    resp = await client.get(url, headers={"User-Agent": "Mozilla/5.0"})
    resp.raise_for_status()
    feed = feedparser.parse(resp.text)

    articles = []
    for entry in feed.entries:
        published_at = None
        if getattr(entry, "published_parsed", None):
            published_at = datetime.fromtimestamp(
                time.mktime(entry.published_parsed), tz=timezone.utc
            )

        image_url = None
        media_content = getattr(entry, "media_content", None)
        if media_content:
            image_url = media_content[0].get("url")
        if not image_url:
            for link in getattr(entry, "links", []):
                if link.get("type", "").startswith("image"):
                    image_url = link.get("href")
                    break

        link = getattr(entry, "link", "")
        article_id = hashlib.md5(link.encode()).hexdigest()

        articles.append(
            {
                "id": article_id,
                "title": getattr(entry, "title", "Untitled"),
                "body": getattr(entry, "summary", None),
                "url": link,
                "source": source_name,
                "image_url": image_url,
                "published_at": published_at,
                "tags": None,
            }
        )
    return articles


async def _get_news_from_rss(category: Optional[str], limit: int) -> list[dict]:
    all_articles: list[dict] = []
    async with httpx.AsyncClient(timeout=10) as client:
        for source_name, url in RSS_FEEDS.items():
            try:
                all_articles.extend(await _fetch_one_feed(client, source_name, url))
            except Exception as e:  # noqa: BLE001
                # One feed being down shouldn't take down the whole request -
                # just skip it and use what the others returned.
                logger.warning("RSS feed '%s' failed: %s", source_name, e)
                continue

    if category:
        cat_lower = category.lower()
        all_articles = [
            a
            for a in all_articles
            if cat_lower in a["title"].lower() or cat_lower in (a.get("body") or "").lower()
        ]

    all_articles.sort(
        key=lambda a: a["published_at"] or datetime.min.replace(tzinfo=timezone.utc),
        reverse=True,
    )
    return all_articles[:limit]


# ---------- Public entry point ----------

async def get_news(category: Optional[str] = None, limit: int = 30) -> list[dict]:
    if settings.cryptocompare_api_key:
        try:
            return await _get_news_from_cryptocompare(category, limit)
        except Exception as e:  # noqa: BLE001
            logger.warning(
                "CryptoCompare news request failed (%s) - falling back to free RSS feeds.", e
            )

    return await _get_news_from_rss(category, limit)
