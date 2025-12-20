"""Settings API routes."""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from ..core.database import get_db
from ..core.security import get_current_user, get_current_active_user, require_roles
from ..models.user import User, UserRole
from ..services.user_service import UserService
from ..services.auth_service import AuthService


router = APIRouter(prefix="/settings", tags=["Settings"])


class NotificationPreferences(BaseModel):
    email_notifications: bool = True
    sms_notifications: bool = True
    push_notifications: bool = True
    load_alerts: bool = True
    document_reminders: bool = True
    marketing_emails: bool = False


class PasswordChange(BaseModel):
    current_password: str
    new_password: str


class MFASetup(BaseModel):
    enable: bool
    method: str = "totp"  # totp, sms, email


@router.get("/profile")
async def get_profile_settings(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Get user profile settings."""
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
        "timezone": current_user.timezone,
        "language": current_user.language,
        "created_at": current_user.created_at,
    }


@router.put("/profile")
async def update_profile_settings(
    first_name: Optional[str] = None,
    last_name: Optional[str] = None,
    phone: Optional[str] = None,
    timezone: Optional[str] = None,
    language: Optional[str] = None,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Update user profile settings."""
    user_service = UserService(db)
    
    from ..schemas.user import UserUpdate
    
    update_data = UserUpdate(
        first_name=first_name,
        last_name=last_name,
        phone=phone,
        timezone=timezone,
        language=language,
    )
    
    user = await user_service.update_user(current_user.id, update_data)
    
    return {"message": "Profile updated", "user": user}


@router.put("/notifications")
async def update_notification_preferences(
    preferences: NotificationPreferences,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Update notification preferences."""
    user_service = UserService(db)
    
    from ..schemas.user import UserPreferencesUpdate
    
    await user_service.update_preferences(
        current_user.id,
        UserPreferencesUpdate(**preferences.model_dump())
    )
    
    return {"message": "Notification preferences updated"}


@router.get("/notifications")
async def get_notification_preferences(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Get notification preferences."""
    # Return default preferences (would be stored in user preferences in production)
    return NotificationPreferences()


@router.post("/password")
async def change_password(
    data: PasswordChange,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Change user password."""
    auth_service = AuthService(db)
    
    try:
        await auth_service.change_password(
            user_id=current_user.id,
            current_password=data.current_password,
            new_password=data.new_password,
        )
        return {"message": "Password changed successfully"}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/mfa")
async def setup_mfa(
    data: MFASetup,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Enable or disable MFA."""
    auth_service = AuthService(db)
    
    if data.enable:
        result = await auth_service.enable_mfa(current_user.id, method=data.method)
        return {"message": "MFA enabled", "setup": result}
    else:
        await auth_service.disable_mfa(current_user.id)
        return {"message": "MFA disabled"}


@router.get("/mfa/status")
async def get_mfa_status(
    current_user: User = Depends(get_current_active_user),
):
    """Get MFA status."""
    return {
        "enabled": current_user.mfa_enabled,
        "method": current_user.mfa_method if hasattr(current_user, 'mfa_method') else None,
    }


@router.delete("/account")
async def delete_account(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Request account deletion."""
    user_service = UserService(db)
    
    # Soft delete - mark as inactive
    await user_service.deactivate_user(current_user.id)
    
    return {"message": "Account deactivation requested. Your account will be deleted in 30 days."}

