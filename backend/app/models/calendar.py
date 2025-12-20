"""Calendar and Task related database models."""
from sqlalchemy import Column, String, Boolean, DateTime, Enum, ForeignKey, Text, Integer
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum
import uuid

from ..core.database import Base


class TaskStatus(str, enum.Enum):
    """Task completion status."""
    TODO = "todo"
    IN_PROGRESS = "in_progress"
    BLOCKED = "blocked"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class CalendarEvent(Base):
    """Calendar event model."""
    __tablename__ = "calendar_events"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    
    # Owner
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    
    # Event details
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    event_type = Column(String(50), default="general")  # pickup, delivery, meeting, training, etc.
    
    # Timing
    start_time = Column(DateTime, nullable=False)
    end_time = Column(DateTime, nullable=False)
    all_day = Column(Boolean, default=False)
    timezone = Column(String(50), default="UTC")
    
    # Recurrence
    is_recurring = Column(Boolean, default=False)
    recurrence_rule = Column(String(255), nullable=True)  # RRULE format
    
    # Location
    location = Column(String(255), nullable=True)
    location_lat = Column(String(20), nullable=True)
    location_lng = Column(String(20), nullable=True)
    
    # Related entities
    load_id = Column(String(36), ForeignKey("loads.id"), nullable=True)
    
    # External sync
    external_id = Column(String(255), nullable=True)  # Google/Outlook event ID
    external_source = Column(String(50), nullable=True)  # google, outlook
    
    # Reminders (stored as JSON array of minutes before event)
    reminders = Column(Text, nullable=True)  # JSON
    
    # Status
    status = Column(String(50), default="confirmed")  # confirmed, tentative, cancelled
    
    # Timestamps
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    
    # Relationships
    user = relationship("User", back_populates="calendar_events")


class Task(Base):
    """Task model for action items and to-dos."""
    __tablename__ = "tasks"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    
    # Owner/Assignee
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    assigned_by = Column(String(36), ForeignKey("users.id"), nullable=True)
    
    # Task details
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    task_type = Column(String(50), default="general")  # onboarding, compliance, document, load, etc.
    
    # Priority and status
    priority = Column(String(20), default="medium")  # low, medium, high, urgent
    status = Column(Enum(TaskStatus), default=TaskStatus.TODO, index=True)
    
    # Due date
    due_date = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    
    # Related entities
    load_id = Column(String(36), ForeignKey("loads.id"), nullable=True)
    document_id = Column(String(36), ForeignKey("documents.id"), nullable=True)
    
    # Auto-generated task info
    is_system_generated = Column(Boolean, default=False)
    source = Column(String(100), nullable=True)  # onboarding_coach, compliance_engine, etc.
    
    # Completion
    completion_notes = Column(Text, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    
    # Relationships
    user = relationship("User", foreign_keys=[user_id], back_populates="tasks")

