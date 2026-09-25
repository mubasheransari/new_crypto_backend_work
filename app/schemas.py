from datetime import datetime
from typing import Optional, List

from pydantic import BaseModel, EmailStr, ConfigDict


# ---------- Auth / Users ----------

class UserCreate(BaseModel):
    email: EmailStr
    password: str
    full_name: Optional[str] = None


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    id: int
    email: EmailStr
    full_name: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


# ---------- Market ----------

class CoinMarket(BaseModel):
    id: str
    symbol: str
    name: str
    image: Optional[str] = None
    current_price: Optional[float] = None
    market_cap: Optional[float] = None
    market_cap_rank: Optional[int] = None
    price_change_percentage_24h: Optional[float] = None
    total_volume: Optional[float] = None
    sparkline_in_7d: Optional[dict] = None


class CoinDetail(BaseModel):
    id: str
    symbol: str
    name: str
    image: Optional[str] = None
    description: Optional[str] = None
    current_price: Optional[float] = None
    market_cap: Optional[float] = None
    price_change_percentage_24h: Optional[float] = None
    price_change_percentage_7d: Optional[float] = None
    ath: Optional[float] = None
    atl: Optional[float] = None
    homepage: Optional[str] = None


# ---------- News ----------

class NewsArticle(BaseModel):
    id: str
    title: str
    body: Optional[str] = None
    url: str
    source: Optional[str] = None
    image_url: Optional[str] = None
    published_at: Optional[datetime] = None
    tags: Optional[str] = None


# ---------- Watchlist ----------

class WatchlistAdd(BaseModel):
    coin_id: str
    symbol: str


class WatchlistOut(BaseModel):
    id: int
    coin_id: str
    symbol: str
    added_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ---------- Analyzer ----------

class ChartAnalysisOut(BaseModel):
    id: int
    user_id: Optional[int] = None
    analyst_name: Optional[str] = None
    analyst_email: Optional[EmailStr] = None
    is_mine: bool = False
    coin_hint: Optional[str] = None
    trend: str
    key_pattern: str
    current_price: str
    entry_price: str
    stop_loss: str
    target_price: str
    invalidation_level: str
    indicators: str
    bullish_scenario: str
    bearish_scenario: str
    setup_clarity: str
    risk_level: str
    volatility_read: str
    disclaimer: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AnalysisNotificationOut(BaseModel):
    id: int
    analysis_id: int
    message: str
    is_read: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ---------- Education ----------

class EducationTopic(BaseModel):
    slug: str
    title: str
    category: str
    summary: str
    content: str


# ---------- Trade of the Day ----------

class TradeOfDayOut(BaseModel):
    id: int
    title: str
    description: str
    image_url: str
    trade_datetime: datetime
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ---------- AI Chat ----------

class ChatSource(BaseModel):
    source_type: str
    source_id: str
    title: str


class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None


class ChatResponse(BaseModel):
    session_id: str
    reply: str
    sources: List[ChatSource] = []
    used_live_data: bool = False


class ChatMessageOut(BaseModel):
    id: int
    role: str
    content: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
