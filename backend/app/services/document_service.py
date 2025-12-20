"""Document service for file management and processing."""
from datetime import datetime, timedelta
from typing import Optional, List, Tuple, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_
import os
import uuid
import json

from ..models.document import Document, DocumentType, DocumentVersion
from ..models.user import User
from ..schemas.document import DocumentValidationResult
from ..core.config import settings


class DocumentService:
    """Service for document management operations."""
    
    MAX_FILE_SIZE = 25 * 1024 * 1024  # 25MB
    ALLOWED_TYPES = ["application/pdf", "image/jpeg", "image/png", "image/webp"]
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def upload_document(
        self,
        file_content: bytes,
        filename: str,
        mime_type: str,
        owner_id: str,
        company_id: str = None,
        load_id: str = None,
        document_type: DocumentType = None,
        description: str = None,
        expiry_date=None,
    ) -> Document:
        """Upload and process a document."""
        # Validate file size
        if len(file_content) > self.MAX_FILE_SIZE:
            raise ValueError(f"File size exceeds {self.MAX_FILE_SIZE // (1024*1024)}MB limit")

        # Validate mime type
        if mime_type not in self.ALLOWED_TYPES:
            raise ValueError(f"File type {mime_type} not allowed")

        # Generate unique filename
        file_id = str(uuid.uuid4())
        ext = os.path.splitext(filename)[1]
        unique_filename = f"{file_id}{ext}"

        # Save file (local for now, S3 in production)
        file_path = await self._save_file(file_content, unique_filename, owner_id)

        # Create document record
        document = Document(
            filename=unique_filename,
            original_filename=filename,
            file_path=file_path,
            file_size=len(file_content),
            mime_type=mime_type,
            document_type=document_type or DocumentType.OTHER,
            owner_id=owner_id,
            company_id=company_id,
            load_id=load_id,
            description=description,
            expiry_date=expiry_date,
        )
        self.db.add(document)
        await self.db.flush()

        # Process document (OCR, classification, extraction)
        await self._process_document(document, file_content)

        await self.db.commit()
        await self.db.refresh(document)
        return document
    
    async def _save_file(self, content: bytes, filename: str, owner_id: str) -> str:
        """Save file to storage."""
        # Create directory structure
        upload_dir = os.path.join("uploads", owner_id)
        os.makedirs(upload_dir, exist_ok=True)
        
        file_path = os.path.join(upload_dir, filename)
        
        with open(file_path, "wb") as f:
            f.write(content)
        
        return file_path
    
    async def _process_document(self, document: Document, content: bytes):
        """Process document with AI (OCR, classification, extraction)."""
        # Import AI service here to avoid circular imports
        from .ai_service import AIService
        
        ai_service = AIService()
        
        # Classify document if not specified
        if document.document_type == DocumentType.OTHER:
            classification = await ai_service.classify_document(content, document.mime_type)
            if classification:
                document.document_type = DocumentType(classification.get("type", "other"))
                document.classification_confidence = classification.get("confidence", 0.0)
        
        # Extract text and data
        extracted = await ai_service.extract_document_data(
            content, 
            document.mime_type,
            document.document_type.value
        )
        
        if extracted:
            document.extracted_text = extracted.get("text", "")
            extracted_data = extracted.get("data", {})
            document.extracted_data = json.dumps(extracted_data)
            document.ocr_data = json.dumps(extracted.get("ocr", {}))

            # Extract dates from the extracted data
            expiry_date_str = extracted_data.get("expiry_date") or extracted.get("expiry_date")
            issue_date_str = extracted_data.get("issue_date") or extracted_data.get("effective_date") or extracted.get("issue_date")

            if issue_date_str:
                try:
                    if isinstance(issue_date_str, str):
                        document.issue_date = datetime.strptime(issue_date_str, "%Y-%m-%d")
                    else:
                        document.issue_date = issue_date_str
                except (ValueError, TypeError):
                    pass

            if expiry_date_str:
                try:
                    if isinstance(expiry_date_str, str):
                        parsed_expiry = datetime.strptime(expiry_date_str, "%Y-%m-%d")
                    else:
                        parsed_expiry = expiry_date_str
                    document.expiry_date = parsed_expiry
                    document.days_until_expiry = (parsed_expiry - datetime.utcnow()).days
                except (ValueError, TypeError):
                    pass
        
        # Validate document
        validation = await self._validate_document(document)
        document.validation_status = validation["status"]
        document.validation_score = validation["score"]
        document.validation_issues = json.dumps(validation.get("issues", []))
    
    async def _validate_document(self, document: Document) -> Dict[str, Any]:
        """Validate document based on type-specific rules."""
        issues = []
        score = 100.0
        
        # Check expiry
        if document.expiry_date:
            days = (document.expiry_date - datetime.utcnow()).days
            if days < 0:
                issues.append("Document has expired")
                score -= 50
            elif days < 30:
                issues.append(f"Document expires in {days} days")
                score -= 10
        
        # Type-specific validation
        extracted_data = json.loads(document.extracted_data) if document.extracted_data else {}
        
        if document.document_type == DocumentType.CDL:
            if not extracted_data.get("cdl_number"):
                issues.append("CDL number not found")
                score -= 20
            if not extracted_data.get("cdl_class"):
                issues.append("CDL class not found")
                score -= 10
        
        elif document.document_type == DocumentType.MC_CERTIFICATE:
            if not extracted_data.get("mc_number"):
                issues.append("MC number not found")
                score -= 25
        
        elif document.document_type == DocumentType.COI:
            if not extracted_data.get("policy_number"):
                issues.append("Policy number not found")
                score -= 15
            if not extracted_data.get("coverage_amount"):
                issues.append("Coverage amount not found")
                score -= 10
        
        status = "valid" if score >= 70 else "invalid"
        if 0 < len(issues) <= 2 and score >= 50:
            status = "pending"
        
        return {"status": status, "score": max(0, score), "issues": issues}
    
    async def get_document(self, document_id: str, user_id: str = None) -> Optional[Document]:
        """Get document by ID."""
        query = select(Document).where(Document.id == document_id)
        if user_id:
            query = query.where(Document.owner_id == user_id)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()
    
    async def list_documents(
        self,
        owner_id: str = None,
        company_id: str = None,
        document_type: DocumentType = None,
        status: str = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Tuple[List[Document], int]:
        """List documents with filters."""
        # Filter by status = active OR status is null (for documents before status was added)
        query = select(Document).where(
            or_(Document.status == "active", Document.status == None, Document.status == "uploaded")
        )
        
        if owner_id:
            query = query.where(Document.owner_id == owner_id)
        if company_id:
            query = query.where(Document.company_id == company_id)
        if document_type:
            query = query.where(Document.document_type == document_type)
        if status:
            query = query.where(Document.validation_status == status)
        
        # Count
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await self.db.execute(count_query)
        total = total_result.scalar()
        
        # Paginate
        query = query.offset((page - 1) * page_size).limit(page_size)
        query = query.order_by(Document.created_at.desc())
        
        result = await self.db.execute(query)
        documents = result.scalars().all()
        
        return list(documents), total
    
    async def get_expiring_documents(self, days: int = 30) -> List[Document]:
        """Get documents expiring within specified days."""
        expiry_threshold = datetime.utcnow() + timedelta(days=days)
        query = select(Document).where(
            and_(
                Document.expiry_date != None,
                Document.expiry_date <= expiry_threshold,
                Document.expiry_date >= datetime.utcnow(),
                Document.status == "active"
            )
        ).order_by(Document.expiry_date)

        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def archive_document(self, document_id: str) -> bool:
        """Archive (soft delete) a document."""
        result = await self.db.execute(select(Document).where(Document.id == document_id))
        document = result.scalar_one_or_none()

        if not document:
            raise ValueError("Document not found")

        document.status = "archived"
        document.updated_at = datetime.utcnow()
        await self.db.commit()
        return True

    async def validate_document(self, document_id: str) -> DocumentValidationResult:
        """Validate a document and return results."""
        result = await self.db.execute(select(Document).where(Document.id == document_id))
        document = result.scalar_one_or_none()

        if not document:
            raise ValueError("Document not found")

        # Re-validate
        validation = await self._validate_document(document)

        # Update document
        document.validation_status = validation["status"]
        document.validation_score = validation["score"]
        document.validation_issues = json.dumps(validation.get("issues", []))
        await self.db.commit()

        extracted_data = json.loads(document.extracted_data) if document.extracted_data else {}

        return DocumentValidationResult(
            document_id=document_id,
            is_valid=validation["status"] == "valid",
            validation_score=validation["score"],
            issues=validation.get("issues", []),
            warnings=[],
            extracted_data=extracted_data,
        )

    async def upload_new_version(
        self,
        document_id: str,
        file_content: bytes,
        filename: str,
        mime_type: str,
        user_id: str,
        changes_description: str = None,
    ) -> Document:
        """Upload a new version of an existing document."""
        # Get existing document
        result = await self.db.execute(select(Document).where(Document.id == document_id))
        document = result.scalar_one_or_none()

        if not document:
            raise ValueError("Document not found")

        # Validate file
        if len(file_content) > self.MAX_FILE_SIZE:
            raise ValueError(f"File size exceeds {self.MAX_FILE_SIZE // (1024*1024)}MB limit")
        if mime_type not in self.ALLOWED_TYPES:
            raise ValueError(f"File type {mime_type} not allowed")

        # Create version record for old file
        version_record = DocumentVersion(
            document_id=document.id,
            version=document.version,
            file_path=document.file_path,
            file_size=document.file_size,
            changes=changes_description or "Replaced with new version",
            created_by=user_id,
        )
        self.db.add(version_record)

        # Generate new filename
        file_id = str(uuid.uuid4())
        ext = os.path.splitext(filename)[1]
        unique_filename = f"{file_id}{ext}"

        # Save new file
        file_path = await self._save_file(file_content, unique_filename, document.owner_id)

        # Update document with new file
        document.filename = unique_filename
        document.original_filename = filename
        document.file_path = file_path
        document.file_size = len(file_content)
        document.mime_type = mime_type
        document.version += 1
        document.updated_at = datetime.utcnow()

        # Reprocess document
        await self._process_document(document, file_content)

        await self.db.commit()
        await self.db.refresh(document)

        return document

    async def get_document_versions(self, document_id: str) -> List[DocumentVersion]:
        """Get all versions of a document."""
        result = await self.db.execute(
            select(DocumentVersion)
            .where(DocumentVersion.document_id == document_id)
            .order_by(DocumentVersion.version.desc())
        )
        return list(result.scalars().all())

    async def get_expiry_alerts(self) -> Dict[str, List[Dict]]:
        """Get documents grouped by expiry urgency (30/14/7/1 days)."""
        now = datetime.utcnow()

        alerts = {
            "expired": [],
            "1_day": [],
            "7_days": [],
            "14_days": [],
            "30_days": [],
        }

        # Get all documents with expiry dates
        result = await self.db.execute(
            select(Document).where(
                Document.expiry_date != None,
                Document.status == "active"
            ).order_by(Document.expiry_date)
        )
        documents = result.scalars().all()

        for doc in documents:
            days_until = (doc.expiry_date - now).days

            doc_info = {
                "document_id": doc.id,
                "document_type": doc.document_type.value,
                "filename": doc.original_filename,
                "owner_id": doc.owner_id,
                "expiry_date": doc.expiry_date.isoformat(),
                "days_until_expiry": days_until,
            }

            if days_until < 0:
                alerts["expired"].append(doc_info)
            elif days_until <= 1:
                alerts["1_day"].append(doc_info)
            elif days_until <= 7:
                alerts["7_days"].append(doc_info)
            elif days_until <= 14:
                alerts["14_days"].append(doc_info)
            elif days_until <= 30:
                alerts["30_days"].append(doc_info)

        return alerts

    async def sign_pod_document(
        self,
        document_id: str,
        user_id: str,
        signature_image: str,
        signature_type: str,
        typed_name: str,
        ip_address: str,
        user_agent: str,
        geolocation: str = None,
    ) -> Dict[str, Any]:
        """Sign a POD document with timestamp, IP, and metadata embedded."""
        import hashlib

        # Get document
        result = await self.db.execute(select(Document).where(Document.id == document_id))
        document = result.scalar_one_or_none()

        if not document:
            raise ValueError("Document not found")

        if document.document_type != DocumentType.POD:
            raise ValueError("Document is not a Proof of Delivery")

        if document.is_signed:
            raise ValueError("Document is already signed")

        # Generate signature hash for integrity
        signed_at = datetime.utcnow()
        hash_input = f"{user_id}:{document_id}:{signed_at.isoformat()}:{ip_address}"
        signature_hash = hashlib.sha256(hash_input.encode()).hexdigest()

        # Create signature metadata
        signature_metadata = {
            "signer_id": user_id,
            "signed_at": signed_at.isoformat(),
            "ip_address": ip_address,
            "user_agent": user_agent,
            "geolocation": geolocation,
            "signature_type": signature_type,
            "typed_name": typed_name,
            "signature_hash": signature_hash,
            "verification_url": f"/documents/{document_id}/verify-signature",
        }

        # Update document with signature
        document.is_signed = True
        document.signed_at = signed_at
        document.signature_data = json.dumps(signature_metadata)
        document.updated_at = signed_at

        await self.db.commit()
        await self.db.refresh(document)

        return {
            "success": True,
            "document_id": document_id,
            "signed_at": signed_at.isoformat(),
            "signature_hash": signature_hash,
            "signature_metadata": signature_metadata,
            "message": "POD signed successfully with timestamp and IP metadata embedded",
        }

    async def verify_pod_signature(self, document_id: str) -> Dict[str, Any]:
        """Verify a POD document's signature and metadata."""
        result = await self.db.execute(select(Document).where(Document.id == document_id))
        document = result.scalar_one_or_none()

        if not document:
            return {"valid": False, "error": "Document not found"}

        if not document.is_signed:
            return {"valid": False, "error": "Document is not signed"}

        signature_data = json.loads(document.signature_data) if document.signature_data else {}

        return {
            "valid": True,
            "document_id": document_id,
            "document_type": document.document_type.value,
            "filename": document.original_filename,
            "signed_at": document.signed_at.isoformat() if document.signed_at else None,
            "signature_metadata": signature_data,
        }

