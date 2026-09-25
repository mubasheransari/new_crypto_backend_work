"""The crypto AI chat assistant: combines
  1. RAG over the app's own content (education articles + cached news)
  2. General crypto knowledge from Gemini itself
  3. Live market data via function calling (price lookups, global stats)

into a single conversational endpoint.

Same safety framing as the rest of the app: no fabricated certainty, no
direct "buy/sell now" instructions, always distinguishes live data from
general knowledge, and includes a standing not-financial-advice note.
"""

import asyncio
import json
import logging

from google import genai
from google.genai import types
from sqlalchemy.orm import Session

from app.config import settings
from app.services import coingecko, rag

logger = logging.getLogger("chat_ai")

MODEL_NAME = "gemini-3.5-flash-lite"
MAX_TOOL_ROUNDS = 3

SYSTEM_PROMPT = """You are a helpful crypto assistant embedded in the Crypto \
Insights app. You can draw on three kinds of information:

1. RETRIEVED CONTEXT - excerpts from this app's own education articles and \
recent cached news, given to you below the user's question when relevant. \
Prefer this when it directly answers the question, and you may mention \
it came from the app's own content.
2. YOUR OWN GENERAL KNOWLEDGE of cryptocurrency, blockchain, and markets - \
use this freely for questions the retrieved context doesn't cover. Be \
clear when you're speaking from general knowledge rather than the app's \
retrieved content or live data.
3. LIVE MARKET DATA - use the get_coin_price and get_global_market_stats \
tools whenever the user asks about a current/live price, market cap, or \
similar real-time figures. Never guess or estimate a current price from \
memory - always call the tool for anything time-sensitive.

Rules:
- Never give direct trading instructions ("buy now", "sell now", "enter \
here"). You can explain concepts, describe what indicators/patterns mean, \
and report live data factually, but decisions belong to the user.
- Never state or imply a numeric "chance of success" or guaranteed outcome \
for any trade or investment. No one can honestly calculate that.
- If you're not confident about something, say so plainly rather than \
guessing.
- Keep answers SHORT - 2-4 sentences for most questions. Only go longer if \
the user explicitly asks for detail or a step-by-step explanation. Users \
are on a mobile chat screen and want quick answers, not essays.
"""

GET_COIN_PRICE_DECL = types.FunctionDeclaration(
    name="get_coin_price",
    description=(
        "Get the current live price, market cap, and 24h change for a specific "
        "cryptocurrency. Use the CoinGecko coin id (lowercase, e.g. 'bitcoin', "
        "'ethereum', 'solana', 'dogecoin') - not the ticker symbol."
    ),
    parameters={
        "type": "object",
        "properties": {
            "coin_id": {
                "type": "string",
                "description": "CoinGecko coin id, e.g. 'bitcoin', 'ethereum', 'solana'",
            }
        },
        "required": ["coin_id"],
    },
)

GET_GLOBAL_STATS_DECL = types.FunctionDeclaration(
    name="get_global_market_stats",
    description=(
        "Get current total crypto market cap, 24h change, total trading "
        "volume, and BTC/ETH dominance across the whole market."
    ),
    parameters={"type": "object", "properties": {}},
)

TOOLS = types.Tool(function_declarations=[GET_COIN_PRICE_DECL, GET_GLOBAL_STATS_DECL])

_client = None


def _get_client() -> genai.Client:
    global _client
    if _client is None:
        _client = genai.Client(api_key=settings.gemini_api_key)
    return _client


def _sync_get_coin_price(coin_id: str) -> dict:
    try:
        raw = asyncio.run(coingecko.get_coin_detail(coin_id))
    except Exception as e:  # noqa: BLE001
        return {"error": f"Could not fetch data for '{coin_id}': {e}"}

    market_data = raw.get("market_data", {})
    return {
        "id": raw.get("id"),
        "name": raw.get("name"),
        "symbol": raw.get("symbol"),
        "current_price_usd": market_data.get("current_price", {}).get("usd"),
        "market_cap_usd": market_data.get("market_cap", {}).get("usd"),
        "price_change_percentage_24h": market_data.get("price_change_percentage_24h"),
    }


def _sync_get_global_market_stats() -> dict:
    try:
        raw = asyncio.run(coingecko.get_global_data())
    except Exception as e:  # noqa: BLE001
        return {"error": f"Could not fetch global market data: {e}"}

    dominance = raw.get("market_cap_percentage", {})
    return {
        "total_market_cap_usd": raw.get("total_market_cap", {}).get("usd"),
        "total_volume_usd": raw.get("total_volume", {}).get("usd"),
        "market_cap_change_percentage_24h": raw.get("market_cap_change_percentage_24h_usd"),
        "btc_dominance": dominance.get("btc"),
        "eth_dominance": dominance.get("eth"),
    }


TOOL_HANDLERS = {
    "get_coin_price": _sync_get_coin_price,
    "get_global_market_stats": _sync_get_global_market_stats,
}


def _build_history_contents(history: list[dict]) -> list[types.Content]:
    """history is a list of {'role': 'user'|'assistant', 'content': str}
    from the DB, oldest first."""
    contents = []
    for msg in history:
        role = "user" if msg["role"] == "user" else "model"
        contents.append(types.Content(role=role, parts=[types.Part.from_text(text=msg["content"])]))
    return contents


def _generate_sync(
    db: Session, user_message: str, history: list[dict]
) -> tuple[str, list[dict], bool]:
    """Returns (reply_text, sources_used, used_live_data)."""
    client = _get_client()

    sources = rag.retrieve(db, user_message)
    context_block = ""
    if sources:
        formatted = "\n\n".join(f"[{s['title']}]\n{s['text']}" for s in sources)
        context_block = f"\n\nRETRIEVED CONTEXT (from the app's own content):\n{formatted}"

    contents = _build_history_contents(history)
    contents.append(
        types.Content(
            role="user",
            parts=[types.Part.from_text(text=f"{user_message}{context_block}")],
        )
    )

    used_live_data = False

    for _ in range(MAX_TOOL_ROUNDS):
        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=contents,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                max_output_tokens=600,
                thinking_config=types.ThinkingConfig(thinking_level="low"),
                tools=[TOOLS],
            ),
        )

        if response.usage_metadata is not None:
            usage = response.usage_metadata
            logger.info(
                "Chat token usage - prompt: %s, output: %s, thinking: %s, total: %s",
                usage.prompt_token_count,
                usage.candidates_token_count,
                usage.thoughts_token_count,
                usage.total_token_count,
            )

        candidate = response.candidates[0] if response.candidates else None
        parts = candidate.content.parts if candidate and candidate.content else []

        function_calls = [p for p in parts if getattr(p, "function_call", None)]
        if not function_calls:
            return (response.text or "").strip(), sources, used_live_data

        # Model wants to call one or more tools - execute them and feed the
        # results back for a follow-up turn.
        contents.append(candidate.content)
        function_response_parts = []
        for part in function_calls:
            fc = part.function_call
            handler = TOOL_HANDLERS.get(fc.name)
            if handler is None:
                result = {"error": f"Unknown tool: {fc.name}"}
            else:
                used_live_data = True
                result = handler(**dict(fc.args or {}))
            function_response_parts.append(
                types.Part.from_function_response(name=fc.name, response=result)
            )
        contents.append(types.Content(role="user", parts=function_response_parts))

    # Ran out of tool-call rounds - return whatever text we last had, if any.
    return "I wasn't able to finish that request - please try rephrasing it.", sources, used_live_data


async def generate_reply(
    db: Session, user_message: str, history: list[dict]
) -> tuple[str, list[dict], bool]:
    if not settings.gemini_api_key:
        raise RuntimeError(
            "GEMINI_API_KEY is not configured on the server. Add it to your .env file."
        )
    try:
        return await asyncio.to_thread(_generate_sync, db, user_message, history)
    except Exception as e:  # noqa: BLE001
        raise RuntimeError(f"Gemini API error: {e}") from e
