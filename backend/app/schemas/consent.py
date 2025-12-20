"""Consent and E-Signature schemas."""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime

from ..models.consent import ConsentType


class ConsentCreate(BaseModel):
    """Create consent form request."""
    consent_type: ConsentType
    version: str = "1.0"
    title: str
    description: Optional[str] = None
    content: Optional[str] = None
    template_url: Optional[str] = None
    is_required: bool = True
    applies_to_roles: Optional[List[str]] = None
    effective_date: Optional[datetime] = None
    expiry_date: Optional[datetime] = None


class ConsentUpdate(BaseModel):
    """Update consent form request."""
    title: Optional[str] = None
    description: Optional[str] = None
    content: Optional[str] = None
    template_url: Optional[str] = None
    is_required: Optional[bool] = None
    is_active: Optional[bool] = None


class ConsentResponse(BaseModel):
    """Consent form response."""
    id: str
    consent_type: ConsentType
    version: str
    title: str
    description: Optional[str]
    content: Optional[str]
    template_url: Optional[str]
    is_required: bool
    is_active: bool
    applies_to_roles: Optional[List[str]]
    effective_date: Optional[datetime]
    expiry_date: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ConsentListResponse(BaseModel):
    """Paginated consent list response."""
    items: List[ConsentResponse]
    total: int
    page: int
    page_size: int


class ESignatureCreate(BaseModel):
    """Create e-signature request."""
    consent_id: Optional[str] = None
    document_id: Optional[str] = None
    load_id: Optional[str] = None
    signature_image: Optional[str] = None  # Base64
    signature_type: str = "drawn"  # drawn, typed, uploaded
    typed_name: Optional[str] = None
    agreement_text: str


class ESignatureResponse(BaseModel):
    """E-signature response."""
    id: str
    user_id: str
    consent_id: Optional[str]
    document_id: Optional[str]
    load_id: Optional[str]
    signature_type: str
    typed_name: Optional[str]
    consent_given: bool
    ip_address: Optional[str]
    signed_at: datetime
    signature_hash: Optional[str]

    class Config:
        from_attributes = True


class UserConsentStatus(BaseModel):
    """User's consent status for all required consents."""
    user_id: str
    pending_consents: List[ConsentResponse]
    signed_consents: List[ESignatureResponse]
    all_required_signed: bool


class ConsentVerificationRequest(BaseModel):
    """Request to verify a signature."""
    signature_id: str
    verification_code: Optional[str] = None

