import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class SignupRequest(BaseModel):
    full_name: str = Field(min_length=1, max_length=255)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    phone_number: str = Field(min_length=7, max_length=32)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class GoogleAuthRequest(BaseModel):
    id_token: str


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    email: EmailStr
    code: str = Field(min_length=6, max_length=6, pattern=r"^\d{6}$")
    new_password: str = Field(min_length=8, max_length=128)


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    full_name: str
    email: EmailStr
    phone_number: str | None
    auth_provider: str
    avatar_url: str | None
    created_at: datetime


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


class MessageResponse(BaseModel):
    message: str


# --- Partner app ---------------------------------------------------------


class PartnerSignupRequest(BaseModel):
    full_name: str = Field(min_length=1, max_length=255)
    business_name: str = Field(min_length=1, max_length=255)
    email: EmailStr
    phone_number: str = Field(min_length=7, max_length=32)
    address: str = Field(min_length=1, max_length=512)
    password: str = Field(min_length=8, max_length=128)


class PartnerLoginRequest(BaseModel):
    email: EmailStr
    password: str


class PartnerResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    full_name: str
    business_name: str
    email: EmailStr
    phone_number: str
    address: str
    is_active: bool
    created_at: datetime


class PartnerTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    partner: PartnerResponse
