"""Authentication schemas."""
from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List
from datetime import datetime

from ..models.user import UserRole


class SignupRequest(BaseModel):
    """User signup request."""
    email: EmailStr
    phone: Optional[str] = None
    password: str = Field(..., min_length=8)
    name: Optional[str] = None  # Full name from frontend
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    role: UserRole = UserRole.CARRIER
    company_name: Optional[str] = None
    usdot: Optional[str] = None
    mc_number: Optional[str] = None


class SignupResponse(BaseModel):
    """User signup response."""
    user_id: str
    email: str
    phone: Optional[str] = None
    role: str
    requires_email_verification: bool = True
    requires_phone_verification: bool = False
    message: str


class LoginRequest(BaseModel):
    """User login request."""
    email: EmailStr
    password: str
    mfa_code: Optional[str] = None


class TokenResponse(BaseModel):
    """JWT token response."""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    user: "UserResponse"


class RefreshTokenRequest(BaseModel):
    """Refresh token request."""
    refresh_token: str


class SendOTPRequest(BaseModel):
    """Request to send OTP."""
    user_id: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    channel: str = "email"  # email, sms
    purpose: str = "verification"  # verification, login, password_reset


class VerifyOTPRequest(BaseModel):
    """OTP verification request."""
    user_id: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    code: str = Field(..., min_length=6, max_length=6)
    purpose: str = "verification"


# Aliases for frontend compatibility
OTPVerifyRequest = VerifyOTPRequest
OTPSendRequest = SendOTPRequest


class PasswordResetRequest(BaseModel):
    """Password reset request."""
    email: EmailStr


class PasswordResetConfirm(BaseModel):
    """Password reset confirmation."""
    token: str
    new_password: str = Field(..., min_length=8)


class MFAToggleRequest(BaseModel):
    """MFA enable/disable request."""
    enabled: bool
    mfa_type: str = "sms"  # sms, email, authenticator


class ChangePasswordRequest(BaseModel):
    """Change password request."""
    current_password: str
    new_password: str = Field(..., min_length=8)


class UserResponse(BaseModel):
    """User response schema."""
    id: str
    email: str
    phone: Optional[str]
    name: str
    role: UserRole
    avatar_url: Optional[str]
    email_verified: bool
    phone_verified: bool
    is_verified: bool
    mfa_enabled: bool
    onboarding_completed: bool
    onboarding_step: str
    onboarding_score: int
    company_id: Optional[str]
    created_at: datetime
    last_login_at: Optional[datetime]

    class Config:
        from_attributes = True


# Update forward reference
TokenResponse.model_rebuild()

