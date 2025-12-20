"""Load/Shipment-related database models."""
from sqlalchemy import Column, String, Boolean, DateTime, Enum, ForeignKey, Text, Integer, Float
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum
import uuid

from ..core.database import Base


class LoadStatus(str, enum.Enum):
    """Load lifecycle status."""
    DRAFT = "draft"
    POSTED = "posted"
    TENDERED = "tendered"
    ACCEPTED = "accepted"
    PLANNED = "planned"
    DISPATCHED = "dispatched"
    EN_ROUTE = "en_route"
    AT_PICKUP = "at_pickup"
    LOADED = "loaded"
    IN_TRANSIT = "in_transit"
    AT_DELIVERY = "at_delivery"
    DELIVERED = "delivered"
    POD_RECEIVED = "pod_received"
    INVOICED = "invoiced"
    PAID = "paid"
    CLOSED = "closed"
    CANCELLED = "cancelled"


class Load(Base):
    """Load/Shipment model."""
    __tablename__ = "loads"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    load_number = Column(String(50), unique=True, nullable=False, index=True)
    reference_number = Column(String(100), nullable=True)
    
    # Status
    status = Column(Enum(LoadStatus), default=LoadStatus.DRAFT, index=True)
    
    # Origin
    origin_address = Column(String(255), nullable=True)
    origin_city = Column(String(100), nullable=False)
    origin_state = Column(String(50), nullable=False)
    origin_zip = Column(String(20), nullable=True)
    origin_lat = Column(Float, nullable=True)
    origin_lng = Column(Float, nullable=True)
    
    # Destination
    destination_address = Column(String(255), nullable=True)
    destination_city = Column(String(100), nullable=False)
    destination_state = Column(String(50), nullable=False)
    destination_zip = Column(String(20), nullable=True)
    destination_lat = Column(Float, nullable=True)
    destination_lng = Column(Float, nullable=True)
    
    # Stops (for multi-stop loads)
    stops = Column(Text, nullable=True)  # JSON array of stops
    
    # Dates
    pickup_date = Column(DateTime, nullable=False)
    pickup_time_start = Column(String(10), nullable=True)
    pickup_time_end = Column(String(10), nullable=True)
    delivery_date = Column(DateTime, nullable=False)
    delivery_time_start = Column(String(10), nullable=True)
    delivery_time_end = Column(String(10), nullable=True)
    
    # Load details
    equipment_type = Column(String(50), nullable=False)  # dry_van, reefer, flatbed, etc.
    weight = Column(Float, nullable=True)
    pieces = Column(Integer, nullable=True)
    commodity = Column(String(255), nullable=True)
    special_instructions = Column(Text, nullable=True)
    temperature_min = Column(Float, nullable=True)  # For reefer
    temperature_max = Column(Float, nullable=True)
    
    # Distance & Rate
    miles = Column(Float, nullable=True)
    rate = Column(Float, nullable=True)
    rate_per_mile = Column(Float, nullable=True)
    accessorials = Column(Text, nullable=True)  # JSON
    
    # Visibility
    is_public = Column(Boolean, default=False)  # Posted to marketplace
    is_broadcast = Column(Boolean, default=False)  # Broadcast to carriers
    
    # Agreed rate (after negotiation)
    agreed_rate = Column(Float, nullable=True)

    # Timestamps
    posted_at = Column(DateTime, nullable=True)
    awarded_at = Column(DateTime, nullable=True)
    dispatched_at = Column(DateTime, nullable=True)
    picked_up_at = Column(DateTime, nullable=True)
    delivered_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    
    # Foreign Keys
    company_id = Column(String(36), ForeignKey("companies.id"), nullable=True, index=True)
    shipper_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    assigned_carrier_id = Column(String(36), ForeignKey("carriers.id"), nullable=True)
    assigned_driver_id = Column(String(36), ForeignKey("drivers.id"), nullable=True)
    
    # Relationships
    company = relationship("Company", back_populates="loads")
    applications = relationship("LoadApplication", back_populates="load")
    assignments = relationship("LoadAssignment", back_populates="load")
    documents = relationship("Document", back_populates="load")


class LoadApplication(Base):
    """Carrier application to a load."""
    __tablename__ = "load_applications"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    load_id = Column(String(36), ForeignKey("loads.id"), nullable=False, index=True)
    carrier_id = Column(String(36), ForeignKey("carriers.id"), nullable=False, index=True)
    
    status = Column(String(50), default="pending")  # pending, accepted, rejected, withdrawn
    bid_amount = Column(Float, nullable=True)
    message = Column(Text, nullable=True)
    rejection_reason = Column(Text, nullable=True)

    # Compliance check results
    compliance_score = Column(Float, nullable=True)
    compliance_passed = Column(Boolean, nullable=True)
    compliance_issues = Column(Text, nullable=True)  # JSON
    
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    
    # Relationships
    load = relationship("Load", back_populates="applications")
    carrier = relationship("Carrier", back_populates="applications")


class LoadAssignment(Base):
    """Load assignment history and tracking."""
    __tablename__ = "load_assignments"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    load_id = Column(String(36), ForeignKey("loads.id"), nullable=False, index=True)
    carrier_id = Column(String(36), ForeignKey("carriers.id"), nullable=False)
    driver_id = Column(String(36), ForeignKey("drivers.id"), nullable=True)
    
    status = Column(String(50), default="assigned")  # assigned, accepted, declined, completed
    assigned_by = Column(String(36), ForeignKey("users.id"), nullable=False)
    reason = Column(Text, nullable=True)
    
    # Rate confirmation
    agreed_rate = Column(Float, nullable=True)
    rate_confirmation_signed = Column(Boolean, default=False)
    rate_confirmation_signed_at = Column(DateTime, nullable=True)
    
    created_at = Column(DateTime, server_default=func.now())
    
    # Relationships
    load = relationship("Load", back_populates="assignments")

