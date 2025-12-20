"""User schemas."""
from pydantic import BaseModel, EmailStr, Field
from typing import Optional, Dict, Any
from datetime import datetime

from ..models.user import UserRole


class UserUpdate(BaseModel):
    """User profile update."""
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    phone: Optional[str] = None
    avatar_url: Optional[str] = None
    language: Optional[str] = None
    timezone: Optional[str] = None
    notification_preferences: Optional[Dict[str, Any]] = None


class UserPreferencesUpdate(BaseModel):
    """User preferences update."""
    email_notifications: Optional[bool] = None
    sms_notifications: Optional[bool] = None
    push_notifications: Optional[bool] = None
    load_alerts: Optional[bool] = None
    document_reminders: Optional[bool] = None
    marketing_emails: Optional[bool] = None


class UserProfileResponse(BaseModel):
    """Full user profile response."""
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
    language: str
    timezone: str
    notification_preferences: Optional[Dict[str, Any]]
    company_id: Optional[str]
    created_at: datetime
    updated_at: datetime
    last_login_at: Optional[datetime]

    class Config:
        from_attributes = True


class OnboardingStepUpdate(BaseModel):
    """Update onboarding step."""
    step: str
    completed: bool = False
    score_delta: int = 0


class OnboardingStatusResponse(BaseModel):
    """Onboarding status response."""
    user_id: str
    current_step: str
    score: int
    completed: bool
    steps: list
    next_actions: list
    missing_documents: list


class AuditLogResponse(BaseModel):
    """Audit log entry response."""
    id: str
    user_id: str
    action: str
    resource_type: Optional[str]
    resource_id: Optional[str]
    details: Optional[str]
    ip_address: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class UserListResponse(BaseModel):
    """Paginated user list response."""
    items: list
    total: int
    page: int
    page_size: int
    pages: int


class AdminUserCreate(BaseModel):
    """Admin create user request."""
    email: EmailStr
    phone: Optional[str] = None
    password: str = Field(..., min_length=8)
    name: str
    role: UserRole
    company_id: Optional[str] = None
    is_verified: bool = False


class AdminUserUpdate(BaseModel):
    """Admin update user request."""
    name: Optional[str] = None
    role: Optional[UserRole] = None
    is_active: Optional[bool] = None
    is_locked: Optional[bool] = None
    is_verified: Optional[bool] = None
    company_id: Optional[str] = None

