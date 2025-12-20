"""Calendar and Task schemas."""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime

from ..models.calendar import TaskStatus


class CalendarEventCreate(BaseModel):
    """Create calendar event request."""
    title: str
    description: Optional[str] = None
    event_type: str = "general"  # pickup, delivery, meeting, training
    start_time: datetime
    end_time: datetime
    all_day: bool = False
    timezone: str = "UTC"
    location: Optional[str] = None
    location_lat: Optional[str] = None
    location_lng: Optional[str] = None
    load_id: Optional[str] = None
    reminders: Optional[List[int]] = None  # Minutes before event
    is_recurring: bool = False
    recurrence_rule: Optional[str] = None


class CalendarEventUpdate(BaseModel):
    """Update calendar event request."""
    title: Optional[str] = None
    description: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    all_day: Optional[bool] = None
    location: Optional[str] = None
    status: Optional[str] = None
    reminders: Optional[List[int]] = None


class CalendarEventResponse(BaseModel):
    """Calendar event response."""
    id: str
    user_id: str
    title: str
    description: Optional[str]
    event_type: str
    start_time: datetime
    end_time: datetime
    all_day: bool
    timezone: str
    location: Optional[str]
    load_id: Optional[str]
    is_recurring: bool
    recurrence_rule: Optional[str]
    reminders: Optional[List[int]]
    status: str
    external_id: Optional[str]
    external_source: Optional[str]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class CalendarEventListResponse(BaseModel):
    """Calendar events list response."""
    items: List[CalendarEventResponse]
    total: int


class TaskCreate(BaseModel):
    """Create task request."""
    title: str
    description: Optional[str] = None
    task_type: str = "general"
    priority: str = "medium"  # low, medium, high, urgent
    due_date: Optional[datetime] = None
    load_id: Optional[str] = None
    document_id: Optional[str] = None
    assigned_to: Optional[str] = None  # User ID


class TaskUpdate(BaseModel):
    """Update task request."""
    title: Optional[str] = None
    description: Optional[str] = None
    priority: Optional[str] = None
    status: Optional[TaskStatus] = None
    due_date: Optional[datetime] = None
    completion_notes: Optional[str] = None


class TaskResponse(BaseModel):
    """Task response."""
    id: str
    user_id: str
    assigned_by: Optional[str]
    title: str
    description: Optional[str]
    task_type: str
    priority: str
    status: TaskStatus
    due_date: Optional[datetime]
    completed_at: Optional[datetime]
    load_id: Optional[str]
    document_id: Optional[str]
    is_system_generated: bool
    source: Optional[str]
    completion_notes: Optional[str]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class TaskListResponse(BaseModel):
    """Paginated task list response."""
    items: List[TaskResponse]
    total: int
    page: int
    page_size: int
    by_status: Dict[str, int]


class ExternalCalendarConnect(BaseModel):
    """Connect external calendar request."""
    provider: str  # google, outlook
    auth_code: str
    redirect_uri: str


class ExternalCalendarSync(BaseModel):
    """Sync external calendar request."""
    provider: str
    sync_direction: str = "both"  # import, export, both
    calendar_id: Optional[str] = None

