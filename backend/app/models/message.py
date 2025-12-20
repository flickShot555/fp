"""Messaging and Notification related database models."""
from sqlalchemy import Column, String, Boolean, DateTime, Enum, ForeignKey, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum
import uuid

from ..core.database import Base


class NotificationType(str, enum.Enum):
    """Types of notifications."""
    LOAD_UPDATE = "load_update"
    DOCUMENT_EXPIRY = "document_expiry"
    MESSAGE = "message"
    COMPLIANCE_ALERT = "compliance_alert"
    PAYMENT = "payment"
    TASK = "task"
    SYSTEM = "system"
    ONBOARDING = "onboarding"
    TRAINING = "training"


class Conversation(Base):
    """Conversation/Chat thread model."""
    __tablename__ = "conversations"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    
    # Conversation metadata
    subject = Column(String(255), nullable=True)
    conversation_type = Column(String(50), default="direct")  # direct, group, load
    
    # Related entities
    load_id = Column(String(36), ForeignKey("loads.id"), nullable=True)
    
    # Participants (stored as JSON array of user IDs)
    participants = Column(Text, nullable=False)  # JSON array
    
    # Status
    is_active = Column(Boolean, default=True)
    
    # Last message info
    last_message_at = Column(DateTime, nullable=True)
    last_message_preview = Column(String(255), nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class Message(Base):
    """Message model."""
    __tablename__ = "messages"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    
    # Conversation
    conversation_id = Column(String(36), ForeignKey("conversations.id"), nullable=False, index=True)
    
    # Sender
    sender_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    
    # Content
    content = Column(Text, nullable=False)
    message_type = Column(String(50), default="text")  # text, file, image, system
    
    # Attachments
    attachments = Column(Text, nullable=True)  # JSON array of file URLs
    
    # Read status (stored as JSON of user_id: timestamp)
    read_by = Column(Text, nullable=True)  # JSON
    
    # Status
    is_edited = Column(Boolean, default=False)
    is_deleted = Column(Boolean, default=False)
    deleted_at = Column(DateTime, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    
    # Relationships
    sender = relationship("User", back_populates="sent_messages")


class Notification(Base):
    """Notification model."""
    __tablename__ = "notifications"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    
    # Recipient
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    
    # Content
    notification_type = Column(Enum(NotificationType), nullable=False)
    title = Column(String(255), nullable=False)
    message = Column(Text, nullable=False)
    
    # Related entity
    resource_type = Column(String(100), nullable=True)  # load, document, message, etc.
    resource_id = Column(String(36), nullable=True)
    action_url = Column(String(500), nullable=True)
    
    # Delivery
    channels = Column(Text, nullable=True)  # JSON: ["in_app", "email", "sms", "push"]
    email_sent = Column(Boolean, default=False)
    sms_sent = Column(Boolean, default=False)
    push_sent = Column(Boolean, default=False)
    
    # Status
    is_read = Column(Boolean, default=False, index=True)
    read_at = Column(DateTime, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, server_default=func.now())
    
    # Relationships
    user = relationship("User", back_populates="notifications")

