"""Training and News API routes."""
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.database import get_db
from ..core.security import get_current_user, get_current_active_user, require_roles
from ..models.user import User, UserRole
from ..schemas.training import (
    TrainingModuleCreate, TrainingModuleResponse, TrainingModuleListResponse,
    TrainingProgressUpdate, TrainingProgressResponse,
    NewsPostCreate, NewsPostResponse, NewsPostListResponse
)
from ..services.training_service import TrainingService


router = APIRouter(prefix="/training", tags=["Training"])


# Training Modules
@router.get("/modules", response_model=TrainingModuleListResponse)
async def list_modules(
    module_type: Optional[str] = None,
    is_required: Optional[bool] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """List training modules."""
    training_service = TrainingService(db)
    
    modules, total = await training_service.list_modules(
        role=current_user.role.value,
        module_type=module_type,
        is_required=is_required,
        page=page,
        page_size=page_size,
    )
    
    return TrainingModuleListResponse(
        modules=modules,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/modules/{module_id}", response_model=TrainingModuleResponse)
async def get_module(
    module_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Get training module by ID."""
    training_service = TrainingService(db)
    
    module = await training_service.get_module(module_id)
    if not module:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Module not found")
    
    return module


@router.post("/modules/{module_id}/progress", response_model=TrainingProgressResponse)
async def update_progress(
    module_id: str,
    data: TrainingProgressUpdate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Update progress on a training module."""
    training_service = TrainingService(db)
    
    progress = await training_service.update_progress(
        user_id=current_user.id,
        module_id=module_id,
        progress_percent=data.progress_percent,
        completed=data.completed,
        quiz_score=data.quiz_score,
    )
    
    return progress


@router.get("/status")
async def get_training_status(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Get user's overall training status."""
    training_service = TrainingService(db)
    
    status = await training_service.get_user_training_status(
        user_id=current_user.id,
        role=current_user.role.value,
    )
    
    return status


# Admin endpoints for modules
@router.post("/modules", response_model=TrainingModuleResponse, status_code=status.HTTP_201_CREATED)
async def create_module(
    data: TrainingModuleCreate,
    current_user: User = Depends(require_roles([UserRole.ADMIN, UserRole.SUPER_ADMIN])),
    db: AsyncSession = Depends(get_db)
):
    """Create a training module (admin only)."""
    training_service = TrainingService(db)
    
    module = await training_service.create_module(
        title=data.title,
        description=data.description,
        content=data.content,
        module_type=data.module_type,
        duration_minutes=data.duration_minutes,
        applies_to_roles=data.applies_to_roles,
        is_required=data.is_required,
        order=data.order,
    )
    
    return module


# News Posts
@router.get("/news", response_model=NewsPostListResponse)
async def list_news(
    category: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=50),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """List news posts."""
    training_service = TrainingService(db)
    
    posts, total = await training_service.list_news(
        role=current_user.role.value,
        category=category,
        page=page,
        page_size=page_size,
    )
    
    return NewsPostListResponse(
        posts=posts,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("/news", response_model=NewsPostResponse, status_code=status.HTTP_201_CREATED)
async def create_news_post(
    data: NewsPostCreate,
    current_user: User = Depends(require_roles([UserRole.ADMIN, UserRole.SUPER_ADMIN])),
    db: AsyncSession = Depends(get_db)
):
    """Create a news post (admin only)."""
    training_service = TrainingService(db)
    
    post = await training_service.create_news_post(
        title=data.title,
        content=data.content,
        author_id=current_user.id,
        category=data.category,
        is_pinned=data.is_pinned,
        target_roles=data.target_roles,
    )
    
    return post

