"""Carrier schemas."""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime


class CarrierCreate(BaseModel):
    """Create carrier profile request."""
    company_id: str
    equipment_types: Optional[List[str]] = None
    power_units: Optional[int] = 0
    trailers: Optional[int] = 0
    service_states: Optional[List[str]] = None


class CarrierUpdate(BaseModel):
    """Update carrier profile request."""
    equipment_types: Optional[List[str]] = None
    power_units: Optional[int] = None
    trailers: Optional[int] = None
    service_states: Optional[List[str]] = None
    available_for_loads: Optional[bool] = None


class CarrierResponse(BaseModel):
    """Carrier response schema."""
    id: str
    company_id: str
    fmcsa_verified: bool
    fmcsa_verification_date: Optional[datetime]
    compliance_score: float
    compliance_status: str
    equipment_types: Optional[List[str]]
    power_units: int
    trailers: int
    service_states: Optional[List[str]]
    insurance_status: Optional[str]
    insurance_expiry: Optional[datetime]
    on_time_delivery_rate: Optional[float]
    total_loads_completed: int
    average_rating: Optional[float]
    is_active: bool
    available_for_loads: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class CarrierDetailResponse(CarrierResponse):
    """Detailed carrier response with company info."""
    company_name: str
    usdot: Optional[str]
    mc_number: Optional[str]
    safety_rating: Optional[str]
    operating_status: Optional[str]


class CarrierListResponse(BaseModel):
    """Paginated carrier list response."""
    items: List[CarrierResponse]
    total: int
    page: int
    page_size: int
    pages: int


class LaneCreate(BaseModel):
    """Create lane request."""
    origin_city: Optional[str] = None
    origin_state: str
    destination_city: Optional[str] = None
    destination_state: str
    equipment_type: Optional[str] = None
    preferred_rate: Optional[float] = None


class LaneResponse(BaseModel):
    """Lane response schema."""
    id: str
    carrier_id: str
    origin_city: Optional[str]
    origin_state: str
    destination_city: Optional[str]
    destination_state: str
    equipment_type: Optional[str]
    preferred_rate: Optional[float]
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class CarrierComplianceCheck(BaseModel):
    """Carrier compliance check result."""
    carrier_id: str
    is_compliant: bool
    score: float
    checks: Dict[str, bool]
    issues: List[str]
    warnings: List[str]
    last_checked: datetime


class FMCSAVerificationRequest(BaseModel):
    """FMCSA verification request."""
    usdot: Optional[str] = None
    mc_number: Optional[str] = None


class FMCSAVerificationResponse(BaseModel):
    """FMCSA verification response."""
    carrier_id: str
    usdot: str
    mc_number: Optional[str]
    legal_name: str
    dba_name: Optional[str]
    operating_status: str
    authority_status: str
    safety_rating: Optional[str]
    insurance_status: str
    is_authorized: bool
    issues: List[str]
    raw_data: Dict[str, Any]


class CarrierInviteRequest(BaseModel):
    """Invite carrier to bid on load."""
    load_id: str
    carrier_ids: List[str]
    message: Optional[str] = None


class CarrierSearchRequest(BaseModel):
    """Search carriers request."""
    equipment_type: Optional[str] = None
    origin_state: Optional[str] = None
    destination_state: Optional[str] = None
    min_compliance_score: Optional[float] = None
    is_verified: Optional[bool] = None

