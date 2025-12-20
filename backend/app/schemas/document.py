"""Document schemas."""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime

from ..models.document import DocumentType


class DocumentUploadResponse(BaseModel):
    """Response after document upload."""
    id: str
    filename: str
    document_type: DocumentType
    classification_confidence: Optional[float]
    extracted_data: Optional[Dict[str, Any]]
    validation_status: str
    validation_issues: Optional[List[str]]
    validation_score: float
    expiry_date: Optional[datetime]
    created_at: datetime


class DocumentResponse(BaseModel):
    """Document response schema."""
    id: str
    filename: str
    original_filename: str
    file_name: Optional[str] = None  # Alias for original_filename for frontend compatibility
    document_type: DocumentType
    file_size: Optional[int]
    mime_type: Optional[str]
    validation_status: str
    validation_score: float
    expiry_date: Optional[datetime]
    days_until_expiry: Optional[int]
    is_signed: bool
    version: int
    status: str
    owner_id: str
    company_id: Optional[str]
    load_id: Optional[str]
    created_at: datetime
    updated_at: datetime
    description: Optional[str] = None

    class Config:
        from_attributes = True

    def __init__(self, **data):
        super().__init__(**data)
        if self.file_name is None:
            self.file_name = self.original_filename


class DocumentListResponse(BaseModel):
    """Paginated document list response."""
    documents: List[DocumentResponse]
    total: int
    page: int
    page_size: int


class DocumentSearchRequest(BaseModel):
    """Document search request."""
    document_type: Optional[str] = None
    status: Optional[str] = None
    owner_id: Optional[str] = None
    company_id: Optional[str] = None
    search: Optional[str] = None


class DocumentVersionResponse(BaseModel):
    """Document version response."""
    id: str
    document_id: str
    version: int
    file_path: str
    file_size: Optional[int]
    changes: Optional[str]
    created_by: str
    created_at: datetime

    class Config:
        from_attributes = True


class DocumentValidationResult(BaseModel):
    """Document validation result."""
    document_id: str
    is_valid: bool
    validation_score: float
    issues: List[str]
    warnings: List[str]
    extracted_data: Dict[str, Any]


class ExpiryAlertResponse(BaseModel):
    """Document expiry alert."""
    document_id: str
    document_type: DocumentType
    filename: str
    expiry_date: datetime
    days_until_expiry: int
    owner_name: str
    company_name: Optional[str]


class DocumentClassificationRequest(BaseModel):
    """Manual document classification request."""
    document_id: str
    document_type: DocumentType
    issue_date: Optional[datetime] = None
    expiry_date: Optional[datetime] = None


class DocumentSignRequest(BaseModel):
    """Request to sign a document."""
    document_id: str
    signature_image: str  # Base64
    signature_type: str = "drawn"  # drawn, typed
    typed_name: Optional[str] = None
    agreement_text: str


class BulkDocumentUploadResponse(BaseModel):
    """Response for bulk document upload."""
    total_files: int
    successful: int
    failed: int
    documents: List[DocumentUploadResponse]
    errors: List[Dict[str, Any]]

