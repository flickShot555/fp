"""Driver management API routes."""
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.database import get_db
from ..core.security import get_current_user, get_current_active_user, require_roles
from ..models.user import User, UserRole
from ..models.driver import DriverStatus
from ..schemas.driver import (
    DriverCreate, DriverUpdate, DriverResponse, DriverListResponse,
    DriverSearchRequest, DriverComplianceStatus, DriverLocationUpdate
)
from ..services.driver_service import DriverService


router = APIRouter(prefix="/drivers", tags=["Drivers"])


@router.post("", response_model=DriverResponse, status_code=status.HTTP_201_CREATED)
async def create_driver(
    data: DriverCreate,
    current_user: User = Depends(require_roles([UserRole.DRIVER, UserRole.CARRIER, UserRole.ADMIN])),
    db: AsyncSession = Depends(get_db)
):
    """Create a driver profile."""
    driver_service = DriverService(db)
    
    try:
        driver = await driver_service.create_driver(current_user.id, data)
        return driver
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/me", response_model=DriverResponse)
async def get_my_driver_profile(
    current_user: User = Depends(require_roles([UserRole.DRIVER])),
    db: AsyncSession = Depends(get_db)
):
    """Get current user's driver profile."""
    driver_service = DriverService(db)
    
    driver = await driver_service.get_driver_by_user(current_user.id)
    if not driver:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Driver profile not found")
    
    return driver


@router.put("/me", response_model=DriverResponse)
async def update_my_driver_profile(
    data: DriverUpdate,
    current_user: User = Depends(require_roles([UserRole.DRIVER])),
    db: AsyncSession = Depends(get_db)
):
    """Update current user's driver profile."""
    driver_service = DriverService(db)
    
    driver = await driver_service.get_driver_by_user(current_user.id)
    if not driver:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Driver profile not found")
    
    try:
        updated = await driver_service.update_driver(driver.id, data)
        return updated
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/me/location")
async def update_my_location(
    data: DriverLocationUpdate,
    current_user: User = Depends(require_roles([UserRole.DRIVER])),
    db: AsyncSession = Depends(get_db)
):
    """Update driver's current location."""
    driver_service = DriverService(db)
    
    driver = await driver_service.get_driver_by_user(current_user.id)
    if not driver:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Driver profile not found")
    
    await driver_service.update_location(
        driver.id,
        lat=data.lat,
        lng=data.lng,
        city=data.city,
        state=data.state,
    )
    
    return {"message": "Location updated"}


@router.get("/me/compliance", response_model=DriverComplianceStatus)
async def get_my_compliance(
    current_user: User = Depends(require_roles([UserRole.DRIVER])),
    db: AsyncSession = Depends(get_db)
):
    """Get current driver's compliance status."""
    driver_service = DriverService(db)
    
    driver = await driver_service.get_driver_by_user(current_user.id)
    if not driver:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Driver profile not found")
    
    result = await driver_service.check_compliance(driver.id)
    return result


@router.get("", response_model=DriverListResponse)
async def list_drivers(
    carrier_id: Optional[str] = None,
    status: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(require_roles([UserRole.CARRIER, UserRole.ADMIN, UserRole.SUPER_ADMIN])),
    db: AsyncSession = Depends(get_db)
):
    """List drivers (carrier/admin only)."""
    driver_service = DriverService(db)
    
    driver_status = None
    if status:
        try:
            driver_status = DriverStatus(status)
        except ValueError:
            pass
    
    drivers, total = await driver_service.list_drivers(
        carrier_id=carrier_id,
        status=driver_status,
        page=page,
        page_size=page_size,
    )
    
    return DriverListResponse(
        drivers=drivers,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{driver_id}", response_model=DriverResponse)
async def get_driver(
    driver_id: str,
    current_user: User = Depends(require_roles([UserRole.CARRIER, UserRole.ADMIN, UserRole.SUPER_ADMIN])),
    db: AsyncSession = Depends(get_db)
):
    """Get driver by ID."""
    driver_service = DriverService(db)
    
    driver = await driver_service.get_driver(driver_id)
    if not driver:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Driver not found")
    
    return driver


@router.get("/{driver_id}/compliance", response_model=DriverComplianceStatus)
async def get_driver_compliance(
    driver_id: str,
    current_user: User = Depends(require_roles([UserRole.CARRIER, UserRole.ADMIN, UserRole.SUPER_ADMIN])),
    db: AsyncSession = Depends(get_db)
):
    """Get driver's compliance status."""
    driver_service = DriverService(db)
    
    result = await driver_service.check_compliance(driver_id)
    return result

