from datetime import datetime, timedelta
from io import BytesIO
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app import models, schemas
from app.database import get_db
from app.auth_utils import get_optional_user, get_current_user
from app.services.gemini_vision import analyze_chart_image

router = APIRouter(prefix="/analyzer", tags=["analyzer"])

MAX_FILE_SIZE_MB = 10
ALLOWED_CONTENT_TYPES = {
    "image/png", "image/jpeg", "image/jpg", "image/webp",
    "image/heic", "image/heif",
}


def _analysis_out(record: models.ChartAnalysis, current_user: Optional[models.User]):
    owner = record.owner
    return schemas.ChartAnalysisOut(
        id=record.id,
        user_id=record.user_id,
        analyst_name=owner.full_name if owner else None,
        analyst_email=owner.email if owner else None,
        is_mine=bool(current_user and record.user_id == current_user.id),
        coin_hint=record.coin_hint,
        trend=record.trend,
        key_pattern=record.key_pattern,
        current_price=record.current_price,
        entry_price=record.entry_price,
        stop_loss=record.stop_loss,
        target_price=record.target_price,
        invalidation_level=record.invalidation_level,
        indicators=record.indicators,
        bullish_scenario=record.bullish_scenario,
        bearish_scenario=record.bearish_scenario,
        setup_clarity=record.setup_clarity,
        risk_level=record.risk_level,
        volatility_read=record.volatility_read,
        disclaimer=record.disclaimer,
        created_at=record.created_at,
    )


@router.post("/chart", response_model=schemas.ChartAnalysisOut)
async def analyze_chart(
    file: UploadFile = File(...),
    coin_hint: Optional[str] = Form(None),
    note: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    current_user: Optional[models.User] = Depends(get_optional_user),
):
    if file.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(status_code=400, detail="Unsupported file type. Please upload a PNG, JPG, WEBP, or HEIC/HEIF image.")

    image_bytes = await file.read()
    if len(image_bytes) > MAX_FILE_SIZE_MB * 1024 * 1024:
        raise HTTPException(status_code=400, detail=f"File too large. Max size is {MAX_FILE_SIZE_MB}MB.")

    user_note = note or ""
    if coin_hint:
        user_note = f"This is a chart for {coin_hint}. {user_note}".strip()

    try:
        analysis = await analyze_chart_image(image_bytes, file.filename or "chart.png", user_note)
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))

    record = models.ChartAnalysis(
        user_id=current_user.id if current_user else None,
        coin_hint=coin_hint,
        trend=analysis.trend,
        key_pattern=analysis.key_pattern,
        current_price=analysis.current_price,
        entry_price=analysis.entry_price,
        stop_loss=analysis.stop_loss,
        target_price=analysis.target_price,
        invalidation_level=analysis.invalidation_level,
        indicators=analysis.indicators,
        bullish_scenario=analysis.bullish_scenario,
        bearish_scenario=analysis.bearish_scenario,
        setup_clarity=analysis.setup_clarity,
        risk_level=analysis.risk_level,
        volatility_read=analysis.volatility_read,
        disclaimer=analysis.disclaimer,
    )
    db.add(record)
    db.flush()

    # Create an in-app notification for every other registered user.
    if current_user:
        others = db.query(models.User).filter(models.User.id != current_user.id).all()
        analyst = current_user.full_name or current_user.email
        for user in others:
            db.add(models.AnalysisNotification(
                user_id=user.id,
                analysis_id=record.id,
                message=f"{analyst} published a new chart analysis{(' for ' + coin_hint) if coin_hint else ''}.",
            ))

    db.commit()
    db.refresh(record)
    return _analysis_out(record, current_user)


@router.get("/history", response_model=list[schemas.ChartAnalysisOut])
def analysis_history(
    scope: str = "all",
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    limit = max(1, min(limit, 200))
    query = db.query(models.ChartAnalysis).order_by(models.ChartAnalysis.created_at.desc())
    if scope == "mine":
        query = query.filter(models.ChartAnalysis.user_id == current_user.id)
    elif scope == "other":
        query = query.filter(models.ChartAnalysis.user_id != current_user.id)
    records = query.limit(limit).all()
    return [_analysis_out(r, current_user) for r in records]


@router.get("/history/{analysis_id}", response_model=schemas.ChartAnalysisOut)
def get_analysis(
    analysis_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    record = db.query(models.ChartAnalysis).filter(models.ChartAnalysis.id == analysis_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="Analysis not found")
    return _analysis_out(record, current_user)


@router.get("/history/{analysis_id}/pdf")
def analysis_pdf(
    analysis_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    record = db.query(models.ChartAnalysis).filter(models.ChartAnalysis.id == analysis_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="Analysis not found")

    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib import colors
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.enums import TA_CENTER
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    except ImportError:
        raise HTTPException(status_code=500, detail="PDF support is not installed on the server.")

    owner = record.owner
    analyst = owner.full_name if owner else (owner.email if owner else "User")
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=42, leftMargin=42, topMargin=42, bottomMargin=42)
    styles = getSampleStyleSheet()
    title = ParagraphStyle("Title2", parent=styles["Title"], alignment=TA_CENTER, spaceAfter=14)
    section = ParagraphStyle("Section", parent=styles["Heading2"], spaceBefore=12, spaceAfter=6)
    body = ParagraphStyle("Body2", parent=styles["BodyText"], leading=15, spaceAfter=6)

    story = [
        Paragraph("Crypto Insights — Chart Analysis", title),
        Paragraph(f"<b>Analyst:</b> {analyst}", body),
        Paragraph(f"<b>Date:</b> {record.created_at.strftime('%d %b %Y, %I:%M %p')}", body),
        Paragraph(f"<b>Coin:</b> {record.coin_hint or 'Not specified'}", body),
        Spacer(1, 8),
        Paragraph("Market Read", section),
    ]
    rows = [
        ["Trend", record.trend], ["Key Pattern", record.key_pattern],
        ["Current Price", record.current_price], ["Entry Price", record.entry_price],
        ["Stop Loss", record.stop_loss], ["Target Price", record.target_price],
        ["Invalidation", record.invalidation_level], ["Indicators", record.indicators],
        ["Setup Clarity", record.setup_clarity], ["Risk Level", record.risk_level],
        ["Volatility", record.volatility_read],
    ]
    table = Table(rows, colWidths=[125, 355])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (0,-1), colors.HexColor("#EEF2FF")),
        ("BOX", (0,0), (-1,-1), 0.5, colors.HexColor("#CBD5E1")),
        ("INNERGRID", (0,0), (-1,-1), 0.25, colors.HexColor("#E2E8F0")),
        ("VALIGN", (0,0), (-1,-1), "TOP"), ("FONTNAME", (0,0), (0,-1), "Helvetica-Bold"),
        ("FONTSIZE", (0,0), (-1,-1), 9), ("LEFTPADDING", (0,0), (-1,-1), 7),
        ("RIGHTPADDING", (0,0), (-1,-1), 7), ("TOPPADDING", (0,0), (-1,-1), 7),
        ("BOTTOMPADDING", (0,0), (-1,-1), 7),
    ]))
    story.append(table)
    for heading, value in [
        ("Bullish Scenario", record.bullish_scenario),
        ("Bearish Scenario", record.bearish_scenario),
        ("Disclaimer", record.disclaimer),
    ]:
        story += [Paragraph(heading, section), Paragraph(value, body)]
    doc.build(story)
    buffer.seek(0)
    filename = f"analysis-{record.id}.pdf"
    return StreamingResponse(
        buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{filename}"'},
    )


@router.get("/notifications", response_model=list[schemas.AnalysisNotificationOut])
def notifications(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    return (db.query(models.AnalysisNotification)
            .filter(models.AnalysisNotification.user_id == current_user.id)
            .order_by(models.AnalysisNotification.created_at.desc())
            .limit(100).all())


@router.post("/notifications/read")
def mark_notifications_read(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    db.query(models.AnalysisNotification).filter(
        models.AnalysisNotification.user_id == current_user.id,
        models.AnalysisNotification.is_read == False,
    ).update({"is_read": True}, synchronize_session=False)
    db.commit()
    return {"status": "ok"}


@router.get("/notifications/unread-count")
def unread_count(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    count = db.query(models.AnalysisNotification).filter(
        models.AnalysisNotification.user_id == current_user.id,
        models.AnalysisNotification.is_read == False,
    ).count()
    return {"count": count}
