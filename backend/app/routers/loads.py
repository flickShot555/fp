"""Marketplace/Loads API routes."""
from typing import Optional, List
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.database import get_db
from ..core.security import get_current_user, get_current_active_user, require_roles
from ..models.user import User, UserRole
from ..models.load import LoadStatus
from ..schemas.load import (
    LoadCreate, LoadUpdate, LoadResponse, LoadListResponse,
    LoadSearchRequest, LoadApplicationCreate, LoadApplicationResponse,
    LoadAssignmentCreate
)
from ..services.load_service import LoadService


router = APIRouter(prefix="/loads", tags=["Marketplace"])


@router.post("", response_model=LoadResponse, status_code=status.HTTP_201_CREATED)
async def create_load(
    data: LoadCreate,
    current_user: User = Depends(require_roles([UserRole.SHIPPER, UserRole.ADMIN, UserRole.SUPER_ADMIN])),
    db: AsyncSession = Depends(get_db)
):
    """Create a new load."""
    load_service = LoadService(db)
    
    try:
        load = await load_service.create_load(data, shipper_id=current_user.id)
        return load
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("", response_model=LoadListResponse)
async def list_loads(
    status: Optional[str] = None,
    origin_state: Optional[str] = None,
    destination_state: Optional[str] = None,
    equipment_type: Optional[str] = None,
    min_rate: Optional[float] = None,
    max_rate: Optional[float] = None,
    pickup_date_from: Optional[datetime] = None,
    pickup_date_to: Optional[datetime] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """List loads (marketplace)."""
    load_service = LoadService(db)
    
    load_status = None
    if status:
        try:
            load_status = LoadStatus(status)
        except ValueError:
            pass
    
    loads, total = await load_service.list_loads(
        status=load_status,
        origin_state=origin_state,
        destination_state=destination_state,
        equipment_type=equipment_type,
        min_rate=min_rate,
        max_rate=max_rate,
        pickup_date_from=pickup_date_from,
        pickup_date_to=pickup_date_to,
        page=page,
        page_size=page_size,
    )
    
    return LoadListResponse(
        loads=loads,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("/search", response_model=LoadListResponse)
async def search_loads(
    search: LoadSearchRequest,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Search loads with advanced filters."""
    load_service = LoadService(db)
    
    loads, total = await load_service.search_loads(search, page=page, page_size=page_size)
    
    return LoadListResponse(
        loads=loads,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/my-loads", response_model=LoadListResponse)
async def get_my_loads(
    status: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Get loads created by or assigned to current user."""
    load_service = LoadService(db)
    
    if current_user.role == UserRole.SHIPPER:
        loads, total = await load_service.get_shipper_loads(current_user.id, page=page, page_size=page_size)
    elif current_user.role in [UserRole.CARRIER, UserRole.DRIVER]:
        loads, total = await load_service.get_carrier_loads(current_user.id, page=page, page_size=page_size)
    else:
        loads, total = await load_service.list_loads(page=page, page_size=page_size)
    
    return LoadListResponse(loads=loads, total=total, page=page, page_size=page_size)


@router.get("/{load_id}", response_model=LoadResponse)
async def get_load(
    load_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Get load by ID."""
    load_service = LoadService(db)
    
    load = await load_service.get_load(load_id)
    if not load:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Load not found")
    
    return load


@router.put("/{load_id}", response_model=LoadResponse)
async def update_load(
    load_id: str,
    data: LoadUpdate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Update a load."""
    load_service = LoadService(db)
    
    load = await load_service.get_load(load_id)
    if not load:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Load not found")
    
    # Check ownership
    if load.shipper_id != current_user.id and current_user.role not in [UserRole.ADMIN, UserRole.SUPER_ADMIN]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    
    try:
        updated = await load_service.update_load(load_id, data)
        return updated
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

