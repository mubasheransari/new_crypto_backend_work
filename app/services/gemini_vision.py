"""Analyzes an uploaded crypto chart screenshot using Google's Gemini
vision capability and returns STRUCTURED fields: trend, key_pattern,
current_price, entry_price, stop_loss, target_price, invalidation_level,
indicators, bullish_scenario, bearish_scenario, setup_clarity, risk_level,
volatility_read, disclaimer.

Uses the `google-genai` SDK's structured-output mode (response_schema) so
the model returns real, individually-addressable fields your app can bind
to directly.

Requires GEMINI_API_KEY to be set in the environment / .env file.
Get a free key at https://aistudio.google.com/apikey

Note: Google frequently retires older Gemini models from free-tier access
(or shuts them down outright). If you start seeing 404 "no longer
available" or 429 "limit: 0" errors mentioning the model name below, check
https://ai.google.dev/gemini-api/docs/latest-model for the current
generally-available model and update MODEL_NAME accordingly - no other
code changes should be needed.

IMPORTANT - deliberate design decisions, please don't remove any of these
without thinking hard about why they're here:

1. No numeric "chance of success" / win-rate / confidence percentage, and
   no binary "safe / not safe" verdict, anywhere in this schema. No model
   can honestly compute either from a chart screenshot - both are
   fabricated certainty dressed up to look rigorous, which is actively
   misleading for something people might risk real money on. `risk_level`
   gives the honest, qualitative equivalent instead (Low/Medium/High with a
   real written reason) - that field IS the answer to "is this safe right
   now", just without pretending to a precision that doesn't exist.

2. current_price is a plain readout (whatever the chart's price label
   shows). entry_price must NOT just repeat it - it has to reflect actual
   technical reasoning (a pullback level, a breakout retest, a pattern
   boundary), or explicitly explain why the current price itself sits at a
   meaningful level. Silently echoing current_price into entry_price is not
   analysis and defeats the purpose of this field.

3. entry_price / stop_loss / target_price / invalidation_level are only
   ever a specific number when the model can actually read that price off
   the chart's visible axis labels. When it can't, it says so plainly
   instead of inventing a plausible-looking number.
"""

import asyncio
import logging

from google import genai
from google.genai import types
from pydantic import BaseModel, Field

from app.config import settings

logger = logging.getLogger("gemini_vision")

MODEL_NAME = "gemini-3.6-flash"


class ChartAnalysisFields(BaseModel):
    """The structured shape Gemini is asked to fill in for every chart."""

    trend: str = Field(
        description="Overall direction (uptrend/downtrend/range-bound), "
        "timeframe if visible, and how strong/clear it looks."
    )
    key_pattern: str = Field(
        description="Any clear chart pattern visible (head & shoulders, "
        "triangle, flag, double top/bottom, etc.) and what it typically "
        "suggests. If none is visible, say so plainly."
    )
    current_price: str = Field(
        description='The actual current/last traded price as shown directly '
        'on the chart (e.g. a price label, the last candle close, or a '
        '"Mark"/"Last Price" display) - read this directly, only when '
        'legible. If not legible, respond exactly with "Not clearly '
        'readable from this chart".'
    )
    entry_price: str = Field(
        description="A technically-reasoned potential entry reference zone "
        "derived from the analysis (e.g. a pullback to a support/moving-"
        "average confluence, a breakout retest level, or the edge of the "
        "current pattern) - only a specific approximate number if legible "
        "from the chart. This must reflect actual analysis and should NOT "
        "simply restate current_price - if current price genuinely already "
        "sits at the key technical level worth noting, say so explicitly "
        "and explain why that level matters, rather than just copying the "
        'number. If no price axis is legible, respond exactly with "Not '
        'clearly readable from this chart".'
    )
    stop_loss: str = Field(
        description='Same rule as entry_price: a specific approximate '
        'price only if legible from the chart, generally just beyond the '
        'nearest support (bullish read) or resistance (bearish read). '
        'Otherwise "Not clearly readable from this chart".'
    )
    target_price: str = Field(
        description='Same rule as entry_price: a specific approximate '
        'price only if legible from the chart, generally at the next '
        'visible resistance (bullish read) or support (bearish read). '
        'Otherwise "Not clearly readable from this chart".'
    )
    invalidation_level: str = Field(
        description='Same rule as entry_price: the approximate price at '
        'which this setup\'s read would be invalidated, only if legible. '
        'Otherwise "Not clearly readable from this chart".'
    )
    indicators: str = Field(
        description="Any visible indicators (RSI, MACD, moving averages, "
        "volume) and what they suggest. If none are visible, say so."
    )
    bullish_scenario: str = Field(
        description="A short 1-2 sentence bullish case for this chart."
    )
    bearish_scenario: str = Field(
        description="A short 1-2 sentence bearish case for this chart."
    )
    setup_clarity: str = Field(
        description='A short, honest, qualitative note on how clean vs '
        'ambiguous this setup is (e.g. "clean, textbook pattern with '
        'confirming volume" vs "mixed signals, low conviction"). Never a '
        "numeric probability, percentage, or win-rate."
    )
    risk_level: str = Field(
        description='This is the direct answer to "is trading this right '
        'now safe or risky" - start with one word: "Low", "Medium", or '
        '"High", followed by a clear, specific written reason (e.g. "High - '
        'price is fighting the dominant downtrend near recent swing lows '
        'with no confirmed reversal signal yet"). Never a numeric risk '
        "score, percentage, or safety rating - a word plus honest reasoning "
        "is the responsible version of a safety read; a fabricated number "
        "would not be."
    )
    volatility_read: str = Field(
        description="A description of how steady vs choppy recent price "
        "action looks on this chart (large frequent swings vs a smooth, "
        "gradual move), based only on what's visible in the image."
    )
    disclaimer: str = Field(
        default="Educational analysis only, not financial advice - prices "
        "above are approximate reference levels, not instructions, and "
        "risk_level is a qualitative read, not a guarantee of safety - "
        "markets are risky and this is not a guarantee of any outcome.",
        description="Always this exact fixed disclaimer string.",
    )


SYSTEM_PROMPT = """You are a technical-analysis assistant embedded in a crypto \
app. You are given a screenshot of a price chart. Fill in every field of the \
requested JSON schema with a clear, educational technical read of the chart.

Rules:
- current_price must be read directly off the chart (the visible last-price/
mark-price label) - this is a simple readout, not analysis.
- entry_price must NOT simply repeat current_price. It must reflect actual
technical reasoning - a pullback level, a breakout retest, a moving-average
confluence, or a pattern boundary. If the current price genuinely already
sits at that key level, say so explicitly and explain why the level matters,
rather than silently outputting the same number in both fields.
- entry_price, stop_loss, target_price, and invalidation_level must each be \
a specific approximate number ONLY when you can actually read that price \
level from the chart's visible axis labels. If the axis isn't legible or \
you cannot confidently place a number, respond with exactly "Not clearly \
readable from this chart" for that field - never guess a plausible-looking \
number just to fill the field.
- Frame every price field as a reference level a trader might consider, \
never as a direct instruction like "buy now" or "enter here".
- risk_level is where "is this safe to trade right now" gets answered - \
always give a real, specific reason, not a generic one. It must be a word \
(Low/Medium/High) plus a written reason, never a number or percentage.
- Never include a numeric success probability, confidence score, win-rate, \
risk score, or binary safe/unsafe verdict anywhere in your output. This is \
a hard rule with no exceptions.
- Keep each text field to 1-3 concise sentences.
"""


_client = None


def _get_client() -> genai.Client:
    global _client
    if _client is None:
        _client = genai.Client(api_key=settings.gemini_api_key)
    return _client


def _media_type_from_filename(filename: str) -> str:
    lower = filename.lower()
    if lower.endswith(".png"):
        return "image/png"
    if lower.endswith(".webp"):
        return "image/webp"
    if lower.endswith(".gif"):
        return "image/gif"
    if lower.endswith(".heic"):
        return "image/heic"
    if lower.endswith(".heif"):
        return "image/heif"
    return "image/jpeg"


def _generate_sync(image_bytes: bytes, filename: str, user_note: str) -> ChartAnalysisFields:
    client = _get_client()
    prompt_text = user_note or "Please analyze this crypto price chart screenshot."

    response = client.models.generate_content(
        model=MODEL_NAME,
        contents=[
            types.Part.from_bytes(
                data=image_bytes,
                mime_type=_media_type_from_filename(filename),
            ),
            prompt_text,
        ],
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            max_output_tokens=2048,
            thinking_config=types.ThinkingConfig(thinking_level="low"),
            response_mime_type="application/json",
            response_schema=ChartAnalysisFields,
        ),
    )

    if response.usage_metadata is not None:
        usage = response.usage_metadata
        logger.info(
            "Gemini token usage - prompt: %s, output: %s, thinking: %s, total: %s",
            usage.prompt_token_count,
            usage.candidates_token_count,
            usage.thoughts_token_count,
            usage.total_token_count,
        )

    if response.parsed is not None:
        return response.parsed

    return ChartAnalysisFields.model_validate_json(response.text)


async def analyze_chart_image(
    image_bytes: bytes, filename: str, user_note: str = ""
) -> ChartAnalysisFields:
    if not settings.gemini_api_key:
        raise RuntimeError(
            "GEMINI_API_KEY is not configured on the server. Add it to your .env file."
        )

    try:
        return await asyncio.to_thread(
            _generate_sync, image_bytes, filename, user_note
        )
    except Exception as e:  # noqa: BLE001
        raise RuntimeError(f"Gemini API error: {e}") from e
