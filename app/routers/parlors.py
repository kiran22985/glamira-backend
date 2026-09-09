import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..models import Partner
from ..schemas import ParlorResponse

router = APIRouter(prefix="/parlors", tags=["parlors"])


@router.get("", response_model=list[ParlorResponse])
async def list_parlors(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    """Active parlors for the customer app's home screen.

    Public: the customer app shows parlors before anyone signs in. Only
    business-facing fields are exposed — see [ParlorResponse].
    """
    result = await db.execute(
        select(Partner)
        .where(Partner.is_active == True)  # noqa: E712
        .order_by(Partner.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return [ParlorResponse.model_validate(p) for p in result.scalars().all()]


@router.get("/{parlor_id}", response_model=ParlorResponse)
async def get_parlor(parlor_id: str, db: AsyncSession = Depends(get_db)):
    try:
        pid = uuid.UUID(parlor_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Parlor not found."
        )

    partner = await db.get(Partner, pid)
    if partner is None or not partner.is_active:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Parlor not found."
        )
    return ParlorResponse.model_validate(partner)
