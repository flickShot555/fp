"""User-related database models."""
from sqlalchemy import Column, String, Boolean, DateTime, Enum, ForeignKey, Text, Integer
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from datetime import datetime
import enum
import uuid

from ..core.database import Base


class UserRole(str, enum.Enum):
    """User roles in the system."""
    CARRIER = "carrier"
    DRIVER = "driver"
    SHIPPER = "shipper"
    BROKER = "broker"
    ADMIN = "admin"
    SUPER_ADMIN = "super_admin"


class User(Base):
    """User account model."""
    __tablename__ = "users"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    email = Column(String(255), unique=True, nullable=False, index=True)
    phone = Column(String(20), unique=True, nullable=True, index=True)
    password_hash = Column(String(255), nullable=False)
    
    # Profile
    first_name = Column(String(100), nullable=True)
    last_name = Column(String(100), nullable=True)
    role = Column(Enum(UserRole), nullable=False, default=UserRole.CARRIER)
    avatar_url = Column(String(500), nullable=True)

    @property
    def name(self) -> str:
        """Get full name."""
        parts = [self.first_name, self.last_name]
        return " ".join(p for p in parts if p) or self.email.split("@")[0]
    
    # Verification
    email_verified = Column(Boolean, default=False)
    phone_verified = Column(Boolean, default=False)
    is_verified = Column(Boolean, default=False)
    verified_at = Column(DateTime, nullable=True)
    
    # MFA
    mfa_enabled = Column(Boolean, default=False)
    mfa_secret = Column(String(255), nullable=True)
    
    # Status
    is_active = Column(Boolean, default=True)
    is_locked = Column(Boolean, default=False)
    failed_login_attempts = Column(Integer, default=0)
    locked_until = Column(DateTime, nullable=True)
    
    # Onboarding
    onboarding_completed = Column(Boolean, default=False)
    onboarding_step = Column(String(50), default="WELCOME")
    onboarding_score = Column(Integer, default=0)
    onboarding_data = Column(Text, nullable=True)  # JSON string of onboarding form data

    # Business Info (from onboarding)
    company_name = Column(String(255), nullable=True)
    dot_number = Column(String(50), nullable=True)
    mc_number = Column(String(50), nullable=True)
    full_name = Column(String(255), nullable=True)
    
    # Preferences
    language = Column(String(10), default="en")
    timezone = Column(String(50), default="UTC")
    notification_preferences = Column(Text, nullable=True)  # JSON string
    
    # Timestamps
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    last_login_at = Column(DateTime, nullable=True)
    
    # Foreign Keys
    company_id = Column(String(36), ForeignKey("companies.id"), nullable=True)
    firebase_uid = Column(String(128), unique=True, nullable=True, index=True)
    
    # Relationships
    company = relationship("Company", back_populates="users")
    documents = relationship("Document", back_populates="owner")
    audit_logs = relationship("AuditLog", back_populates="user")
    refresh_tokens = relationship("RefreshToken", back_populates="user")
    sent_messages = relationship("Message", foreign_keys="Message.sender_id", back_populates="sender")
    notifications = relationship("Notification", back_populates="user")
    tasks = relationship("Task", foreign_keys="Task.user_id", back_populates="user")
    calendar_events = relationship("CalendarEvent", back_populates="user")


class AuditLog(Base):
    """Audit log for tracking user actions."""
    __tablename__ = "audit_logs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=True, index=True)
    action = Column(String(100), nullable=False, index=True)
    resource_type = Column(String(100), nullable=True)
    resource_id = Column(String(36), nullable=True)
    details = Column(Text, nullable=True)
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(String(500), nullable=True)
    created_at = Column(DateTime, server_default=func.now())

    # Relationships
    user = relationship("User", back_populates="audit_logs")


class OTPVerification(Base):
    """OTP verification records."""
    __tablename__ = "otp_verifications"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=True)
    email = Column(String(255), nullable=True)
    phone = Column(String(20), nullable=True)
    otp_code = Column(String(10), nullable=False)
    otp_type = Column(String(20), nullable=False)  # email, sms, mfa
    expires_at = Column(DateTime, nullable=False)
    verified = Column(Boolean, default=False)
    attempts = Column(Integer, default=0)
    created_at = Column(DateTime, server_default=func.now())


class RefreshToken(Base):
    """Refresh token storage for token rotation."""
    __tablename__ = "refresh_tokens"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    token_hash = Column(String(255), nullable=False, unique=True)
    expires_at = Column(DateTime, nullable=False)
    revoked = Column(Boolean, default=False)
    revoked_at = Column(DateTime, nullable=True)
    replaced_by = Column(String(36), nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    
    # Relationships
    user = relationship("User", back_populates="refresh_tokens")

