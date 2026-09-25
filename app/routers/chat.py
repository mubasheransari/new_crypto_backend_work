import uuid

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.orm import Session

from app import models, schemas
from app.config import settings
from app.database import get_db
from app.auth_utils import get_optional_user
from app.services import chat_ai, rag

router = APIRouter(prefix="/chat", tags=["chat"])


def verify_admin(x_admin_key: str | None = Header(default=None)) -> None:
    if not x_admin_key or x_admin_key != settings.admin_api_key:
        raise HTTPException(status_code=401, detail="Invalid or missing admin key")


@router.post("", response_model=schemas.ChatResponse)
async def send_message(
    payload: schemas.ChatRequest,
    db: Session = Depends(get_db),
    current_user: models.User | None = Depends(get_optional_user),
):
    session_id = payload.session_id or uuid.uuid4().hex

    history_rows = (
        db.query(models.ChatMessage)
        .filter(models.ChatMessage.session_id == session_id)
        .order_by(models.ChatMessage.created_at.asc())
        .limit(20)  # keep recent context bounded
        .all()
    )
    history = [{"role": r.role, "content": r.content} for r in history_rows]

    # Store the user's message first so it's saved even if generation fails.
    db.add(
        models.ChatMessage(
            session_id=session_id,
            user_id=current_user.id if current_user else None,
            role="user",
            content=payload.message,
        )
    )
    db.commit()

    try:
        reply, sources, used_live_data = await chat_ai.generate_reply(
            db, payload.message, history
        )
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))

    import json as _json

    db.add(
        models.ChatMessage(
            session_id=session_id,
            user_id=current_user.id if current_user else None,
            role="assistant",
            content=reply,
            sources_json=_json.dumps(sources),
            used_live_data=used_live_data,
        )
    )
    db.commit()

    return schemas.ChatResponse(
        session_id=session_id,
        reply=reply,
        sources=[
            schemas.ChatSource(
                source_type=s["source_type"], source_id=s["source_id"], title=s["title"]
            )
            for s in sources
        ],
        used_live_data=used_live_data,
    )


@router.get("/history", response_model=list[schemas.ChatMessageOut])
def get_history(session_id: str, db: Session = Depends(get_db)):
    return (
        db.query(models.ChatMessage)
        .filter(models.ChatMessage.session_id == session_id)
        .order_by(models.ChatMessage.created_at.asc())
        .all()
    )


@router.post("/reindex")
def reindex_knowledge_base(
    db: Session = Depends(get_db),
    _: None = Depends(verify_admin),
):
    """Admin-only: rebuilds the RAG index from the current education
    content. Call this after editing app/routers/education.py's TOPICS."""
    try:
        count = rag.rebuild_index(db)
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))
    return {"chunks_indexed": count}
