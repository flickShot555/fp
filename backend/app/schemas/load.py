"""Load/Shipment schemas."""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime

from ..models.load import LoadStatus


class LoadCreate(BaseModel):
    """Create load request."""
    reference_number: Optional[str] = None
    origin_address: Optional[str] = None
    origin_city: str
    origin_state: str
    origin_zip: Optional[str] = None
    destination_address: Optional[str] = None
    destination_city: str
    destination_state: str
    destination_zip: Optional[str] = None
    stops: Optional[List[Dict[str, Any]]] = None
    pickup_date: datetime
    pickup_time_start: Optional[str] = None
    pickup_time_end: Optional[str] = None
    delivery_date: datetime
    delivery_time_start: Optional[str] = None
    delivery_time_end: Optional[str] = None
    equipment_type: str
    weight: Optional[float] = None
    pieces: Optional[int] = None
    commodity: Optional[str] = None
    special_instructions: Optional[str] = None
    temperature_min: Optional[float] = None
    temperature_max: Optional[float] = None
    rate: Optional[float] = None


class LoadUpdate(BaseModel):
    """Update load request."""
    reference_number: Optional[str] = None
    origin_city: Optional[str] = None
    origin_state: Optional[str] = None
    destination_city: Optional[str] = None
    destination_state: Optional[str] = None
    pickup_date: Optional[datetime] = None
    delivery_date: Optional[datetime] = None
    equipment_type: Optional[str] = None
    weight: Optional[float] = None
    rate: Optional[float] = None
    special_instructions: Optional[str] = None
    status: Optional[LoadStatus] = None


class LoadResponse(BaseModel):
    """Load response schema."""
    id: str
    load_number: str
    reference_number: Optional[str]
    status: LoadStatus
    origin_city: str
    origin_state: str
    origin_zip: Optional[str]
    destination_city: str
    destination_state: str
    destination_zip: Optional[str]
    pickup_date: datetime
    delivery_date: datetime
    equipment_type: str
    weight: Optional[float]
    pieces: Optional[int]
    commodity: Optional[str]
    miles: Optional[float]
    rate: Optional[float]
    rate_per_mile: Optional[float]
    is_public: bool
    company_id: Optional[str]
    shipper_id: str
    assigned_carrier_id: Optional[str]
    assigned_driver_id: Optional[str]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class LoadListResponse(BaseModel):
    """Paginated load list response."""
    loads: List[LoadResponse]
    total: int
    page: int
    page_size: int


class LoadApplicationCreate(BaseModel):
    """Create load application request."""
    proposed_rate: Optional[float] = None
    notes: Optional[str] = None
    # Aliases for backward compatibility
    bid_amount: Optional[float] = None
    message: Optional[str] = None


class LoadApplicationResponse(BaseModel):
    """Load application response."""
    id: str
    load_id: str
    carrier_id: str
    status: str
    bid_amount: Optional[float]
    message: Optional[str]
    rejection_reason: Optional[str] = None
    compliance_score: Optional[float]
    compliance_passed: Optional[bool]
    created_at: datetime

    class Config:
        from_attributes = True


class LoadApplicationListResponse(BaseModel):
    """Paginated load application list response."""
    applications: List[LoadApplicationResponse]
    total: int
    page: int
    page_size: int


class LoadAssignmentCreate(BaseModel):
    """Create load assignment request."""
    load_id: str
    carrier_id: str
    driver_id: Optional[str] = None
    agreed_rate: Optional[float] = None


class LoadAssignmentResponse(BaseModel):
    """Load assignment response."""
    id: str
    load_id: str
    carrier_id: str
    driver_id: Optional[str]
    status: str
    assigned_by: str
    agreed_rate: Optional[float]
    rate_confirmation_signed: bool
    created_at: datetime

    class Config:
        from_attributes = True


class LoadStatusUpdate(BaseModel):
    """Update load status request."""
    status: LoadStatus
    notes: Optional[str] = None
    location: Optional[Dict[str, Any]] = None  # {lat, lng, city, state}


class LoadSearchRequest(BaseModel):
    """Load search/filter request."""
    origin_state: Optional[str] = None
    origin_city: Optional[str] = None
    destination_state: Optional[str] = None
    destination_city: Optional[str] = None
    equipment_type: Optional[str] = None
    pickup_date_from: Optional[datetime] = None
    pickup_date_to: Optional[datetime] = None
    min_rate: Optional[float] = None
    max_weight: Optional[float] = None
    status: Optional[LoadStatus] = None


class LoadMatchResult(BaseModel):
    """Load matching result."""
    load: LoadResponse
    match_score: float
    compliance_check: Dict[str, Any]
    distance_from_lane: Optional[float]

