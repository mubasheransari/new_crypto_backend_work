from typing import Optional

from fastapi import APIRouter, HTTPException, Query
import httpx

from app.services import coingecko

router = APIRouter(prefix="/market", tags=["market"])


@router.get("/coins")
async def list_coins(
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=250),
    vs_currency: str = "usd",
):
    try:
        data = await coingecko.get_markets(
            vs_currency=vs_currency, page=page, per_page=per_page
        )
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=502, detail=f"CoinGecko error: {e}")

    results = []
    for c in data:
        results.append(
            {
                "id": c.get("id"),
                "symbol": c.get("symbol"),
                "name": c.get("name"),
                "image": c.get("image"),
                "current_price": c.get("current_price"),
                "market_cap": c.get("market_cap"),
                "market_cap_rank": c.get("market_cap_rank"),
                "price_change_percentage_24h": c.get("price_change_percentage_24h_in_currency")
                or c.get("price_change_percentage_24h"),
                "total_volume": c.get("total_volume"),
                "sparkline_in_7d": c.get("sparkline_in_7d"),
            }
        )
    return results


@router.get("/search")
async def search(query: str = Query(..., min_length=1)):
    try:
        return await coingecko.search_coins(query)
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=502, detail=f"CoinGecko error: {e}")


@router.get("/trending")
async def trending():
    try:
        return await coingecko.get_trending()
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=502, detail=f"CoinGecko error: {e}")


@router.get("/global")
async def global_market_data():
    try:
        raw = await coingecko.get_global_data()
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=502, detail=f"CoinGecko error: {e}")

    market_cap = raw.get("total_market_cap", {}).get("usd")
    volume = raw.get("total_volume", {}).get("usd")
    market_cap_change_pct = raw.get("market_cap_change_percentage_24h_usd")
    dominance = raw.get("market_cap_percentage", {})

    return {
        "total_market_cap_usd": market_cap,
        "total_volume_usd": volume,
        "market_cap_change_percentage_24h": market_cap_change_pct,
        "btc_dominance": dominance.get("btc"),
        "eth_dominance": dominance.get("eth"),
        "active_cryptocurrencies": raw.get("active_cryptocurrencies"),
    }


@router.get("/coins/{coin_id}")
async def coin_detail(coin_id: str):
    try:
        raw = await coingecko.get_coin_detail(coin_id)
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            raise HTTPException(status_code=404, detail="Coin not found")
        raise HTTPException(status_code=502, detail=f"CoinGecko error: {e}")

    market_data = raw.get("market_data", {})
    return {
        "id": raw.get("id"),
        "symbol": raw.get("symbol"),
        "name": raw.get("name"),
        "image": raw.get("image", {}).get("large"),
        "description": (raw.get("description", {}) or {}).get("en"),
        "current_price": market_data.get("current_price", {}).get("usd"),
        "market_cap": market_data.get("market_cap", {}).get("usd"),
        "price_change_percentage_24h": market_data.get("price_change_percentage_24h"),
        "price_change_percentage_7d": market_data.get("price_change_percentage_7d"),
        "ath": market_data.get("ath", {}).get("usd"),
        "atl": market_data.get("atl", {}).get("usd"),
        "homepage": (raw.get("links", {}) or {}).get("homepage", [None])[0],
    }
