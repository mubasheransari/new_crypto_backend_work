import asyncio
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
import httpx
from sqlalchemy.orm import Session

from app.database import get_db
from app.services import news_service, rag

router = APIRouter(prefix="/news", tags=["news"])


def _index_news_background(articles: list[dict]) -> None:
    from app.database import SessionLocal

    db = SessionLocal()
    try:
        rag.index_news_articles(db, articles)
    except Exception:  # noqa: BLE001
        pass
    finally:
        db.close()


@router.get("")
async def get_news(
    background_tasks: BackgroundTasks,
    category: Optional[str] = Query(
        None, description="e.g. BTC, ETH, Trading, Regulation, Mining"
    ),
    limit: int = Query(30, ge=1, le=100),
):
    try:
        articles = await news_service.get_news(category=category, limit=limit)
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=502, detail=f"News provider error: {e}")

    # Feed fresh headlines into the chat's RAG index after the response is
    # already sent - never delays the news the user is waiting for.
    background_tasks.add_task(_index_news_background, articles)

    return articles
