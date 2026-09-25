import os
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.database import Base, engine, SessionLocal
from app.routers import auth, market, news, analyzer, watchlist, education, trade_of_day, chat
from app.services import rag

logger = logging.getLogger("main")

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Crypto Insights API",
    description="Backend for a crypto market, news, education, AI chart-analysis, AI chat, and Trade of the Day app.",
    version="1.2.0",
)

origins = (
    ["*"] if settings.allowed_origins.strip() == "*"
    else [o.strip() for o in settings.allowed_origins.split(",")]
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(market.router)
app.include_router(news.router)
app.include_router(analyzer.router)
app.include_router(watchlist.router)
app.include_router(education.router)
app.include_router(trade_of_day.router)
app.include_router(chat.router)

STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
UPLOADS_DIR = os.path.join(STATIC_DIR, "uploads")
os.makedirs(UPLOADS_DIR, exist_ok=True)
app.mount("/static/uploads", StaticFiles(directory=UPLOADS_DIR), name="uploads")

ADMIN_PANEL_DIR = os.path.join(STATIC_DIR, "admin_panel")
app.mount("/admin", StaticFiles(directory=ADMIN_PANEL_DIR, html=True), name="admin")


@app.on_event("startup")
def build_rag_index_on_startup() -> None:
    """Best-effort: index the education knowledge base for chat retrieval.
    Never blocks or crashes app startup - if there's no Gemini key yet, or
    a transient network issue, the chat endpoint just falls back to
    general knowledge until POST /chat/reindex is called successfully."""
    if not settings.gemini_api_key:
        logger.info("Skipping RAG index build at startup - GEMINI_API_KEY not set yet.")
        return
    db = SessionLocal()
    try:
        existing = db.query(rag.models.KnowledgeChunk).count()
        if existing == 0:
            count = rag.rebuild_index(db)
            logger.info("Built initial RAG index: %d chunks", count)
    except Exception as e:  # noqa: BLE001
        logger.warning("RAG index build skipped at startup: %s", e)
    finally:
        db.close()


@app.get("/health", tags=["health"])
def health():
    return {"status": "ok"}
