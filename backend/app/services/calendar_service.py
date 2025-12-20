"""Calendar and Task service."""
from datetime import datetime, timedelta
from typing import Optional, List, Tuple, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
import json

from ..models.calendar import CalendarEvent, Task, TaskStatus
from ..schemas.calendar import CalendarEventCreate, CalendarEventUpdate, TaskCreate, TaskUpdate


class CalendarService:
    """Service for calendar and task management."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    # Calendar Events
    async def create_event(self, data: CalendarEventCreate, user_id: str) -> CalendarEvent:
        """Create a calendar event."""
        event = CalendarEvent(
            user_id=user_id,
            title=data.title,
            description=data.description,
            event_type=data.event_type,
            start_time=data.start_time,
            end_time=data.end_time,
            all_day=data.all_day,
            timezone=data.timezone,
            location=data.location,
            location_lat=data.location_lat,
            location_lng=data.location_lng,
            load_id=data.load_id,
            reminders=json.dumps(data.reminders) if data.reminders else None,
            is_recurring=data.is_recurring,
            recurrence_rule=data.recurrence_rule,
        )
        
        self.db.add(event)
        await self.db.commit()
        await self.db.refresh(event)
        return event
    
    async def get_event(self, event_id: str) -> Optional[CalendarEvent]:
        """Get calendar event by ID."""
        result = await self.db.execute(select(CalendarEvent).where(CalendarEvent.id == event_id))
        return result.scalar_one_or_none()
    
    async def update_event(self, event_id: str, data: CalendarEventUpdate, user_id: str) -> CalendarEvent:
        """Update a calendar event."""
        event = await self.get_event(event_id)
        if not event:
            raise ValueError("Event not found")
        if event.user_id != user_id:
            raise ValueError("Not authorized to update this event")
        
        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            if field == "reminders" and value:
                value = json.dumps(value)
            if hasattr(event, field):
                setattr(event, field, value)
        
        event.updated_at = datetime.utcnow()
        await self.db.commit()
        await self.db.refresh(event)
        return event
    
    async def delete_event(self, event_id: str, user_id: str) -> bool:
        """Delete a calendar event."""
        event = await self.get_event(event_id)
        if not event:
            raise ValueError("Event not found")
        if event.user_id != user_id:
            raise ValueError("Not authorized to delete this event")
        
        await self.db.delete(event)
        await self.db.commit()
        return True
    
    async def get_user_events(
        self,
        user_id: str,
        start_date: datetime,
        end_date: datetime,
    ) -> List[CalendarEvent]:
        """Get user's events within date range."""
        query = select(CalendarEvent).where(
            CalendarEvent.user_id == user_id,
            CalendarEvent.status != "cancelled",
            CalendarEvent.start_time >= start_date,
            CalendarEvent.end_time <= end_date,
        ).order_by(CalendarEvent.start_time)
        
        result = await self.db.execute(query)
        return list(result.scalars().all())
    
    # Tasks
    async def create_task(self, data: TaskCreate, user_id: str, assigned_by: str = None) -> Task:
        """Create a task."""
        task = Task(
            user_id=data.assigned_to or user_id,
            assigned_by=assigned_by or user_id,
            title=data.title,
            description=data.description,
            task_type=data.task_type,
            priority=data.priority,
            due_date=data.due_date,
            load_id=data.load_id,
            document_id=data.document_id,
            status=TaskStatus.TODO,
        )
        
        self.db.add(task)
        await self.db.commit()
        await self.db.refresh(task)
        return task
    
    async def get_task(self, task_id: str) -> Optional[Task]:
        """Get task by ID."""
        result = await self.db.execute(select(Task).where(Task.id == task_id))
        return result.scalar_one_or_none()
    
    async def update_task(self, task_id: str, data: TaskUpdate, user_id: str) -> Task:
        """Update a task."""
        task = await self.get_task(task_id)
        if not task:
            raise ValueError("Task not found")
        
        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            if hasattr(task, field):
                setattr(task, field, value)
        
        if data.status == TaskStatus.COMPLETED:
            task.completed_at = datetime.utcnow()
        
        task.updated_at = datetime.utcnow()
        await self.db.commit()
        await self.db.refresh(task)
        return task
    
    async def get_user_tasks(
        self,
        user_id: str,
        status: TaskStatus = None,
        task_type: str = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Tuple[List[Task], int, Dict[str, int]]:
        """Get user's tasks with counts by status."""
        query = select(Task).where(Task.user_id == user_id)
        
        if status:
            query = query.where(Task.status == status)
        if task_type:
            query = query.where(Task.task_type == task_type)
        
        # Count total
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await self.db.execute(count_query)
        total = total_result.scalar()
        
        # Get status counts
        status_counts = {}
        for s in TaskStatus:
            count_result = await self.db.execute(
                select(func.count()).where(Task.user_id == user_id, Task.status == s)
            )
            status_counts[s.value] = count_result.scalar()
        
        # Paginate
        query = query.order_by(Task.due_date.asc().nullslast(), Task.priority.desc())
        query = query.offset((page - 1) * page_size).limit(page_size)
        
        result = await self.db.execute(query)
        tasks = list(result.scalars().all())
        
        return tasks, total, status_counts
    
    async def create_system_task(
        self,
        user_id: str,
        title: str,
        description: str,
        task_type: str,
        source: str,
        due_date: datetime = None,
        document_id: str = None,
    ) -> Task:
        """Create a system-generated task."""
        task = Task(
            user_id=user_id,
            title=title,
            description=description,
            task_type=task_type,
            priority="high",
            due_date=due_date,
            document_id=document_id,
            is_system_generated=True,
            source=source,
            status=TaskStatus.TODO,
        )
        
        self.db.add(task)
        await self.db.commit()
        await self.db.refresh(task)
        return task

