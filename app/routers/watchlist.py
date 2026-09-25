from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import models, schemas
from app.database import get_db
from app.auth_utils import get_current_user

router = APIRouter(prefix="/watchlist", tags=["watchlist"])


@router.get("", response_model=list[schemas.WatchlistOut])
def get_watchlist(
    db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)
):
    return (
        db.query(models.WatchlistItem)
        .filter(models.WatchlistItem.user_id == current_user.id)
        .all()
    )


@router.post("", response_model=schemas.WatchlistOut, status_code=201)
def add_to_watchlist(
    payload: schemas.WatchlistAdd,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    existing = (
        db.query(models.WatchlistItem)
        .filter(
            models.WatchlistItem.user_id == current_user.id,
            models.WatchlistItem.coin_id == payload.coin_id,
        )
        .first()
    )
    if existing:
        raise HTTPException(status_code=400, detail="Already in watchlist")

    item = models.WatchlistItem(
        user_id=current_user.id, coin_id=payload.coin_id, symbol=payload.symbol
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.delete("/{coin_id}", status_code=204)
def remove_from_watchlist(
    coin_id: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    item = (
        db.query(models.WatchlistItem)
        .filter(
            models.WatchlistItem.user_id == current_user.id,
            models.WatchlistItem.coin_id == coin_id,
        )
        .first()
    )
    if not item:
        raise HTTPException(status_code=404, detail="Not in watchlist")
    db.delete(item)
    db.commit()
    return None
