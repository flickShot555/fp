"""Messaging and Notification schemas."""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime

from ..models.message import NotificationType


class ConversationCreate(BaseModel):
    """Create conversation request."""
    subject: Optional[str] = None
    conversation_type: str = "direct"  # direct, group, load
    participant_ids: List[str]
    load_id: Optional[str] = None


class ConversationResponse(BaseModel):
    """Conversation response."""
    id: str
    subject: Optional[str]
    conversation_type: str
    load_id: Optional[str]
    participants: List[str]
    is_active: bool
    last_message_at: Optional[datetime]
    last_message_preview: Optional[str]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ConversationListResponse(BaseModel):
    """Paginated conversation list."""
    items: List[ConversationResponse]
    total: int
    page: int
    page_size: int


class MessageCreate(BaseModel):
    """Create message request."""
    conversation_id: str
    content: str
    message_type: str = "text"  # text, file, image, system
    attachments: Optional[List[str]] = None


class MessageResponse(BaseModel):
    """Message response."""
    id: str
    conversation_id: str
    sender_id: str
    sender_name: Optional[str] = None
    content: str
    message_type: str
    attachments: Optional[List[str]]
    read_by: Optional[Dict[str, datetime]]
    is_edited: bool
    is_deleted: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class MessageListResponse(BaseModel):
    """Paginated message list."""
    items: List[MessageResponse]
    total: int
    page: int
    page_size: int
    has_more: bool


class NotificationCreate(BaseModel):
    """Create notification request."""
    user_id: str
    notification_type: NotificationType
    title: str
    message: str
    resource_type: Optional[str] = None
    resource_id: Optional[str] = None
    action_url: Optional[str] = None
    channels: Optional[List[str]] = None  # in_app, email, sms, push


class NotificationResponse(BaseModel):
    """Notification response."""
    id: str
    user_id: str
    notification_type: NotificationType
    title: str
    message: str
    resource_type: Optional[str]
    resource_id: Optional[str]
    action_url: Optional[str]
    is_read: bool
    read_at: Optional[datetime]
    created_at: datetime

    class Config:
        from_attributes = True


class NotificationListResponse(BaseModel):
    """Paginated notification list."""
    items: List[NotificationResponse]
    total: int
    unread_count: int
    page: int
    page_size: int


class MarkNotificationsReadRequest(BaseModel):
    """Mark notifications as read."""
    notification_ids: Optional[List[str]] = None  # None = mark all
    

class AlertCreate(BaseModel):
    """Create alert request."""
    alert_type: str  # document_expiry, compliance, load_status, system
    title: str
    message: str
    severity: str = "info"  # info, warning, error, critical
    user_id: Optional[str] = None
    resource_type: Optional[str] = None
    resource_id: Optional[str] = None


class AlertResponse(BaseModel):
    """Alert response."""
    id: str
    alert_type: str
    title: str
    message: str
    severity: str
    user_id: Optional[str]
    resource_type: Optional[str]
    resource_id: Optional[str]
    is_acknowledged: bool
    acknowledged_at: Optional[datetime]
    created_at: datetime

