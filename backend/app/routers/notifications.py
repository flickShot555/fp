"""Notifications API routes."""
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.database import get_db
from ..core.security import get_current_user, get_current_active_user
from ..models.user import User
from ..schemas.message import NotificationResponse, NotificationListResponse
from ..services.notification_service import NotificationService


router = APIRouter(prefix="/notifications", tags=["Notifications"])


@router.get("", response_model=NotificationListResponse)
async def list_notifications(
    is_read: Optional[bool] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """List user's notifications."""
    notification_service = NotificationService(db)
    
    notifications, total, unread_count = await notification_service.get_user_notifications(
        user_id=current_user.id,
        is_read=is_read,
        page=page,
        page_size=page_size,
    )
    
    return NotificationListResponse(
        notifications=notifications,
        total=total,
        page=page,
        page_size=page_size,
        unread_count=unread_count,
    )


@router.get("/unread-count")
async def get_unread_count(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Get count of unread notifications."""
    notification_service = NotificationService(db)
    
    _, _, unread_count = await notification_service.get_user_notifications(
        user_id=current_user.id,
        is_read=False,
        page=1,
        page_size=1,
    )
    
    return {"unread_count": unread_count}


@router.post("/mark-read")
async def mark_notifications_read(
    notification_ids: Optional[List[str]] = None,
    mark_all: bool = False,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Mark notifications as read."""
    notification_service = NotificationService(db)
    
    if mark_all:
        await notification_service.mark_as_read(user_id=current_user.id)
    elif notification_ids:
        await notification_service.mark_as_read(notification_ids=notification_ids)
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Provide notification_ids or set mark_all=true"
        )
    
    return {"message": "Notifications marked as read"}


@router.post("/{notification_id}/read")
async def mark_single_notification_read(
    notification_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Mark a single notification as read."""
    notification_service = NotificationService(db)
    
    await notification_service.mark_as_read(notification_ids=[notification_id])
    
    return {"message": "Notification marked as read"}

