"""Company-related database models."""
from sqlalchemy import Column, String, Boolean, DateTime, Enum, Text, Integer, Float
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum
import uuid

from ..core.database import Base


class CompanyType(str, enum.Enum):
    """Types of companies."""
    CARRIER = "carrier"
    SHIPPER = "shipper"
    BROKER = "broker"
    FACTORING = "factoring"
    INSURANCE = "insurance"
    SERVICE_PROVIDER = "service_provider"


class Company(Base):
    """Company/Organization model."""
    __tablename__ = "companies"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(255), nullable=False, index=True)
    legal_name = Column(String(255), nullable=True)
    dba_name = Column(String(255), nullable=True)
    company_type = Column(Enum(CompanyType), nullable=False)
    
    # Identifiers
    usdot = Column(String(20), unique=True, nullable=True, index=True)
    mc_number = Column(String(20), unique=True, nullable=True, index=True)
    ein = Column(String(20), nullable=True)
    scac_code = Column(String(10), nullable=True)
    
    # Contact
    email = Column(String(255), nullable=True)
    phone = Column(String(20), nullable=True)
    fax = Column(String(20), nullable=True)
    website = Column(String(255), nullable=True)
    
    # Address
    address_line1 = Column(String(255), nullable=True)
    address_line2 = Column(String(255), nullable=True)
    city = Column(String(100), nullable=True)
    state = Column(String(50), nullable=True)
    zip_code = Column(String(20), nullable=True)
    country = Column(String(50), default="USA")
    
    # FMCSA Data
    fmcsa_status = Column(String(50), nullable=True)  # AUTHORIZED, PENDING, REVOKED
    authority_status = Column(String(50), nullable=True)
    safety_rating = Column(String(50), nullable=True)
    safety_rating_date = Column(DateTime, nullable=True)
    insurance_status = Column(String(50), nullable=True)
    operating_status = Column(String(50), nullable=True)
    
    # Fleet Info (for carriers)
    power_units = Column(Integer, default=0)
    drivers_count = Column(Integer, default=0)
    equipment_types = Column(Text, nullable=True)  # JSON array
    service_areas = Column(Text, nullable=True)  # JSON array
    
    # Compliance
    compliance_score = Column(Float, default=0.0)
    last_compliance_check = Column(DateTime, nullable=True)
    
    # Billing (for shippers)
    billing_address = Column(Text, nullable=True)
    payment_terms = Column(String(50), nullable=True)
    credit_limit = Column(Float, nullable=True)
    
    # Status
    is_active = Column(Boolean, default=True)
    verified = Column(Boolean, default=False)
    verified_at = Column(DateTime, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    
    # Relationships
    users = relationship("User", back_populates="company")
    carriers = relationship("Carrier", back_populates="company")
    loads = relationship("Load", back_populates="company")
    documents = relationship("Document", back_populates="company")

