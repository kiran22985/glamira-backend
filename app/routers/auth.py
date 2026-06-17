import asyncio
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token as google_id_token
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..database import get_db
from ..deps import get_current_user
from ..email_utils import send_password_reset_email
from ..models import PasswordResetToken, User
from ..schemas import (
    ForgotPasswordRequest,
    GoogleAuthRequest,
    LoginRequest,
    MessageResponse,
    ResetPasswordRequest,
    SignupRequest,
    TokenResponse,
    UserResponse,
)
from ..security import (
    create_access_token,
    generate_reset_token,
    hash_password,
    hash_reset_token,
    verify_password,
)


def _verify_google_id_token(token: str, audience: str) -> dict:
    """Blocking Google ID-token verification (runs in a worker thread)."""
    return google_id_token.verify_oauth2_token(
        token, google_requests.Request(), audience
    )

router = APIRouter(prefix="/auth", tags=["auth"])


async def _get_user_by_email(db: AsyncSession, email: str) -> User | None:
    result = await db.execute(select(User).where(User.email == email.lower()))
    return result.scalar_one_or_none()


def _token_for(user: User) -> TokenResponse:
    return TokenResponse(
        access_token=create_access_token(str(user.id)),
        user=UserResponse.model_validate(user),
    )


@router.post(
    "/signup", response_model=TokenResponse, status_code=status.HTTP_201_CREATED
)
async def signup(payload: SignupRequest, db: AsyncSession = Depends(get_db)):
    if await _get_user_by_email(db, payload.email):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists.",
        )

    user = User(
        full_name=payload.full_name.strip(),
        email=payload.email.lower(),
        phone_number=payload.phone_number,
        hashed_password=hash_password(payload.password),
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return _token_for(user)


@router.post("/login", response_model=TokenResponse)
async def login(payload: LoginRequest, db: AsyncSession = Depends(get_db)):
    user = await _get_user_by_email(db, payload.email)
    if user is None or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password.",
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Account is disabled."
        )
    return _token_for(user)


@router.post("/google", response_model=TokenResponse)
async def google_auth(
    payload: GoogleAuthRequest, db: AsyncSession = Depends(get_db)
):
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

    email = email.lower()
    user = await _get_user_by_email(db, email)
    if user is None:
        # First Google sign-in → create the account. No usable password is set
        # (a random hash keeps the column populated); they sign in via Google.
        user = User(
            full_name=idinfo.get("name") or email.split("@")[0],
            email=email,
            hashed_password=hash_password(secrets.token_urlsafe(32)),
            auth_provider="google",
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)

    return _token_for(user)


@router.post("/forgot-password", response_model=MessageResponse)
async def forgot_password(
    payload: ForgotPasswordRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    user = await _get_user_by_email(db, payload.email)
    # Always respond the same way so the endpoint can't be used to discover
    # which emails are registered.
    if user is not None:
        raw_token, token_hash = generate_reset_token()
        reset = PasswordResetToken(
            user_id=user.id,
            token_hash=token_hash,
            expires_at=datetime.now(timezone.utc)
            + timedelta(minutes=settings.reset_token_expire_minutes),
        )
        db.add(reset)
        await db.commit()
        background_tasks.add_task(
            send_password_reset_email, user.email, raw_token
        )

    return MessageResponse(
        message="If an account exists for that email, a reset link has been sent."
    )


@router.post("/reset-password", response_model=MessageResponse)
async def reset_password(
    payload: ResetPasswordRequest, db: AsyncSession = Depends(get_db)
):
    token_hash = hash_reset_token(payload.token)
    result = await db.execute(
        select(PasswordResetToken).where(
            PasswordResetToken.token_hash == token_hash
        )
    )
    reset = result.scalar_one_or_none()

    now = datetime.now(timezone.utc)
    if reset is None or reset.used or reset.expires_at < now:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This reset link is invalid or has expired.",
        )

    user = await db.get(User, reset.user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid reset link."
        )

    user.hashed_password = hash_password(payload.new_password)
    reset.used = True
    await db.commit()
    return MessageResponse(message="Your password has been reset. You can now log in.")


@router.get("/me", response_model=UserResponse)
async def me(current_user: User = Depends(get_current_user)):
    return UserResponse.model_validate(current_user)
