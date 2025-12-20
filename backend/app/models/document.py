"""Document-related database models."""
from sqlalchemy import Column, String, Boolean, DateTime, Enum, ForeignKey, Text, Integer, Float
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum
import uuid

from ..core.database import Base


class DocumentType(str, enum.Enum):
    """Types of documents in the system."""
    CDL = "cdl"
    MC_CERTIFICATE = "mc_certificate"
    COI = "coi"  # Certificate of Insurance
    W9 = "w9"
    BOL = "bol"  # Bill of Lading
    POD = "pod"  # Proof of Delivery
    RATE_CONFIRMATION = "rate_confirmation"
    INVOICE = "invoice"
    MVR = "mvr"  # Motor Vehicle Record
    MEDICAL_CARD = "medical_card"
    DRUG_TEST = "drug_test"
    CLEARINGHOUSE_CONSENT = "clearinghouse_consent"
    DRIVER_APPLICATION = "driver_application"
    AUTHORITY = "authority"
    IFTA = "ifta"
    UCR = "ucr"
    BOC3 = "boc3"
    OTHER = "other"


class Document(Base):
    """Document model for storing uploaded files and their metadata."""
    __tablename__ = "documents"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    
    # File info
    filename = Column(String(255), nullable=False)
    original_filename = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=False)  # S3 path or local path
    file_size = Column(Integer, nullable=True)
    mime_type = Column(String(100), nullable=True)
    
    # Document classification
    document_type = Column(Enum(DocumentType), nullable=False, default=DocumentType.OTHER)
    classification_confidence = Column(Float, nullable=True)
    description = Column(Text, nullable=True)
    
    # Extracted data
    extracted_text = Column(Text, nullable=True)
    extracted_data = Column(Text, nullable=True)  # JSON
    ocr_data = Column(Text, nullable=True)  # JSON
    
    # Validation
    validation_status = Column(String(50), default="pending")  # pending, valid, invalid, expired
    validation_issues = Column(Text, nullable=True)  # JSON array
    validation_score = Column(Float, default=0.0)
    
    # Expiry tracking
    issue_date = Column(DateTime, nullable=True)
    expiry_date = Column(DateTime, nullable=True)
    expiry_alert_sent = Column(Boolean, default=False)
    days_until_expiry = Column(Integer, nullable=True)
    
    # E-signature
    is_signed = Column(Boolean, default=False)
    signed_at = Column(DateTime, nullable=True)
    signature_data = Column(Text, nullable=True)  # JSON with signature metadata
    
    # Version control
    version = Column(Integer, default=1)
    is_latest = Column(Boolean, default=True)
    previous_version_id = Column(String(36), nullable=True)
    
    # Status
    status = Column(String(50), default="active")  # active, archived, deleted
    
    # Timestamps
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    
    # Foreign Keys
    owner_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    company_id = Column(String(36), ForeignKey("companies.id"), nullable=True, index=True)
    load_id = Column(String(36), ForeignKey("loads.id"), nullable=True, index=True)
    
    # Relationships
    owner = relationship("User", back_populates="documents")
    company = relationship("Company", back_populates="documents")
    load = relationship("Load", back_populates="documents")
    versions = relationship("DocumentVersion", back_populates="document")


class DocumentVersion(Base):
    """Document version history."""
    __tablename__ = "document_versions"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    document_id = Column(String(36), ForeignKey("documents.id"), nullable=False, index=True)
    version = Column(Integer, nullable=False)
    file_path = Column(String(500), nullable=False)
    file_size = Column(Integer, nullable=True)
    changes = Column(Text, nullable=True)  # Description of changes
    created_by = Column(String(36), ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, server_default=func.now())
    
    # Relationships
    document = relationship("Document", back_populates="versions")

