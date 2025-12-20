"""Training and news service."""
from datetime import datetime
from typing import Optional, List, Tuple, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
import json

from ..models.training import TrainingModule, TrainingProgress, NewsPost
from ..models.user import UserRole


class TrainingService:
    """Service for training modules and news."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    # Training Modules
    async def create_module(
        self,
        title: str,
        description: str,
        content: str,
        module_type: str,
        duration_minutes: int = None,
        applies_to_roles: List[str] = None,
        is_required: bool = False,
        order: int = 0,
    ) -> TrainingModule:
        """Create a training module."""
        module = TrainingModule(
            title=title,
            description=description,
            content=content,
            module_type=module_type,
            duration_minutes=duration_minutes,
            applies_to_roles=json.dumps(applies_to_roles) if applies_to_roles else None,
            is_required=is_required,
            order=order,
        )
        
        self.db.add(module)
        await self.db.commit()
        await self.db.refresh(module)
        return module
    
    async def get_module(self, module_id: str) -> Optional[TrainingModule]:
        """Get training module by ID."""
        result = await self.db.execute(select(TrainingModule).where(TrainingModule.id == module_id))
        return result.scalar_one_or_none()
    
    async def list_modules(
        self,
        role: str = None,
        module_type: str = None,
        is_required: bool = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Tuple[List[TrainingModule], int]:
        """List training modules."""
        query = select(TrainingModule).where(TrainingModule.is_active == True)
        
        if module_type:
            query = query.where(TrainingModule.module_type == module_type)
        if is_required is not None:
            query = query.where(TrainingModule.is_required == is_required)
        
        # Count
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await self.db.execute(count_query)
        total = total_result.scalar()
        
        # Paginate
        query = query.order_by(TrainingModule.order, TrainingModule.created_at)
        query = query.offset((page - 1) * page_size).limit(page_size)
        
        result = await self.db.execute(query)
        modules = list(result.scalars().all())
        
        # Filter by role
        if role:
            filtered = []
            for m in modules:
                if m.applies_to_roles:
                    roles = json.loads(m.applies_to_roles)
                    if role in roles or len(roles) == 0:
                        filtered.append(m)
                else:
                    filtered.append(m)
            modules = filtered
        
        return modules, total
    
    async def get_user_progress(self, user_id: str, module_id: str) -> Optional[TrainingProgress]:
        """Get user's progress on a module."""
        result = await self.db.execute(
            select(TrainingProgress).where(
                TrainingProgress.user_id == user_id,
                TrainingProgress.module_id == module_id
            )
        )
        return result.scalar_one_or_none()
    
    async def update_progress(
        self,
        user_id: str,
        module_id: str,
        progress_percent: float,
        completed: bool = False,
        quiz_score: float = None,
    ) -> TrainingProgress:
        """Update user's progress on a module."""
        progress = await self.get_user_progress(user_id, module_id)
        
        if not progress:
            progress = TrainingProgress(
                user_id=user_id,
                module_id=module_id,
                progress_percent=progress_percent,
                is_completed=completed,
                quiz_score=quiz_score,
            )
            self.db.add(progress)
        else:
            progress.progress_percent = max(progress.progress_percent, progress_percent)
            if completed:
                progress.is_completed = True
                progress.completed_at = datetime.utcnow()
            if quiz_score is not None:
                progress.quiz_score = quiz_score
        
        await self.db.commit()
        await self.db.refresh(progress)
        return progress
    
    async def get_user_training_status(self, user_id: str, role: str) -> Dict[str, Any]:
        """Get user's overall training status."""
        modules, _ = await self.list_modules(role=role)
        required_modules = [m for m in modules if m.is_required]
        
        # Get progress for all modules
        progress_result = await self.db.execute(
            select(TrainingProgress).where(TrainingProgress.user_id == user_id)
        )
        progress_list = list(progress_result.scalars().all())
        progress_map = {p.module_id: p for p in progress_list}
        
        completed_required = sum(
            1 for m in required_modules
            if m.id in progress_map and progress_map[m.id].is_completed
        )
        
        return {
            "total_modules": len(modules),
            "required_modules": len(required_modules),
            "completed_required": completed_required,
            "all_required_complete": completed_required == len(required_modules),
            "modules": [
                {
                    "id": m.id,
                    "title": m.title,
                    "is_required": m.is_required,
                    "progress": progress_map.get(m.id, {}).progress_percent if m.id in progress_map else 0,
                    "completed": progress_map.get(m.id, {}).is_completed if m.id in progress_map else False,
                }
                for m in modules
            ],
        }
    
    # News Posts
    async def create_news_post(
        self,
        title: str,
        content: str,
        author_id: str,
        category: str = "general",
        is_pinned: bool = False,
        target_roles: List[str] = None,
    ) -> NewsPost:
        """Create a news post."""
        post = NewsPost(
            title=title,
            content=content,
            author_id=author_id,
            category=category,
            is_pinned=is_pinned,
            target_roles=json.dumps(target_roles) if target_roles else None,
            published_at=datetime.utcnow(),
        )
        
        self.db.add(post)
        await self.db.commit()
        await self.db.refresh(post)
        return post
    
    async def list_news(
        self,
        role: str = None,
        category: str = None,
        page: int = 1,
        page_size: int = 10,
    ) -> Tuple[List[NewsPost], int]:
        """List news posts."""
        query = select(NewsPost).where(NewsPost.is_published == True)
        
        if category:
            query = query.where(NewsPost.category == category)
        
        # Count
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await self.db.execute(count_query)
        total = total_result.scalar()
        
        # Order by pinned first, then by date
        query = query.order_by(NewsPost.is_pinned.desc(), NewsPost.published_at.desc())
        query = query.offset((page - 1) * page_size).limit(page_size)
        
        result = await self.db.execute(query)
        posts = list(result.scalars().all())
        
        return posts, total

