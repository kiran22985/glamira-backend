import asyncio
from datetime import datetime, timedelta, timezone

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    HTTPException,
    UploadFile,
    status,
)
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token as google_id_token
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .. import images, storage
from ..config import settings
from ..database import get_db
from ..deps import get_current_partner
from ..email_utils import send_password_reset_email
from ..models import Partner, PartnerPasswordResetToken
from ..schemas import (
    ForgotPasswordRequest,
    GoogleAuthRequest,
    MessageResponse,
    PartnerLoginRequest,
    PartnerResponse,
    PartnerSignupRequest,
    PartnerTokenResponse,
    ResetPasswordRequest,
)
from ..security import (
    create_access_token,
    generate_reset_code,
    hash_password,
    hash_reset_code,
    verify_password,
)

MAX_RESET_ATTEMPTS = 5

PARLOR_IMAGE_MAX_BYTES = 5 * 1024 * 1024  # 5 MB
# Matches the formats the partner app's picker offers.
PARLOR_IMAGE_FORMATS = {images.PNG, images.JPEG}

router = APIRouter(prefix="/partner/auth", tags=["partner-auth"])


def _verify_google_id_token(token: str, audience: str) -> dict:
    """Blocking Google ID-token verification (runs in a worker thread)."""
    return google_id_token.verify_oauth2_token(
        token, google_requests.Request(), audience
    )


async def _get_partner_by_email(db: AsyncSession, email: str) -> Partner | None:
    result = await db.execute(select(Partner).where(Partner.email == email.lower()))
    return result.scalar_one_or_none()


def _token_for(partner: Partner) -> PartnerTokenResponse:
    return PartnerTokenResponse(
        access_token=create_access_token(str(partner.id), role="partner"),
        partner=PartnerResponse.model_validate(partner),
    )


@router.post(
    "/signup",
    response_model=PartnerTokenResponse,
    status_code=status.HTTP_201_CREATED,
)
async def signup(payload: PartnerSignupRequest, db: AsyncSession = Depends(get_db)):
    if await _get_partner_by_email(db, payload.email):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A partner account with this email already exists.",
        )

    partner = Partner(
        full_name=payload.full_name.strip(),
        business_name=payload.business_name.strip(),
        email=payload.email.lower(),
        phone_number=payload.phone_number.strip(),
        address=payload.address.strip(),
        hashed_password=hash_password(payload.password),
    )
    db.add(partner)
    await db.commit()
    await db.refresh(partner)
    return _token_for(partner)


@router.post("/login", response_model=PartnerTokenResponse)
async def login(payload: PartnerLoginRequest, db: AsyncSession = Depends(get_db)):
    partner = await _get_partner_by_email(db, payload.email)
    if partner is None or not verify_password(
        payload.password, partner.hashed_password
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password.",
        )
    if not partner.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This partner account is disabled.",
        )
    return _token_for(partner)


@router.post("/google", response_model=PartnerTokenResponse)
async def google_auth(payload: GoogleAuthRequest, db: AsyncSession = Depends(get_db)):
    """Sign in an *existing* partner with a Google ID token.

    Unlike the customer endpoint this never creates an account: a partner
    record needs a business name, phone number and address, none of which a
    Google token carries. Unknown emails are told to sign up first.
    """
    if not settings.google_client_id:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Google sign-in is not configured on the server.",
        )

    try:
        idinfo = await asyncio.to_thread(
            _verify_google_id_token, payload.id_token, settings.google_client_id
        )
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired Google token.",
        )

    email = idinfo.get("email")
    if not email or not idinfo.get("email_verified", False):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Your Google account has no verified email.",
        )

    partner = await _get_partner_by_email(db, email.lower())
    if partner is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No partner account for this Google address. Please sign up first.",
        )
    if not partner.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This partner account is disabled.",
        )
    return _token_for(partner)


@router.post("/forgot-password", response_model=MessageResponse)
async def forgot_password(
    payload: ForgotPasswordRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    partner = await _get_partner_by_email(db, payload.email)
    # Always respond the same way so the endpoint can't be used to discover
    # which emails are registered.
    if partner is not None:
        code = generate_reset_code()
        reset = PartnerPasswordResetToken(
            partner_id=partner.id,
            code_hash=hash_reset_code(code),
            expires_at=datetime.now(timezone.utc)
            + timedelta(minutes=settings.reset_token_expire_minutes),
        )
        db.add(reset)
        await db.commit()
        background_tasks.add_task(send_password_reset_email, partner.email, code)

    return MessageResponse(
        message="If a partner account exists for that email, a reset code has been sent."
    )


@router.post("/reset-password", response_model=MessageResponse)
async def reset_password(
    payload: ResetPasswordRequest, db: AsyncSession = Depends(get_db)
):
    partner = await _get_partner_by_email(db, payload.email)
    if partner is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset code.",
        )

    # Most recent unused code for this partner.
    result = await db.execute(
        select(PartnerPasswordResetToken)
        .where(
            PartnerPasswordResetToken.partner_id == partner.id,
            PartnerPasswordResetToken.used == False,  # noqa: E712
        )
        .order_by(PartnerPasswordResetToken.created_at.desc())
    )
    reset = result.scalars().first()

    now = datetime.now(timezone.utc)
    if reset is None or reset.expires_at < now:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset code. Please request a new one.",
        )

    if reset.attempts >= MAX_RESET_ATTEMPTS:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many attempts. Please request a new reset code.",
        )

    if reset.code_hash != hash_reset_code(payload.code):
        reset.attempts += 1
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Incorrect code. Please try again.",
        )

    partner.hashed_password = hash_password(payload.new_password)
    reset.used = True
    await db.commit()
    return MessageResponse(
        message="Your password has been reset. You can now log in."
    )


@router.get("/me", response_model=PartnerResponse)
async def me(current_partner: Partner = Depends(get_current_partner)):
    return PartnerResponse.model_validate(current_partner)


@router.post("/me/parlor-image", response_model=PartnerResponse)
async def upload_parlor_image(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_partner: Partner = Depends(get_current_partner),
):
    """Replace the partner's parlor photo. JPEG or PNG, up to 5 MB."""
    contents = await file.read()
    if len(contents) > PARLOR_IMAGE_MAX_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Image is too large (max 5 MB).",
        )

    ext = images.detect_image_extension(contents)
    if ext not in PARLOR_IMAGE_FORMATS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported image type. Use JPG, JPEG or PNG.",
        )

    try:
        url = await asyncio.to_thread(
            storage.upload_image,
            contents,
            folder=storage.PARLOR_FOLDER,
            owner_id=str(current_partner.id),
        )
    except storage.StorageError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)
        )

    current_partner.image_url = url
    await db.commit()
    await db.refresh(current_partner)
    return PartnerResponse.model_validate(current_partner)


@router.delete("/me/parlor-image", response_model=PartnerResponse)
async def remove_parlor_image(
    db: AsyncSession = Depends(get_db),
    current_partner: Partner = Depends(get_current_partner),
):
    if current_partner.image_url:
        await asyncio.to_thread(
            storage.delete_image,
            folder=storage.PARLOR_FOLDER,
            owner_id=str(current_partner.id),
        )
        current_partner.image_url = None
        await db.commit()
        await db.refresh(current_partner)
    return PartnerResponse.model_validate(current_partner)
