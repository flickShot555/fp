"""Carrier management API routes."""
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.database import get_db
from ..core.security import get_current_user, get_current_active_user, require_roles
from ..models.user import User, UserRole
from ..schemas.carrier import (
    CarrierCreate, CarrierUpdate, CarrierResponse, CarrierListResponse,
    CarrierSearchRequest, LaneCreate, LaneResponse, FMCSAVerificationResponse
)
from ..services.carrier_service import CarrierService
from ..services.fmcsa_service import FMCSAService
from ..services.compliance_service import ComplianceService


router = APIRouter(prefix="/carriers", tags=["Carriers"])


@router.post("", response_model=CarrierResponse, status_code=status.HTTP_201_CREATED)
async def create_carrier(
    data: CarrierCreate,
    current_user: User = Depends(require_roles([UserRole.CARRIER, UserRole.ADMIN, UserRole.SUPER_ADMIN])),
    db: AsyncSession = Depends(get_db)
):
    """Create a carrier profile."""
    carrier_service = CarrierService(db)
    
    try:
        carrier = await carrier_service.create_carrier(data)
        return carrier
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("", response_model=CarrierListResponse)
async def list_carriers(
    is_active: bool = True,
    is_verified: Optional[bool] = None,
    min_compliance_score: Optional[float] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """List carriers."""
    carrier_service = CarrierService(db)
    
    carriers, total = await carrier_service.list_carriers(
        is_active=is_active,
        is_verified=is_verified,
        min_compliance_score=min_compliance_score,
        page=page,
        page_size=page_size,
    )
    
    return CarrierListResponse(
        carriers=carriers,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("/search", response_model=CarrierListResponse)
async def search_carriers(
    search: CarrierSearchRequest,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Search carriers for load matching."""
    carrier_service = CarrierService(db)
    
    carriers, total = await carrier_service.search_carriers(search, page=page, page_size=page_size)
    
    return CarrierListResponse(
        carriers=carriers,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{carrier_id}", response_model=CarrierResponse)
async def get_carrier(
    carrier_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Get carrier by ID."""
    carrier_service = CarrierService(db)
    
    carrier = await carrier_service.get_carrier(carrier_id)
    if not carrier:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Carrier not found")
    
    return carrier


@router.put("/{carrier_id}", response_model=CarrierResponse)
async def update_carrier(
    carrier_id: str,
    data: CarrierUpdate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Update carrier profile."""
    carrier_service = CarrierService(db)
    
    try:
        carrier = await carrier_service.update_carrier(carrier_id, data)
        return carrier
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/{carrier_id}/verify-fmcsa", response_model=FMCSAVerificationResponse)
async def verify_fmcsa(
    carrier_id: str,
    usdot: Optional[str] = None,
    mc_number: Optional[str] = None,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Verify carrier against FMCSA database."""
    fmcsa_service = FMCSAService(db)
    
    try:
        result = await fmcsa_service.verify_carrier(carrier_id, usdot=usdot, mc_number=mc_number)
        
        if "error" in result:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=result["error"])
        
        return result
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/{carrier_id}/compliance")
async def get_carrier_compliance(
    carrier_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Get carrier compliance status."""
    compliance_service = ComplianceService(db)
    
    try:
        result = await compliance_service.check_carrier_compliance(carrier_id)
        return result
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/{carrier_id}/lanes", response_model=LaneResponse, status_code=status.HTTP_201_CREATED)
async def add_lane(
    carrier_id: str,
    data: LaneCreate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Add a preferred lane for carrier."""
    carrier_service = CarrierService(db)
    
    try:
        lane = await carrier_service.add_lane(carrier_id, data)
        return lane
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/{carrier_id}/lanes", response_model=List[LaneResponse])
async def get_carrier_lanes(
    carrier_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Get carrier's preferred lanes."""
    carrier_service = CarrierService(db)
    
    lanes = await carrier_service.get_carrier_lanes(carrier_id)
    return lanes

