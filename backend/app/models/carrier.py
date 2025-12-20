"""Carrier-related database models."""
from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, Text, Integer, Float
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid

from ..core.database import Base


class Carrier(Base):
    """Carrier profile model."""
    __tablename__ = "carriers"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    company_id = Column(String(36), ForeignKey("companies.id"), nullable=False, index=True)
    
    # FMCSA verification
    fmcsa_verified = Column(Boolean, default=False)
    fmcsa_verification_date = Column(DateTime, nullable=True)
    fmcsa_verification_data = Column(Text, nullable=True)  # JSON
    
    # Compliance
    compliance_score = Column(Float, default=0.0)
    compliance_status = Column(String(50), default="pending")  # pending, compliant, non_compliant
    last_compliance_check = Column(DateTime, nullable=True)
    
    # Equipment
    equipment_types = Column(Text, nullable=True)  # JSON array
    power_units = Column(Integer, default=0)
    trailers = Column(Integer, default=0)
    
    # Service areas
    service_states = Column(Text, nullable=True)  # JSON array
    preferred_lanes = Column(Text, nullable=True)  # JSON array
    
    # Insurance
    insurance_status = Column(String(50), nullable=True)
    insurance_expiry = Column(DateTime, nullable=True)
    cargo_insurance_limit = Column(Float, nullable=True)
    liability_insurance_limit = Column(Float, nullable=True)
    
    # Performance metrics
    on_time_delivery_rate = Column(Float, nullable=True)
    damage_claim_rate = Column(Float, nullable=True)
    total_loads_completed = Column(Integer, default=0)
    average_rating = Column(Float, nullable=True)
    
    # Status
    is_active = Column(Boolean, default=True)
    available_for_loads = Column(Boolean, default=True)
    
    # Timestamps
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    
    # Relationships
    company = relationship("Company", back_populates="carriers")
    drivers = relationship("Driver", back_populates="carrier")
    lanes = relationship("Lane", back_populates="carrier")
    applications = relationship("LoadApplication", back_populates="carrier")


class CarrierProfile(Base):
    """Extended carrier profile with additional details."""
    __tablename__ = "carrier_profiles"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    carrier_id = Column(String(36), ForeignKey("carriers.id"), nullable=False, unique=True)
    
    # Certifications
    hazmat_certified = Column(Boolean, default=False)
    tanker_certified = Column(Boolean, default=False)
    twic_card = Column(Boolean, default=False)
    tsa_certified = Column(Boolean, default=False)
    
    # Specializations
    specializations = Column(Text, nullable=True)  # JSON array
    
    # Documents status
    authority_active = Column(Boolean, default=False)
    boc3_filed = Column(Boolean, default=False)
    ifta_active = Column(Boolean, default=False)
    ucr_active = Column(Boolean, default=False)
    
    # Banking/Payment
    factoring_company = Column(String(255), nullable=True)
    payment_method = Column(String(50), nullable=True)
    
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class Lane(Base):
    """Carrier preferred lanes."""
    __tablename__ = "lanes"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    carrier_id = Column(String(36), ForeignKey("carriers.id"), nullable=False, index=True)
    
    origin_city = Column(String(100), nullable=True)
    origin_state = Column(String(50), nullable=False)
    destination_city = Column(String(100), nullable=True)
    destination_state = Column(String(50), nullable=False)
    
    equipment_type = Column(String(50), nullable=True)
    preferred_rate = Column(Float, nullable=True)
    
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())
    
    # Relationships
    carrier = relationship("Carrier", back_populates="lanes")

