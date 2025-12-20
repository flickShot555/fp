"""Compliance service for rules engine and scoring."""
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import json

from ..models.carrier import Carrier
from ..models.driver import Driver
from ..models.document import Document, DocumentType
from ..models.user import User, UserRole


class ComplianceService:
    """Service for compliance checking and scoring."""
    
    # Document requirements by role
    REQUIRED_DOCUMENTS = {
        UserRole.CARRIER: [
            DocumentType.MC_CERTIFICATE,
            DocumentType.COI,
            DocumentType.W9,
            DocumentType.AUTHORITY,
        ],
        UserRole.DRIVER: [
            DocumentType.CDL,
            DocumentType.MEDICAL_CARD,
            DocumentType.MVR,
            DocumentType.DRUG_TEST,
            DocumentType.CLEARINGHOUSE_CONSENT,
        ],
    }
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def check_user_compliance(self, user_id: str) -> Dict[str, Any]:
        """Check compliance status for a user."""
        # Get user
        result = await self.db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        
        if not user:
            return {"error": "User not found"}
        
        # Get required documents for role
        required_docs = self.REQUIRED_DOCUMENTS.get(user.role, [])
        
        # Get user's documents
        doc_result = await self.db.execute(
            select(Document).where(
                Document.owner_id == user_id,
                Document.status == "active"
            )
        )
        documents = list(doc_result.scalars().all())
        
        # Check each requirement
        checks = {}
        issues = []
        warnings = []
        
        for doc_type in required_docs:
            doc = next((d for d in documents if d.document_type == doc_type), None)
            
            if not doc:
                checks[doc_type.value] = False
                issues.append(f"Missing {doc_type.value} document")
            elif doc.validation_status != "valid":
                checks[doc_type.value] = False
                issues.append(f"{doc_type.value} document not validated")
            elif doc.expiry_date and doc.expiry_date < datetime.utcnow():
                checks[doc_type.value] = False
                issues.append(f"{doc_type.value} document has expired")
            elif doc.expiry_date and doc.expiry_date < datetime.utcnow() + timedelta(days=30):
                checks[doc_type.value] = True
                warnings.append(f"{doc_type.value} document expires soon")
            else:
                checks[doc_type.value] = True
        
        # Calculate score
        if len(checks) > 0:
            score = (sum(checks.values()) / len(checks)) * 100
        else:
            score = 100.0
        
        return {
            "user_id": user_id,
            "role": user.role.value,
            "is_compliant": len(issues) == 0,
            "score": score,
            "checks": checks,
            "issues": issues,
            "warnings": warnings,
            "required_documents": [d.value for d in required_docs],
            "last_checked": datetime.utcnow(),
        }
    
    async def check_carrier_compliance(self, carrier_id: str) -> Dict[str, Any]:
        """Check compliance status for a carrier."""
        # Get carrier
        result = await self.db.execute(select(Carrier).where(Carrier.id == carrier_id))
        carrier = result.scalar_one_or_none()
        
        if not carrier:
            return {"error": "Carrier not found"}
        
        issues = []
        checks = {}
        
        # FMCSA verification
        checks["fmcsa_verified"] = carrier.fmcsa_verified
        if not carrier.fmcsa_verified:
            issues.append("FMCSA verification required")
        
        # Insurance
        checks["insurance_valid"] = (
            carrier.insurance_status == "active" and
            carrier.insurance_expiry and
            carrier.insurance_expiry > datetime.utcnow()
        )
        if not checks["insurance_valid"]:
            issues.append("Insurance not valid or expired")
        
        # Company documents
        doc_result = await self.db.execute(
            select(Document).where(
                Document.company_id == carrier.company_id,
                Document.status == "active"
            )
        )
        documents = list(doc_result.scalars().all())
        
        for doc_type in self.REQUIRED_DOCUMENTS[UserRole.CARRIER]:
            doc = next((d for d in documents if d.document_type == doc_type), None)
            key = f"document_{doc_type.value}"
            
            if doc and doc.validation_status == "valid":
                if doc.expiry_date and doc.expiry_date < datetime.utcnow():
                    checks[key] = False
                    issues.append(f"{doc_type.value} expired")
                else:
                    checks[key] = True
            else:
                checks[key] = False
                issues.append(f"{doc_type.value} missing or invalid")
        
        score = (sum(checks.values()) / len(checks)) * 100 if checks else 0
        
        # Update carrier compliance score
        carrier.compliance_score = score
        carrier.compliance_status = "compliant" if score >= 80 else "non_compliant"
        carrier.last_compliance_check = datetime.utcnow()
        await self.db.commit()
        
        return {
            "carrier_id": carrier_id,
            "is_compliant": score >= 80,
            "score": score,
            "checks": checks,
            "issues": issues,
            "last_checked": datetime.utcnow(),
        }
    
    async def get_expiring_documents_report(self, days: int = 30) -> List[Dict[str, Any]]:
        """Get report of documents expiring within specified days."""
        expiry_date = datetime.utcnow() + timedelta(days=days)
        
        result = await self.db.execute(
            select(Document).where(
                Document.expiry_date != None,
                Document.expiry_date <= expiry_date,
                Document.expiry_date >= datetime.utcnow(),
                Document.status == "active"
            ).order_by(Document.expiry_date)
        )
        
        documents = result.scalars().all()
        
        report = []
        for doc in documents:
            days_until = (doc.expiry_date - datetime.utcnow()).days
            report.append({
                "document_id": doc.id,
                "document_type": doc.document_type.value,
                "filename": doc.original_filename,
                "owner_id": doc.owner_id,
                "expiry_date": doc.expiry_date,
                "days_until_expiry": days_until,
                "severity": "critical" if days_until <= 7 else "warning" if days_until <= 14 else "info",
            })
        
        return report
    
    async def get_next_best_actions(self, user_id: str) -> List[Dict[str, Any]]:
        """Get prioritized list of actions for compliance."""
        compliance = await self.check_user_compliance(user_id)
        
        actions = []
        
        for issue in compliance.get("issues", []):
            if "Missing" in issue:
                doc_type = issue.replace("Missing ", "").replace(" document", "")
                actions.append({
                    "priority": "high",
                    "action": "upload",
                    "title": f"Upload {doc_type}",
                    "description": f"Please upload your {doc_type} document to complete your profile.",
                    "category": "document",
                })
            elif "expired" in issue.lower():
                doc_type = issue.split(" ")[0]
                actions.append({
                    "priority": "critical",
                    "action": "renew",
                    "title": f"Renew {doc_type}",
                    "description": f"Your {doc_type} has expired. Please upload a new version.",
                    "category": "document",
                })
        
        return sorted(actions, key=lambda x: {"critical": 0, "high": 1, "medium": 2, "low": 3}.get(x["priority"], 4))

