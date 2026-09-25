from datetime import datetime

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, UniqueConstraint, Boolean
from sqlalchemy.orm import relationship

from app.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    full_name = Column(String, nullable=True)
    hashed_password = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    watchlist_items = relationship(
        "WatchlistItem", back_populates="owner", cascade="all, delete-orphan"
    )
    chart_analyses = relationship(
        "ChartAnalysis", back_populates="owner", cascade="all, delete-orphan"
    )


class WatchlistItem(Base):
    __tablename__ = "watchlist_items"
    __table_args__ = (UniqueConstraint("user_id", "coin_id", name="uq_user_coin"),)

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    coin_id = Column(String, nullable=False)
    symbol = Column(String, nullable=False)
    added_at = Column(DateTime, default=datetime.utcnow)

    owner = relationship("User", back_populates="watchlist_items")


class ChartAnalysis(Base):
    """Stores a history of AI chart-screenshot analyses per user, as
    structured fields rather than one text blob."""

    __tablename__ = "chart_analyses"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    coin_hint = Column(String, nullable=True)

    trend = Column(String, nullable=False)
    key_pattern = Column(String, nullable=False)
    current_price = Column(String, nullable=False)
    entry_price = Column(String, nullable=False)
    stop_loss = Column(String, nullable=False)
    target_price = Column(String, nullable=False)
    invalidation_level = Column(String, nullable=False)
    indicators = Column(String, nullable=False)
    bullish_scenario = Column(String, nullable=False)
    bearish_scenario = Column(String, nullable=False)
    setup_clarity = Column(String, nullable=False)
    risk_level = Column(String, nullable=False)
    volatility_read = Column(String, nullable=False)
    disclaimer = Column(String, nullable=False)

    created_at = Column(DateTime, default=datetime.utcnow)

    owner = relationship("User", back_populates="chart_analyses")
    notifications = relationship("AnalysisNotification", back_populates="analysis", cascade="all, delete-orphan")


class AnalysisNotification(Base):
    __tablename__ = "analysis_notifications"
    __table_args__ = (UniqueConstraint("user_id", "analysis_id", name="uq_analysis_notification"),)

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    analysis_id = Column(Integer, ForeignKey("chart_analyses.id"), nullable=False, index=True)
    message = Column(String, nullable=False)
    is_read = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    user = relationship("User")
    analysis = relationship("ChartAnalysis", back_populates="notifications")


class TradeOfTheDay(Base):
    """A single 'Trade of the Day' post, managed from the admin panel."""

    __tablename__ = "trade_of_day"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    description = Column(String, nullable=False)
    image_url = Column(String, nullable=False)
    trade_datetime = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class KnowledgeChunk(Base):
    """A single embedded chunk of the RAG knowledge base (education
    articles + cached news). embedding_json stores the vector as a JSON
    array of floats - fine for a knowledge base this size; a dedicated
    vector DB isn't needed."""

    __tablename__ = "knowledge_chunks"

    id = Column(Integer, primary_key=True, index=True)
    source_type = Column(String, nullable=False)  # "education" | "news"
    source_id = Column(String, nullable=False)  # slug or article id
    title = Column(String, nullable=False)
    text = Column(String, nullable=False)
    embedding_json = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class ChatMessage(Base):
    """A single message in a chat conversation. Guest chats (no user_id)
    aren't persisted across sessions on the client, but are still stored
    server-side for the lifetime of that session_id."""

    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String, nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    role = Column(String, nullable=False)  # "user" | "assistant"
    content = Column(String, nullable=False)
    sources_json = Column(String, nullable=True)  # retrieved sources, if any
    used_live_data = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
