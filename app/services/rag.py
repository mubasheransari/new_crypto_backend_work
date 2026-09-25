"""Lightweight, dependency-free RAG (retrieval-augmented generation) layer
over the app's own content: education articles + cached news headlines.

Deliberately does NOT use a heavyweight vector database (Chroma, Pinecone,
etc.) - for a knowledge base this size (dozens to low hundreds of chunks),
storing embeddings as JSON in the existing SQLite database and doing cosine
similarity in-memory with numpy is simpler, has zero extra infrastructure,
and avoids adding another dependency with its own version-conflict risk.

Uses Gemini's embedding model (gemini-embedding-001), which has its own
free-tier quota separate from the chat/analysis quota.
"""

import json
import logging

import numpy as np
from google import genai
from google.genai import types
from sqlalchemy.orm import Session

from app.config import settings
from app import models

logger = logging.getLogger("rag")

EMBEDDING_MODEL = "gemini-embedding-001"
EMBEDDING_DIMENSIONS = 768  # smaller than the 3072 default - good quality, less storage
TOP_K = 4

_client = None


def _get_client() -> genai.Client:
    global _client
    if _client is None:
        _client = genai.Client(api_key=settings.gemini_api_key)
    return _client


def embed_text(text: str, task_type: str = "RETRIEVAL_DOCUMENT") -> list[float]:
    """task_type should be RETRIEVAL_DOCUMENT when indexing content and
    RETRIEVAL_QUERY when embedding a user's question - Gemini's embedding
    model is trained to treat these differently for better retrieval."""
    client = _get_client()
    result = client.models.embed_content(
        model=EMBEDDING_MODEL,
        contents=text,
        config=types.EmbedContentConfig(
            task_type=task_type,
            output_dimensionality=EMBEDDING_DIMENSIONS,
        ),
    )
    return list(result.embeddings[0].values)


def _chunk_text(text: str, max_chars: int = 800) -> list[str]:
    """Simple paragraph-aware chunking - good enough for our fairly short
    education articles and news summaries."""
    paragraphs = [p.strip() for p in text.split("\n") if p.strip()]
    chunks: list[str] = []
    current = ""
    for p in paragraphs:
        if len(current) + len(p) + 1 <= max_chars:
            current = f"{current}\n{p}".strip()
        else:
            if current:
                chunks.append(current)
            current = p
    if current:
        chunks.append(current)
    return chunks or [text]


def rebuild_index(db: Session) -> int:
    """Re-embeds all education content (and any cached news passed in
    separately via index_news_articles) and replaces the stored chunks.
    Returns the number of chunks indexed. Safe to call repeatedly - e.g.
    from an admin-triggered refresh endpoint."""
    if not settings.gemini_api_key:
        raise RuntimeError("GEMINI_API_KEY is not configured - cannot build embeddings.")

    from app.routers.education import TOPICS  # local import avoids a circular import

    db.query(models.KnowledgeChunk).filter(
        models.KnowledgeChunk.source_type == "education"
    ).delete()

    count = 0
    for topic in TOPICS:
        full_text = f"{topic['title']}\n\n{topic['content']}"
        for chunk_text in _chunk_text(full_text):
            try:
                embedding = embed_text(chunk_text, task_type="RETRIEVAL_DOCUMENT")
            except Exception as e:  # noqa: BLE001
                logger.warning("Failed to embed chunk for %s: %s", topic["slug"], e)
                continue
            db.add(
                models.KnowledgeChunk(
                    source_type="education",
                    source_id=topic["slug"],
                    title=topic["title"],
                    text=chunk_text,
                    embedding_json=json.dumps(embedding),
                )
            )
            count += 1

    db.commit()
    logger.info("RAG index rebuilt: %d education chunks", count)
    return count


def index_news_articles(db: Session, articles: list[dict]) -> int:
    """Embeds and stores a batch of news articles for retrieval. Called
    opportunistically after a successful /news fetch so recent headlines
    become searchable without a separate indexing job. Skips articles
    already indexed (by source_id)."""
    if not settings.gemini_api_key:
        return 0

    existing_ids = {
        row[0]
        for row in db.query(models.KnowledgeChunk.source_id)
        .filter(models.KnowledgeChunk.source_type == "news")
        .all()
    }

    count = 0
    for article in articles[:15]:  # keep the news slice of the index small/fresh
        article_id = str(article.get("id"))
        if article_id in existing_ids:
            continue
        text = f"{article.get('title', '')}\n\n{(article.get('body') or '')[:600]}"
        try:
            embedding = embed_text(text, task_type="RETRIEVAL_DOCUMENT")
        except Exception as e:  # noqa: BLE001
            logger.warning("Failed to embed news article %s: %s", article_id, e)
            continue
        db.add(
            models.KnowledgeChunk(
                source_type="news",
                source_id=article_id,
                title=article.get("title", ""),
                text=text,
                embedding_json=json.dumps(embedding),
            )
        )
        count += 1

    if count:
        db.commit()
        # Keep the news slice of the index from growing unbounded.
        _prune_old_news(db, keep=50)
    return count


def _prune_old_news(db: Session, keep: int) -> None:
    news_chunks = (
        db.query(models.KnowledgeChunk)
        .filter(models.KnowledgeChunk.source_type == "news")
        .order_by(models.KnowledgeChunk.created_at.desc())
        .all()
    )
    for chunk in news_chunks[keep:]:
        db.delete(chunk)
    if len(news_chunks) > keep:
        db.commit()


def retrieve(db: Session, query: str, top_k: int = TOP_K) -> list[dict]:
    """Embeds the query and returns the top_k most similar stored chunks
    by cosine similarity. Returns [] gracefully if nothing is indexed yet
    or embedding fails, rather than raising - retrieval is an enhancement,
    not something that should break the chat endpoint."""
    chunks = db.query(models.KnowledgeChunk).all()
    if not chunks:
        return []

    try:
        query_embedding = np.array(embed_text(query, task_type="RETRIEVAL_QUERY"))
    except Exception as e:  # noqa: BLE001
        logger.warning("Failed to embed query for retrieval: %s", e)
        return []

    matrix = np.array([json.loads(c.embedding_json) for c in chunks])
    query_norm = query_embedding / (np.linalg.norm(query_embedding) + 1e-10)
    matrix_norm = matrix / (np.linalg.norm(matrix, axis=1, keepdims=True) + 1e-10)
    similarities = matrix_norm @ query_norm

    top_indices = np.argsort(similarities)[::-1][:top_k]
    results = []
    for i in top_indices:
        idx = int(i)
        results.append(
            {
                "source_type": chunks[idx].source_type,
                "source_id": chunks[idx].source_id,
                "title": chunks[idx].title,
                "text": chunks[idx].text,
                "score": float(similarities[idx]),
            }
        )
    return results
