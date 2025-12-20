"""Load applications and assignments API routes."""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.database import get_db
from ..core.security import get_current_active_user, require_roles
from ..models.user import User, UserRole
from ..schemas.load import (
    LoadApplicationCreate, LoadApplicationResponse, LoadApplicationListResponse,
    LoadAssignmentCreate, LoadAssignmentResponse
)
from ..services.load_service import LoadService


router = APIRouter(prefix="/loads", tags=["Load Applications"])


@router.post("/{load_id}/apply", response_model=LoadApplicationResponse, status_code=status.HTTP_201_CREATED)
async def apply_for_load(
    load_id: str,
    data: LoadApplicationCreate,
    current_user: User = Depends(require_roles([UserRole.CARRIER])),
    db: AsyncSession = Depends(get_db)
):
    """Apply for a load (carrier only)."""
    load_service = LoadService(db)
    
    try:
        application = await load_service.apply_for_load(
            load_id=load_id,
            carrier_id=current_user.id,
            proposed_rate=data.proposed_rate,
            notes=data.notes,
        )
        return application
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/{load_id}/applications", response_model=LoadApplicationListResponse)
async def get_load_applications(
    load_id: str,
    status: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Get applications for a load."""
    load_service = LoadService(db)
    
    # Check if user owns the load or is admin
    load = await load_service.get_load(load_id)
    if not load:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Load not found")
    
    if load.shipper_id != current_user.id and current_user.role not in [UserRole.ADMIN, UserRole.SUPER_ADMIN]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    
    applications, total = await load_service.get_load_applications(
        load_id=load_id,
        status=status,
        page=page,
        page_size=page_size,
    )
    
    return LoadApplicationListResponse(
        applications=applications,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("/{load_id}/applications/{application_id}/accept", response_model=LoadAssignmentResponse)
async def accept_application(
    load_id: str,
    application_id: str,
    current_user: User = Depends(require_roles([UserRole.SHIPPER, UserRole.ADMIN, UserRole.SUPER_ADMIN])),
    db: AsyncSession = Depends(get_db)
):
    """Accept a load application and create assignment."""
    load_service = LoadService(db)
    
    load = await load_service.get_load(load_id)
    if not load:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Load not found")
    
    if load.shipper_id != current_user.id and current_user.role not in [UserRole.ADMIN, UserRole.SUPER_ADMIN]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    
    try:
        assignment = await load_service.accept_application(application_id)
        return assignment
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/{load_id}/applications/{application_id}/reject")
async def reject_application(
    load_id: str,
    application_id: str,
    reason: Optional[str] = None,
    current_user: User = Depends(require_roles([UserRole.SHIPPER, UserRole.ADMIN, UserRole.SUPER_ADMIN])),
    db: AsyncSession = Depends(get_db)
):
    """Reject a load application."""
    load_service = LoadService(db)
    
    load = await load_service.get_load(load_id)
    if not load:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Load not found")
    
    if load.shipper_id != current_user.id and current_user.role not in [UserRole.ADMIN, UserRole.SUPER_ADMIN]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    
    try:
        await load_service.reject_application(application_id, reason=reason)
        return {"message": "Application rejected"}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/{load_id}/status")
async def update_load_status(
    load_id: str,
    new_status: str,
    notes: Optional[str] = None,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Update load status."""
    load_service = LoadService(db)
    
    load = await load_service.get_load(load_id)
    if not load:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Load not found")
    
    try:
        updated = await load_service.update_load_status(
            load_id=load_id,
            new_status=new_status,
            user_id=current_user.id,
            notes=notes,
        )
        return {"message": f"Load status updated to {new_status}", "load": updated}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/my-applications", response_model=LoadApplicationListResponse)
async def get_my_applications(
    status: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(require_roles([UserRole.CARRIER])),
    db: AsyncSession = Depends(get_db)
):
    """Get current carrier's applications."""
    load_service = LoadService(db)
    
    applications, total = await load_service.get_carrier_applications(
        carrier_id=current_user.id,
        status=status,
        page=page,
        page_size=page_size,
    )
    
    return LoadApplicationListResponse(
        applications=applications,
        total=total,
        page=page,
        page_size=page_size,
    )

