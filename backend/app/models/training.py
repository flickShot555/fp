"""Training and News related database models."""
from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, Text, Integer, Float
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid

from ..core.database import Base


class TrainingModule(Base):
    """Training module/course model."""
    __tablename__ = "training_modules"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    
    # Module details
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    category = Column(String(100), nullable=True)  # safety, compliance, onboarding, etc.
    
    # Content
    content_type = Column(String(50), default="video")  # video, article, quiz, interactive
    content_url = Column(String(500), nullable=True)
    content_duration = Column(Integer, nullable=True)  # Duration in minutes
    
    # Requirements
    is_required = Column(Boolean, default=False)
    required_for_roles = Column(Text, nullable=True)  # JSON array of roles
    prerequisites = Column(Text, nullable=True)  # JSON array of module IDs
    
    # Quiz/Assessment
    has_quiz = Column(Boolean, default=False)
    passing_score = Column(Integer, default=80)
    quiz_questions = Column(Text, nullable=True)  # JSON array of questions
    
    # Ordering
    sequence_order = Column(Integer, default=0)
    
    # Status
    is_active = Column(Boolean, default=True)
    
    # Timestamps
    published_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class TrainingProgress(Base):
    """User progress on training modules."""
    __tablename__ = "training_progress"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    
    # Foreign Keys
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    module_id = Column(String(36), ForeignKey("training_modules.id"), nullable=False, index=True)
    
    # Progress
    status = Column(String(50), default="not_started")  # not_started, in_progress, completed
    progress_percent = Column(Float, default=0.0)
    
    # Quiz results
    quiz_score = Column(Integer, nullable=True)
    quiz_passed = Column(Boolean, nullable=True)
    quiz_attempts = Column(Integer, default=0)
    
    # Time tracking
    time_spent = Column(Integer, default=0)  # Time in seconds
    last_accessed_at = Column(DateTime, nullable=True)
    
    # Completion
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    
    # Certificate
    certificate_url = Column(String(500), nullable=True)
    certificate_issued_at = Column(DateTime, nullable=True)
    
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class NewsPost(Base):
    """News and announcements model."""
    __tablename__ = "news_posts"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    
    # Content
    title = Column(String(255), nullable=False)
    content = Column(Text, nullable=False)
    summary = Column(String(500), nullable=True)
    category = Column(String(100), nullable=True)  # industry, compliance, company, tips
    
    # Media
    image_url = Column(String(500), nullable=True)
    attachments = Column(Text, nullable=True)  # JSON array of URLs
    
    # Targeting
    target_roles = Column(Text, nullable=True)  # JSON array of roles
    is_featured = Column(Boolean, default=False)
    is_pinned = Column(Boolean, default=False)
    
    # Author
    author_id = Column(String(36), ForeignKey("users.id"), nullable=True)
    
    # Status
    status = Column(String(50), default="draft")  # draft, published, archived
    
    # Timestamps
    published_at = Column(DateTime, nullable=True)
    expires_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

