"""Document Vault API routes."""
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status, Query, UploadFile, File, Form, Request
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from ..core.database import get_db
from ..core.security import get_current_user, get_current_active_user, require_roles
from ..models.user import User, UserRole
from ..models.document import DocumentType
from ..schemas.document import (
    DocumentResponse, DocumentListResponse, DocumentUploadResponse,
    DocumentValidationResult, DocumentSearchRequest
)
from ..services.document_service import DocumentService


class PODSignRequest(BaseModel):
    """Request to sign a POD document."""
    signature_image: str  # Base64 encoded
    signature_type: str = "drawn"  # drawn, typed, uploaded
    typed_name: Optional[str] = None
    geolocation: Optional[str] = None


router = APIRouter(prefix="/documents", tags=["Documents"])


@router.post("", response_model=DocumentUploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(
    file: UploadFile = File(...),
    document_type: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    expiry_date: Optional[str] = Form(None),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Upload a new document."""
    doc_service = DocumentService(db)

    try:
        # Read file content
        content = await file.read()

        # Parse document type
        doc_type = None
        if document_type:
            try:
                doc_type = DocumentType(document_type)
            except ValueError:
                pass

        # Parse expiry date
        parsed_expiry = None
        if expiry_date:
            try:
                from datetime import datetime
                parsed_expiry = datetime.fromisoformat(expiry_date)
            except ValueError:
                pass

        result = await doc_service.upload_document(
            owner_id=current_user.id,
            file_content=content,
            filename=file.filename,
            mime_type=file.content_type,
            document_type=doc_type,
            description=description,
            expiry_date=parsed_expiry,
        )

        return result

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/upload", response_model=DocumentUploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_document_alias(
    file: UploadFile = File(...),
    document_type: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    expiry_date: Optional[str] = Form(None),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Upload a new document (alias endpoint)."""
    return await upload_document(file, document_type, description, expiry_date, current_user, db)


@router.get("", response_model=DocumentListResponse)
async def list_documents(
    document_type: Optional[str] = None,
    status: Optional[str] = Query("active"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """List user's documents."""
    doc_service = DocumentService(db)
    
    doc_type = None
    if document_type:
        try:
            doc_type = DocumentType(document_type)
        except ValueError:
            pass
    
    documents, total = await doc_service.list_documents(
        owner_id=current_user.id,
        document_type=doc_type,
        status=status,
        page=page,
        page_size=page_size,
    )
    
    return DocumentListResponse(
        documents=documents,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{document_id}", response_model=DocumentResponse)
async def get_document(
    document_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Get document by ID."""
    doc_service = DocumentService(db)
    
    document = await doc_service.get_document(document_id)
    
    if not document:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    
    # Check ownership or admin
    if document.owner_id != current_user.id and current_user.role not in [UserRole.ADMIN, UserRole.SUPER_ADMIN]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    
    return document


@router.delete("/{document_id}")
async def delete_document(
    document_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Delete (archive) a document."""
    doc_service = DocumentService(db)
    
    document = await doc_service.get_document(document_id)
    
    if not document:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    
    if document.owner_id != current_user.id and current_user.role not in [UserRole.ADMIN, UserRole.SUPER_ADMIN]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    
    await doc_service.archive_document(document_id)
    return {"message": "Document archived"}


@router.post("/{document_id}/validate", response_model=DocumentValidationResult)
async def validate_document(
    document_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Validate a document using AI."""
    doc_service = DocumentService(db)
    
    document = await doc_service.get_document(document_id)
    
    if not document:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    
    if document.owner_id != current_user.id and current_user.role not in [UserRole.ADMIN, UserRole.SUPER_ADMIN]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    
    result = await doc_service.validate_document(document_id)
    return result


@router.get("/{document_id}/download")
async def download_document(
    document_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Get document download URL."""
    doc_service = DocumentService(db)

    document = await doc_service.get_document(document_id)

    if not document:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    if document.owner_id != current_user.id and current_user.role not in [UserRole.ADMIN, UserRole.SUPER_ADMIN]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    return {"download_url": document.file_url, "filename": document.original_filename}


@router.post("/{document_id}/version", response_model=DocumentResponse)
async def upload_new_version(
    document_id: str,
    file: UploadFile = File(...),
    changes_description: Optional[str] = Form(None),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Upload a new version of an existing document."""
    doc_service = DocumentService(db)

    # Verify ownership
    document = await doc_service.get_document(document_id)
    if not document:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    if document.owner_id != current_user.id and current_user.role not in [UserRole.ADMIN, UserRole.SUPER_ADMIN]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    try:
        content = await file.read()
        result = await doc_service.upload_new_version(
            document_id=document_id,
            file_content=content,
            filename=file.filename,
            mime_type=file.content_type,
            user_id=current_user.id,
            changes_description=changes_description,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/{document_id}/versions")
async def get_document_versions(
    document_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Get version history for a document."""
    doc_service = DocumentService(db)

    document = await doc_service.get_document(document_id)
    if not document:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    if document.owner_id != current_user.id and current_user.role not in [UserRole.ADMIN, UserRole.SUPER_ADMIN]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    versions = await doc_service.get_document_versions(document_id)
    return {
        "document_id": document_id,
        "current_version": document.version,
        "versions": [
            {
                "version": v.version,
                "file_path": v.file_path,
                "file_size": v.file_size,
                "changes": v.changes,
                "created_at": v.created_at,
            }
            for v in versions
        ]
    }


@router.get("/alerts/expiring")
async def get_expiry_alerts(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Get documents expiring soon (30/14/7/1 days) or already expired."""
    doc_service = DocumentService(db)

    alerts = await doc_service.get_expiry_alerts()

    # Filter by user unless admin
    if current_user.role not in [UserRole.ADMIN, UserRole.SUPER_ADMIN]:
        for category in alerts:
            alerts[category] = [
                doc for doc in alerts[category]
                if doc["owner_id"] == current_user.id
            ]

    return {
        "alerts": alerts,
        "summary": {
            "expired": len(alerts["expired"]),
            "critical_1_day": len(alerts["1_day"]),
            "urgent_7_days": len(alerts["7_days"]),
            "warning_14_days": len(alerts["14_days"]),
            "notice_30_days": len(alerts["30_days"]),
        }
    }


@router.post("/{document_id}/sign-pod")
async def sign_pod_document(
    document_id: str,
    data: PODSignRequest,
    request: Request,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Sign a POD document with timestamp, IP, and metadata embedded."""
    doc_service = DocumentService(db)

    # Verify ownership or driver role
    document = await doc_service.get_document(document_id)
    if not document:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    if document.owner_id != current_user.id and current_user.role not in [UserRole.DRIVER, UserRole.CARRIER, UserRole.ADMIN]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    try:
        result = await doc_service.sign_pod_document(
            document_id=document_id,
            user_id=current_user.id,
            signature_image=data.signature_image,
            signature_type=data.signature_type,
            typed_name=data.typed_name,
            ip_address=request.client.host,
            user_agent=request.headers.get("user-agent"),
            geolocation=data.geolocation,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/{document_id}/verify-signature")
async def verify_pod_signature(
    document_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Verify a POD document's signature and metadata. Public endpoint for verification."""
    doc_service = DocumentService(db)

    result = await doc_service.verify_pod_signature(document_id)
    return result
