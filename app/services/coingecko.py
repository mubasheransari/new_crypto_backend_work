"""Thin wrapper around the free CoinGecko public API."""

import time
from typing import Any, Optional

import httpx

BASE_URL = "https://api.coingecko.com/api/v3"

_cache: dict[str, tuple[float, Any]] = {}
CACHE_TTL_SECONDS = 30


async def _get(path: str, params: Optional[dict] = None) -> Any:
    cache_key = f"{path}?{params}"
    now = time.time()
    if cache_key in _cache:
        cached_at, data = _cache[cache_key]
        if now - cached_at < CACHE_TTL_SECONDS:
            return data

    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(f"{BASE_URL}{path}", params=params or {})
        resp.raise_for_status()
        data = resp.json()

    _cache[cache_key] = (now, data)
    return data


async def get_markets(
    vs_currency: str = "usd",
    page: int = 1,
    per_page: int = 50,
    ids: Optional[str] = None,
    order: str = "market_cap_desc",
) -> list[dict]:
    params = {
        "vs_currency": vs_currency,
        "order": order,
        "per_page": per_page,
        "page": page,
        "sparkline": "true",
        "price_change_percentage": "24h,7d",
    }
    if ids:
        params["ids"] = ids
    return await _get("/coins/markets", params)


async def search_coins(query: str) -> list[dict]:
    data = await _get("/search", {"query": query})
    return data.get("coins", [])


async def get_coin_detail(coin_id: str) -> dict:
    params = {
        "localization": "false",
        "tickers": "false",
        "market_data": "true",
        "community_data": "false",
        "developer_data": "false",
        "sparkline": "false",
    }
    return await _get(f"/coins/{coin_id}", params)


async def get_trending() -> list[dict]:
    data = await _get("/search/trending")
    return data.get("coins", [])


async def get_global_data() -> dict:
    """Total crypto market cap, volume, and BTC dominance - CoinGecko's
    free /global endpoint. No API key needed. Never touches the Gemini API."""
    data = await _get("/global")
    return data.get("data", {})
