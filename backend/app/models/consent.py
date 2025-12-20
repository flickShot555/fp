"""Consent and E-Signature related database models."""
from sqlalchemy import Column, String, Boolean, DateTime, Enum, ForeignKey, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum
import uuid

from ..core.database import Base


class ConsentType(str, enum.Enum):
    """Types of consent forms."""
    TERMS_OF_SERVICE = "terms_of_service"
    PRIVACY_POLICY = "privacy_policy"
    CLEARINGHOUSE = "clearinghouse"
    BACKGROUND_CHECK = "background_check"
    DRUG_TEST = "drug_test"
    MVR_CHECK = "mvr_check"
    RATE_CONFIRMATION = "rate_confirmation"
    POD = "pod"  # Proof of Delivery
    CARRIER_AGREEMENT = "carrier_agreement"
    DRIVER_AGREEMENT = "driver_agreement"
    BROKER_AGREEMENT = "broker_agreement"
    NDA = "nda"
    OTHER = "other"


class Consent(Base):
    """Consent record model."""
    __tablename__ = "consents"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    
    # Consent details
    consent_type = Column(Enum(ConsentType), nullable=False, index=True)
    version = Column(String(20), nullable=False, default="1.0")
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    content = Column(Text, nullable=True)  # Full consent text/HTML
    template_url = Column(String(500), nullable=True)  # Link to PDF/document template
    
    # Required/Active
    is_required = Column(Boolean, default=True)
    is_active = Column(Boolean, default=True)
    
    # Applicability
    applies_to_roles = Column(Text, nullable=True)  # JSON array of roles
    
    # Timestamps
    effective_date = Column(DateTime, nullable=True)
    expiry_date = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class ESignature(Base):
    """E-Signature capture model."""
    __tablename__ = "esignatures"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    
    # Foreign Keys
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    consent_id = Column(String(36), ForeignKey("consents.id"), nullable=True)
    document_id = Column(String(36), ForeignKey("documents.id"), nullable=True)
    load_id = Column(String(36), ForeignKey("loads.id"), nullable=True)
    
    # Signature data
    signature_image = Column(Text, nullable=True)  # Base64 encoded image
    signature_type = Column(String(50), default="drawn")  # drawn, typed, uploaded
    typed_name = Column(String(255), nullable=True)
    
    # Legal agreement
    agreement_text = Column(Text, nullable=False)  # What they agreed to
    consent_given = Column(Boolean, default=True)
    
    # Verification
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(String(500), nullable=True)
    geolocation = Column(Text, nullable=True)  # JSON with lat/lng
    
    # Timestamps
    signed_at = Column(DateTime, server_default=func.now())
    expires_at = Column(DateTime, nullable=True)
    
    # Hash for integrity
    signature_hash = Column(String(255), nullable=True)

