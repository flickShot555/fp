"""Training and News schemas."""
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel


class TrainingModuleCreate(BaseModel):
    """Schema for creating a training module."""
    title: str
    description: str
    content: str
    module_type: str = "video"  # video, article, quiz
    duration_minutes: Optional[int] = None
    applies_to_roles: Optional[List[str]] = None
    is_required: bool = False
    order: int = 0


class TrainingModuleResponse(BaseModel):
    """Schema for training module response."""
    id: str
    title: str
    description: str
    content: str
    module_type: str
    duration_minutes: Optional[int] = None
    applies_to_roles: Optional[str] = None
    is_required: bool
    order: int
    is_active: bool
    created_at: datetime
    
    class Config:
        from_attributes = True


class TrainingModuleListResponse(BaseModel):
    """Schema for training module list response."""
    modules: List[TrainingModuleResponse]
    total: int
    page: int
    page_size: int


class TrainingProgressUpdate(BaseModel):
    """Schema for updating training progress."""
    progress_percent: float
    completed: bool = False
    quiz_score: Optional[float] = None


class TrainingProgressResponse(BaseModel):
    """Schema for training progress response."""
    id: str
    user_id: str
    module_id: str
    progress_percent: float
    is_completed: bool
    completed_at: Optional[datetime] = None
    quiz_score: Optional[float] = None
    
    class Config:
        from_attributes = True


class NewsPostCreate(BaseModel):
    """Schema for creating a news post."""
    title: str
    content: str
    category: str = "general"
    is_pinned: bool = False
    target_roles: Optional[List[str]] = None


class NewsPostResponse(BaseModel):
    """Schema for news post response."""
    id: str
    title: str
    content: str
    author_id: str
    category: str
    is_pinned: bool
    is_published: bool
    published_at: Optional[datetime] = None
    created_at: datetime
    
    class Config:
        from_attributes = True


class NewsPostListResponse(BaseModel):
    """Schema for news post list response."""
    posts: List[NewsPostResponse]
    total: int
    page: int
    page_size: int

