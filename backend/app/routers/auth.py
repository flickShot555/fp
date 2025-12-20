"""Authentication API routes."""
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.database import get_db
from ..core.security import get_current_user, get_current_active_user
from ..models.user import User
from ..schemas.auth import (
    SignupRequest, SignupResponse, LoginRequest, TokenResponse,
    VerifyOTPRequest, SendOTPRequest, OTPSendRequest, OTPVerifyRequest,
    RefreshTokenRequest, PasswordResetRequest, PasswordResetConfirm, MFAToggleRequest
)
from ..services.auth_service import AuthService
from ..services.otp_service import OTPService


router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/signup", response_model=SignupResponse, status_code=status.HTTP_201_CREATED)
async def signup(
    request: SignupRequest,
    req: Request,
    db: AsyncSession = Depends(get_db)
):
    """Register a new user."""
    auth_service = AuthService(db)

    # Handle name field - split into first_name and last_name if provided
    first_name = request.first_name
    last_name = request.last_name
    if request.name and not (first_name or last_name):
        parts = request.name.strip().split(' ', 1)
        first_name = parts[0]
        last_name = parts[1] if len(parts) > 1 else ""

    try:
        user = await auth_service.signup(
            email=request.email,
            password=request.password,
            phone=request.phone,
            first_name=first_name,
            last_name=last_name,
            role=request.role,
            company_name=request.company_name,
            ip_address=req.client.host,
            user_agent=req.headers.get("user-agent"),
        )

        return SignupResponse(
            user_id=user.id,
            email=user.email,
            phone=user.phone,
            role=user.role.value,
            requires_email_verification=True,
            requires_phone_verification=bool(user.phone),
            message="Account created. Please verify your email.",
        )

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/login", response_model=TokenResponse)
async def login(
    request: LoginRequest,
    req: Request,
    response: Response,
    db: AsyncSession = Depends(get_db)
):
    """Authenticate user and return tokens."""
    auth_service = AuthService(db)
    
    try:
        result = await auth_service.login(
            email=request.email,
            password=request.password,
            ip_address=req.client.host,
            user_agent=req.headers.get("user-agent"),
        )
        
        # Set refresh token as HTTP-only cookie
        response.set_cookie(
            key="refresh_token",
            value=result["refresh_token"],
            httponly=True,
            secure=True,
            samesite="lax",
            max_age=7 * 24 * 60 * 60,  # 7 days
        )
        
        return TokenResponse(
            access_token=result["access_token"],
            refresh_token=result["refresh_token"],
            token_type="bearer",
            expires_in=result["expires_in"],
            user=result["user"],
        )
    
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    request: RefreshTokenRequest = None,
    req: Request = None,
    response: Response = None,
    db: AsyncSession = Depends(get_db)
):
    """Refresh access token using refresh token."""
    auth_service = AuthService(db)
    
    # Get refresh token from request body or cookie
    token = request.refresh_token if request else req.cookies.get("refresh_token")
    
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token required")
    
    try:
        result = await auth_service.refresh_token(
            refresh_token=token,
            ip_address=req.client.host,
            user_agent=req.headers.get("user-agent"),
        )
        
        # Update cookie
        response.set_cookie(
            key="refresh_token",
            value=result["refresh_token"],
            httponly=True,
            secure=True,
            samesite="lax",
            max_age=7 * 24 * 60 * 60,
        )
        
        return TokenResponse(
            access_token=result["access_token"],
            refresh_token=result["refresh_token"],
            token_type="bearer",
            expires_in=result["expires_in"],
            user=result["user"],
        )
    
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))


@router.post("/logout")
async def logout(
    response: Response,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Logout user and invalidate tokens."""
    auth_service = AuthService(db)
    await auth_service.logout(current_user.id)
    
    response.delete_cookie("refresh_token")
    
    return {"message": "Logged out successfully"}


@router.post("/send-otp")
async def send_otp(
    request: OTPSendRequest,
    db: AsyncSession = Depends(get_db)
):
    """Send OTP to email or phone."""
    otp_service = OTPService(db)
    
    try:
        await otp_service.send_otp(
            user_id=request.user_id,
            channel=request.channel,
            purpose=request.purpose,
        )
        return {"message": f"OTP sent to {request.channel}"}
    
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/verify-otp")
async def verify_otp(
    request: OTPVerifyRequest,
    db: AsyncSession = Depends(get_db)
):
    """Verify OTP code."""
    otp_service = OTPService(db)
    
    try:
        result = await otp_service.verify_otp(
            user_id=request.user_id,
            code=request.code,
            purpose=request.purpose,
        )
        return {"verified": result, "message": "OTP verified successfully" if result else "Invalid OTP"}
    
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/password-reset/request")
async def request_password_reset(
    request: PasswordResetRequest,
    db: AsyncSession = Depends(get_db)
):
    """Request password reset."""
    auth_service = AuthService(db)
    
    await auth_service.request_password_reset(request.email)
    
    return {"message": "If the email exists, a reset link has been sent."}


@router.post("/password-reset/confirm")
async def confirm_password_reset(
    request: PasswordResetConfirm,
    db: AsyncSession = Depends(get_db)
):
    """Confirm password reset with token."""
    auth_service = AuthService(db)
    
    try:
        await auth_service.reset_password(request.token, request.new_password)
        return {"message": "Password reset successfully"}
    
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/me")
async def get_current_user_info(
    current_user: User = Depends(get_current_active_user)
):
    """Get current user information."""
    return {
        "id": current_user.id,
        "email": current_user.email,
        "phone": current_user.phone,
        "first_name": current_user.first_name,
        "last_name": current_user.last_name,
        "role": current_user.role.value,
        "email_verified": current_user.email_verified,
        "phone_verified": current_user.phone_verified,
        "mfa_enabled": current_user.mfa_enabled,
        "created_at": current_user.created_at,
    }

