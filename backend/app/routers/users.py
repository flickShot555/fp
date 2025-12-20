"""User management API routes."""
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.database import get_db
from ..core.security import get_current_user, get_current_active_user, require_roles
from ..models.user import User, UserRole
from ..schemas.user import (
    UserUpdate, UserProfileResponse, UserListResponse,
    OnboardingStatusResponse, UserPreferencesUpdate
)
from ..services.user_service import UserService
from ..services.onboarding_service import OnboardingService


router = APIRouter(prefix="/users", tags=["Users"])


@router.get("/me", response_model=UserProfileResponse)
async def get_my_profile(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Get current user's profile."""
    user_service = UserService(db)
    return await user_service.get_user_profile(current_user.id)


@router.put("/me", response_model=UserProfileResponse)
async def update_my_profile(
    data: UserUpdate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Update current user's profile."""
    user_service = UserService(db)
    
    try:
        user = await user_service.update_user(current_user.id, data)
        return await user_service.get_user_profile(user.id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.put("/me/preferences")
async def update_preferences(
    data: UserPreferencesUpdate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Update user preferences."""
    user_service = UserService(db)
    
    await user_service.update_preferences(current_user.id, data)
    return {"message": "Preferences updated"}


@router.get("/me/onboarding", response_model=OnboardingStatusResponse)
async def get_onboarding_status(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Get current user's onboarding status."""
    onboarding_service = OnboardingService(db)
    return await onboarding_service.get_onboarding_status(current_user.id)


@router.get("/me/coach-status")
async def get_coach_status(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Get AI coach status for onboarding."""
    onboarding_service = OnboardingService(db)
    return await onboarding_service.get_coach_status(current_user.id)


# Admin endpoints
@router.get("", response_model=UserListResponse)
async def list_users(
    role: Optional[UserRole] = None,
    is_active: bool = True,
    search: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(require_roles([UserRole.ADMIN, UserRole.SUPER_ADMIN])),
    db: AsyncSession = Depends(get_db)
):
    """List all users (admin only)."""
    user_service = UserService(db)
    
    users, total = await user_service.list_users(
        role=role,
        is_active=is_active,
        search=search,
        page=page,
        page_size=page_size,
    )
    
    return UserListResponse(
        users=users,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=(total + page_size - 1) // page_size,
    )


@router.get("/{user_id}", response_model=UserProfileResponse)
async def get_user(
    user_id: str,
    current_user: User = Depends(require_roles([UserRole.ADMIN, UserRole.SUPER_ADMIN])),
    db: AsyncSession = Depends(get_db)
):
    """Get user by ID (admin only)."""
    user_service = UserService(db)
    
    profile = await user_service.get_user_profile(user_id)
    if not profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    
    return profile


@router.put("/{user_id}", response_model=UserProfileResponse)
async def update_user(
    user_id: str,
    data: UserUpdate,
    current_user: User = Depends(require_roles([UserRole.ADMIN, UserRole.SUPER_ADMIN])),
    db: AsyncSession = Depends(get_db)
):
    """Update user by ID (admin only)."""
    user_service = UserService(db)
    
    try:
        user = await user_service.update_user(user_id, data, admin_id=current_user.id)
        return await user_service.get_user_profile(user.id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/{user_id}/deactivate")
async def deactivate_user(
    user_id: str,
    current_user: User = Depends(require_roles([UserRole.ADMIN, UserRole.SUPER_ADMIN])),
    db: AsyncSession = Depends(get_db)
):
    """Deactivate a user (admin only)."""
    user_service = UserService(db)
    
    try:
        await user_service.deactivate_user(user_id, admin_id=current_user.id)
        return {"message": "User deactivated"}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/{user_id}/reactivate")
async def reactivate_user(
    user_id: str,
    current_user: User = Depends(require_roles([UserRole.ADMIN, UserRole.SUPER_ADMIN])),
    db: AsyncSession = Depends(get_db)
):
    """Reactivate a user (admin only)."""
    user_service = UserService(db)
    
    try:
        await user_service.reactivate_user(user_id, admin_id=current_user.id)
        return {"message": "User reactivated"}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

