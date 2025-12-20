"""Notification service for alerts and notifications."""
from datetime import datetime
from typing import Optional, List, Tuple, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, update
import json

from ..models.message import Notification, NotificationType
from ..schemas.message import NotificationCreate
from ..core.config import settings


class NotificationService:
    """Service for notification management."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def create_notification(
        self,
        user_id: str,
        notification_type: NotificationType,
        title: str,
        message: str,
        resource_type: str = None,
        resource_id: str = None,
        action_url: str = None,
        channels: List[str] = None,
    ) -> Notification:
        """Create a new notification."""
        notification = Notification(
            user_id=user_id,
            notification_type=notification_type,
            title=title,
            message=message,
            resource_type=resource_type,
            resource_id=resource_id,
            action_url=action_url,
            channels=json.dumps(channels) if channels else json.dumps(["in_app"]),
        )
        
        self.db.add(notification)
        await self.db.commit()
        await self.db.refresh(notification)
        
        # Send via other channels
        if channels:
            await self._send_to_channels(notification, channels)
        
        return notification
    
    async def _send_to_channels(self, notification: Notification, channels: List[str]):
        """Send notification via specified channels."""
        if "email" in channels:
            await self._send_email_notification(notification)
        if "sms" in channels:
            await self._send_sms_notification(notification)
        if "push" in channels:
            await self._send_push_notification(notification)
    
    async def _send_email_notification(self, notification: Notification):
        """Send notification via email."""
        if not settings.SENDGRID_API_KEY:
            print(f"[DEV] Email notification to user {notification.user_id}: {notification.title}")
            return
        
        # Get user email
        from ..models.user import User
        result = await self.db.execute(select(User).where(User.id == notification.user_id))
        user = result.scalar_one_or_none()
        
        if not user or not user.email:
            return
        
        from sendgrid import SendGridAPIClient
        from sendgrid.helpers.mail import Mail
        
        mail = Mail(
            from_email=settings.SENDGRID_FROM_EMAIL,
            to_emails=user.email,
            subject=f"FreightPower AI - {notification.title}",
            html_content=f"<p>{notification.message}</p>",
        )
        
        sg = SendGridAPIClient(settings.SENDGRID_API_KEY)
        await sg.send(mail)
        
        notification.email_sent = True
    
    async def _send_sms_notification(self, notification: Notification):
        """Send notification via SMS."""
        if not settings.TWILIO_ACCOUNT_SID:
            print(f"[DEV] SMS notification to user {notification.user_id}: {notification.title}")
            return
        
        # Get user phone
        from ..models.user import User
        result = await self.db.execute(select(User).where(User.id == notification.user_id))
        user = result.scalar_one_or_none()
        
        if not user or not user.phone:
            return
        
        from twilio.rest import Client
        
        client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
        client.messages.create(
            body=f"{notification.title}: {notification.message}",
            from_=settings.TWILIO_PHONE_NUMBER,
            to=user.phone,
        )
        
        notification.sms_sent = True
    
    async def _send_push_notification(self, notification: Notification):
        """Send push notification."""
        # Placeholder for Firebase Cloud Messaging or other push service
        notification.push_sent = True
    
    async def get_user_notifications(
        self,
        user_id: str,
        is_read: bool = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Tuple[List[Notification], int, int]:
        """Get user's notifications."""
        query = select(Notification).where(Notification.user_id == user_id)
        
        if is_read is not None:
            query = query.where(Notification.is_read == is_read)
        
        # Count total
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await self.db.execute(count_query)
        total = total_result.scalar()
        
        # Count unread
        unread_query = select(func.count()).where(
            Notification.user_id == user_id,
            Notification.is_read == False
        )
        unread_result = await self.db.execute(unread_query)
        unread_count = unread_result.scalar()
        
        # Paginate
        query = query.order_by(Notification.created_at.desc())
        query = query.offset((page - 1) * page_size).limit(page_size)
        
        result = await self.db.execute(query)
        notifications = list(result.scalars().all())
        
        return notifications, total, unread_count
    
    async def mark_as_read(self, notification_ids: List[str] = None, user_id: str = None):
        """Mark notifications as read."""
        query = update(Notification).values(is_read=True, read_at=datetime.utcnow())
        
        if notification_ids:
            query = query.where(Notification.id.in_(notification_ids))
        elif user_id:
            query = query.where(Notification.user_id == user_id)
        else:
            raise ValueError("Must provide notification_ids or user_id")
        
        await self.db.execute(query)
        await self.db.commit()
    
    async def send_document_expiry_alert(self, user_id: str, document_type: str, days_until_expiry: int):
        """Send document expiry alert."""
        severity = "info" if days_until_expiry > 14 else "warning" if days_until_expiry > 7 else "critical"
        
        await self.create_notification(
            user_id=user_id,
            notification_type=NotificationType.DOCUMENT_EXPIRY,
            title=f"Document Expiring Soon",
            message=f"Your {document_type} expires in {days_until_expiry} days. Please renew it.",
            channels=["in_app", "email"] if days_until_expiry <= 7 else ["in_app"],
        )
    
    async def send_load_update(self, user_id: str, load_number: str, status: str, load_id: str):
        """Send load status update notification."""
        await self.create_notification(
            user_id=user_id,
            notification_type=NotificationType.LOAD_UPDATE,
            title=f"Load {load_number} Updated",
            message=f"Load status changed to: {status}",
            resource_type="load",
            resource_id=load_id,
            action_url=f"/loads/{load_id}",
            channels=["in_app"],
        )

