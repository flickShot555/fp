"""Driver-related database models."""
from sqlalchemy import Column, String, Boolean, DateTime, Enum, ForeignKey, Text, Float, Date
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum
import uuid

from ..core.database import Base


class DriverStatus(str, enum.Enum):
    """Driver availability status."""
    AVAILABLE = "available"
    ON_LOAD = "on_load"
    OFF_DUTY = "off_duty"
    ON_BREAK = "on_break"
    HOME_TIME = "home_time"
    UNAVAILABLE = "unavailable"


class Driver(Base):
    """Driver model."""
    __tablename__ = "drivers"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, unique=True, index=True)
    carrier_id = Column(String(36), ForeignKey("carriers.id"), nullable=True, index=True)
    
    # Status
    status = Column(Enum(DriverStatus), default=DriverStatus.UNAVAILABLE)
    
    # Personal Info
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)
    date_of_birth = Column(Date, nullable=True)
    
    # CDL Info
    cdl_number = Column(String(50), nullable=True)
    cdl_state = Column(String(50), nullable=True)
    cdl_class = Column(String(10), nullable=True)  # A, B, C
    cdl_expiry = Column(Date, nullable=True)
    cdl_verified = Column(Boolean, default=False)
    
    # Endorsements
    hazmat_endorsement = Column(Boolean, default=False)
    tanker_endorsement = Column(Boolean, default=False)
    doubles_triples = Column(Boolean, default=False)
    passenger_endorsement = Column(Boolean, default=False)
    
    # Medical
    medical_card_expiry = Column(Date, nullable=True)
    medical_card_verified = Column(Boolean, default=False)
    
    # Drug & Alcohol
    last_drug_test = Column(DateTime, nullable=True)
    drug_test_status = Column(String(50), nullable=True)  # passed, pending, failed
    clearinghouse_status = Column(String(50), nullable=True)
    
    # Experience
    years_experience = Column(Float, nullable=True)
    total_miles = Column(Float, nullable=True)
    
    # Performance
    safety_score = Column(Float, nullable=True)
    on_time_rate = Column(Float, nullable=True)
    total_loads = Column(Float, default=0)
    
    # Location
    current_city = Column(String(100), nullable=True)
    current_state = Column(String(50), nullable=True)
    current_lat = Column(Float, nullable=True)
    current_lng = Column(Float, nullable=True)
    last_location_update = Column(DateTime, nullable=True)
    
    # ELD Info
    eld_provider = Column(String(100), nullable=True)
    eld_device_id = Column(String(100), nullable=True)
    
    # Available hours (HOS)
    hours_available = Column(Float, nullable=True)
    cycle_hours_used = Column(Float, nullable=True)
    
    # Compliance
    compliance_score = Column(Float, default=0.0)
    onboarding_completed = Column(Boolean, default=False)
    
    # Timestamps
    hire_date = Column(DateTime, nullable=True)
    termination_date = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    
    # Relationships
    carrier = relationship("Carrier", back_populates="drivers")

