import os
import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app import models, schemas
from app.config import settings
from app.database import get_db

router = APIRouter(prefix="/trade-of-day", tags=["trade-of-day"])

UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static", "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

ALLOWED_CONTENT_TYPES = {"image/png", "image/jpeg", "image/jpg", "image/webp"}
MAX_FILE_SIZE_MB = 10


def verify_admin(x_admin_key: Optional[str] = Header(default=None)) -> None:
    if not x_admin_key or x_admin_key != settings.admin_api_key:
        raise HTTPException(status_code=401, detail="Invalid or missing admin key")


@router.get("/latest", response_model=schemas.TradeOfDayOut)
def get_latest(db: Session = Depends(get_db)):
    trade = (
        db.query(models.TradeOfTheDay)
        .order_by(models.TradeOfTheDay.trade_datetime.desc())
        .first()
    )
    if not trade:
        raise HTTPException(status_code=404, detail="No Trade of the Day posted yet")
    return trade


@router.get("", response_model=list[schemas.TradeOfDayOut])
def list_trades(limit: int = 20, db: Session = Depends(get_db)):
    return (
        db.query(models.TradeOfTheDay)
        .order_by(models.TradeOfTheDay.trade_datetime.desc())
        .limit(min(limit, 100))
        .all()
    )


@router.post("", response_model=schemas.TradeOfDayOut, status_code=201)
async def create_trade(
    title: str = Form(...),
    description: str = Form(...),
    trade_datetime: str = Form(..., description="ISO 8601, e.g. 2026-08-04T14:30"),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    _: None = Depends(verify_admin),
):
    if file.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=400,
            detail="Unsupported file type. Please upload a PNG, JPG, or WEBP image.",
        )

    image_bytes = await file.read()
    if len(image_bytes) > MAX_FILE_SIZE_MB * 1024 * 1024:
        raise HTTPException(
            status_code=400, detail=f"File too large. Max size is {MAX_FILE_SIZE_MB}MB."
        )

    try:
        parsed_datetime = datetime.fromisoformat(trade_datetime)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="trade_datetime must be ISO 8601, e.g. 2026-08-04T14:30",
        )

    ext = os.path.splitext(file.filename or "")[1] or ".jpg"
    unique_name = f"{uuid.uuid4().hex}{ext}"
    file_path = os.path.join(UPLOAD_DIR, unique_name)
    with open(file_path, "wb") as f:
        f.write(image_bytes)

    trade = models.TradeOfTheDay(
        title=title,
        description=description,
        image_url=f"/static/uploads/{unique_name}",
        trade_datetime=parsed_datetime,
    )
    db.add(trade)
    db.commit()
    db.refresh(trade)
    return trade


@router.delete("/{trade_id}", status_code=204)
def delete_trade(
    trade_id: int,
    db: Session = Depends(get_db),
    _: None = Depends(verify_admin),
):
    trade = (
        db.query(models.TradeOfTheDay)
        .filter(models.TradeOfTheDay.id == trade_id)
        .first()
    )
    if not trade:
        raise HTTPException(status_code=404, detail="Trade of the Day entry not found")

    if trade.image_url:
        try:
            os.remove(os.path.join(UPLOAD_DIR, os.path.basename(trade.image_url)))
        except OSError:
            pass

    db.delete(trade)
    db.commit()
    return None
