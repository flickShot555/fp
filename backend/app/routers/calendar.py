"""Calendar and Tasks API routes."""
from typing import Optional, List
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.database import get_db
from ..core.security import get_current_user, get_current_active_user
from ..models.user import User
from ..models.calendar import TaskStatus
from ..schemas.calendar import (
    CalendarEventCreate, CalendarEventUpdate, CalendarEventResponse,
    TaskCreate, TaskUpdate, TaskResponse, TaskListResponse
)
from ..services.calendar_service import CalendarService


router = APIRouter(prefix="/calendar", tags=["Calendar"])


# Calendar Events
@router.post("/events", response_model=CalendarEventResponse, status_code=status.HTTP_201_CREATED)
async def create_event(
    data: CalendarEventCreate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Create a calendar event."""
    calendar_service = CalendarService(db)
    
    try:
        event = await calendar_service.create_event(data, user_id=current_user.id)
        return event
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/events")
async def list_events(
    start_date: datetime,
    end_date: datetime,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """List calendar events within date range."""
    calendar_service = CalendarService(db)
    
    events = await calendar_service.get_user_events(
        user_id=current_user.id,
        start_date=start_date,
        end_date=end_date,
    )
    
    return {"events": events}


@router.get("/events/{event_id}", response_model=CalendarEventResponse)
async def get_event(
    event_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Get calendar event by ID."""
    calendar_service = CalendarService(db)
    
    event = await calendar_service.get_event(event_id)
    if not event:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")
    
    if event.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    
    return event


@router.put("/events/{event_id}", response_model=CalendarEventResponse)
async def update_event(
    event_id: str,
    data: CalendarEventUpdate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Update a calendar event."""
    calendar_service = CalendarService(db)
    
    try:
        event = await calendar_service.update_event(event_id, data, user_id=current_user.id)
        return event
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.delete("/events/{event_id}")
async def delete_event(
    event_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Delete a calendar event."""
    calendar_service = CalendarService(db)
    
    try:
        await calendar_service.delete_event(event_id, user_id=current_user.id)
        return {"message": "Event deleted"}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


# Tasks
@router.post("/tasks", response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
async def create_task(
    data: TaskCreate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Create a task."""
    calendar_service = CalendarService(db)
    
    try:
        task = await calendar_service.create_task(data, user_id=current_user.id, assigned_by=current_user.id)
        return task
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/tasks", response_model=TaskListResponse)
async def list_tasks(
    status: Optional[str] = None,
    task_type: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """List user's tasks."""
    calendar_service = CalendarService(db)
    
    task_status = None
    if status:
        try:
            task_status = TaskStatus(status)
        except ValueError:
            pass
    
    tasks, total, status_counts = await calendar_service.get_user_tasks(
        user_id=current_user.id,
        status=task_status,
        task_type=task_type,
        page=page,
        page_size=page_size,
    )
    
    return TaskListResponse(
        tasks=tasks,
        total=total,
        page=page,
        page_size=page_size,
        status_counts=status_counts,
    )


@router.put("/tasks/{task_id}", response_model=TaskResponse)
async def update_task(
    task_id: str,
    data: TaskUpdate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Update a task."""
    calendar_service = CalendarService(db)
    
    try:
        task = await calendar_service.update_task(task_id, data, user_id=current_user.id)
        return task
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

