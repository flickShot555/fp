"""Driver schemas."""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime, date

from ..models.driver import DriverStatus


class DriverCreate(BaseModel):
    """Create driver request."""
    first_name: str
    last_name: str
    date_of_birth: Optional[date] = None
    cdl_number: Optional[str] = None
    cdl_state: Optional[str] = None
    cdl_class: Optional[str] = None
    cdl_expiry: Optional[date] = None
    carrier_id: Optional[str] = None


class DriverUpdate(BaseModel):
    """Update driver request."""
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    status: Optional[DriverStatus] = None
    cdl_number: Optional[str] = None
    cdl_state: Optional[str] = None
    cdl_class: Optional[str] = None
    cdl_expiry: Optional[date] = None
    medical_card_expiry: Optional[date] = None
    current_city: Optional[str] = None
    current_state: Optional[str] = None
    hours_available: Optional[float] = None


class DriverResponse(BaseModel):
    """Driver response schema."""
    id: str
    user_id: str
    carrier_id: Optional[str]
    status: DriverStatus
    first_name: str
    last_name: str
    cdl_number: Optional[str]
    cdl_state: Optional[str]
    cdl_class: Optional[str]
    cdl_expiry: Optional[date]
    cdl_verified: bool
    hazmat_endorsement: bool
    tanker_endorsement: bool
    medical_card_expiry: Optional[date]
    medical_card_verified: bool
    years_experience: Optional[float]
    safety_score: Optional[float]
    on_time_rate: Optional[float]
    compliance_score: float
    onboarding_completed: bool
    current_city: Optional[str]
    current_state: Optional[str]
    hours_available: Optional[float]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class DriverListResponse(BaseModel):
    """Paginated driver list response."""
    items: List[DriverResponse]
    total: int
    page: int
    page_size: int
    pages: int


class DriverLocationUpdate(BaseModel):
    """Update driver location."""
    lat: float
    lng: float
    city: Optional[str] = None
    state: Optional[str] = None


class DriverHOSUpdate(BaseModel):
    """Update driver Hours of Service."""
    hours_available: float
    cycle_hours_used: float
    status: DriverStatus


class DriverComplianceStatus(BaseModel):
    """Driver compliance status."""
    driver_id: str
    is_compliant: bool
    score: float
    cdl_valid: bool
    medical_valid: bool
    drug_test_status: Optional[str]
    clearinghouse_status: Optional[str]
    missing_documents: List[str]
    expiring_documents: List[Dict[str, Any]]


class DriverAssignmentRequest(BaseModel):
    """Request to assign driver to load."""
    driver_id: str
    load_id: str
    notes: Optional[str] = None


class DriverSearchRequest(BaseModel):
    """Search drivers request."""
    carrier_id: Optional[str] = None
    status: Optional[DriverStatus] = None
    state: Optional[str] = None
    cdl_class: Optional[str] = None
    hazmat: Optional[bool] = None
    min_hours_available: Optional[float] = None

