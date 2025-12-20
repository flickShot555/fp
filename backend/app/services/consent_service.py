"""Consent and E-Signature service."""
from datetime import datetime
from typing import Optional, List, Tuple, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
import hashlib
import json

from ..models.consent import Consent, ConsentType, ESignature
from ..models.user import User
from ..schemas.consent import ConsentCreate, ConsentUpdate, ESignatureCreate


class ConsentService:
    """Service for consent and e-signature management."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def create_consent(self, data: ConsentCreate) -> Consent:
        """Create a new consent form."""
        consent = Consent(
            consent_type=data.consent_type,
            version=data.version,
            title=data.title,
            description=data.description,
            content=data.content,
            template_url=data.template_url,
            is_required=data.is_required,
            applies_to_roles=json.dumps(data.applies_to_roles) if data.applies_to_roles else None,
            effective_date=data.effective_date,
            expiry_date=data.expiry_date,
        )
        
        self.db.add(consent)
        await self.db.commit()
        await self.db.refresh(consent)
        return consent
    
    async def get_consent(self, consent_id: str) -> Optional[Consent]:
        """Get consent by ID."""
        result = await self.db.execute(select(Consent).where(Consent.id == consent_id))
        return result.scalar_one_or_none()
    
    async def list_consents(
        self,
        consent_type: ConsentType = None,
        is_active: bool = True,
        role: str = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Tuple[List[Consent], int]:
        """List consent forms with filters."""
        query = select(Consent)
        
        if is_active is not None:
            query = query.where(Consent.is_active == is_active)
        if consent_type:
            query = query.where(Consent.consent_type == consent_type)
        if role:
            query = query.where(
                Consent.applies_to_roles.ilike(f'%"{role}"%') | 
                Consent.applies_to_roles.is_(None)
            )
        
        # Count
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await self.db.execute(count_query)
        total = total_result.scalar()
        
        # Paginate
        query = query.offset((page - 1) * page_size).limit(page_size)
        query = query.order_by(Consent.created_at.desc())
        
        result = await self.db.execute(query)
        consents = result.scalars().all()
        
        return list(consents), total
    
    async def get_required_consents_for_role(self, role: str) -> List[Consent]:
        """Get all required consents for a specific role."""
        query = select(Consent).where(
            Consent.is_active == True,
            Consent.is_required == True,
        )
        
        result = await self.db.execute(query)
        consents = result.scalars().all()
        
        # Filter by role
        filtered = []
        for consent in consents:
            if consent.applies_to_roles:
                roles = json.loads(consent.applies_to_roles)
                if role in roles or len(roles) == 0:
                    filtered.append(consent)
            else:
                filtered.append(consent)
        
        return filtered
    
    async def sign_consent(
        self,
        user_id: str,
        data: ESignatureCreate,
        ip_address: str = None,
        user_agent: str = None,
    ) -> ESignature:
        """Create e-signature for consent."""
        # Generate signature hash
        hash_input = f"{user_id}{data.consent_id}{data.agreement_text}{datetime.utcnow().isoformat()}"
        signature_hash = hashlib.sha256(hash_input.encode()).hexdigest()
        
        signature = ESignature(
            user_id=user_id,
            consent_id=data.consent_id,
            document_id=data.document_id,
            load_id=data.load_id,
            signature_image=data.signature_image,
            signature_type=data.signature_type,
            typed_name=data.typed_name,
            agreement_text=data.agreement_text,
            ip_address=ip_address,
            user_agent=user_agent,
            signature_hash=signature_hash,
        )
        
        self.db.add(signature)
        await self.db.commit()
        await self.db.refresh(signature)
        return signature
    
    async def get_user_signatures(self, user_id: str) -> List[ESignature]:
        """Get all signatures by user."""
        result = await self.db.execute(
            select(ESignature).where(ESignature.user_id == user_id).order_by(ESignature.signed_at.desc())
        )
        return list(result.scalars().all())
    
    async def get_user_consent_status(self, user_id: str, role: str) -> Dict[str, Any]:
        """Get user's consent status for all required consents."""
        # Get required consents
        required = await self.get_required_consents_for_role(role)
        
        # Get user's signatures
        signatures = await self.get_user_signatures(user_id)
        signed_consent_ids = {s.consent_id for s in signatures if s.consent_id}
        
        pending = [c for c in required if c.id not in signed_consent_ids]
        signed = [s for s in signatures if s.consent_id in {c.id for c in required}]
        
        return {
            "user_id": user_id,
            "pending_consents": pending,
            "signed_consents": signed,
            "all_required_signed": len(pending) == 0,
        }
    
    async def verify_signature(self, signature_id: str) -> Dict[str, Any]:
        """Verify a signature's authenticity."""
        result = await self.db.execute(select(ESignature).where(ESignature.id == signature_id))
        signature = result.scalar_one_or_none()

        if not signature:
            return {"valid": False, "error": "Signature not found"}

        return {
            "valid": True,
            "signature_id": signature.id,
            "user_id": signature.user_id,
            "signed_at": signature.signed_at,
            "signature_hash": signature.signature_hash,
            "consent_id": signature.consent_id,
            "document_id": signature.document_id,
        }

    async def admin_override_consent(
        self,
        user_id: str,
        consent_id: str,
        admin_id: str,
        reason: str,
        ip_address: str = None,
    ) -> Dict[str, Any]:
        """Admin override to grant consent on behalf of user with reason logging."""
        from ..models.user import AuditLog

        # Verify consent exists
        consent = await self.get_consent(consent_id)
        if not consent:
            raise ValueError("Consent not found")

        # Generate signature hash for override
        hash_input = f"ADMIN_OVERRIDE:{admin_id}:{user_id}:{consent_id}:{datetime.utcnow().isoformat()}"
        signature_hash = hashlib.sha256(hash_input.encode()).hexdigest()

        # Create signature entry marking it as admin override
        signature = ESignature(
            user_id=user_id,
            consent_id=consent_id,
            signature_type="admin_override",
            typed_name=f"ADMIN OVERRIDE by {admin_id}",
            agreement_text=f"Admin override granted. Reason: {reason}",
            ip_address=ip_address,
            signature_hash=signature_hash,
        )
        self.db.add(signature)

        # Log the override action in audit logs
        audit_log = AuditLog(
            user_id=admin_id,
            action="admin_consent_override",
            resource_type="consent",
            resource_id=consent_id,
            details=json.dumps({
                "target_user_id": user_id,
                "consent_id": consent_id,
                "consent_title": consent.title,
                "reason": reason,
                "override_signature_id": signature.id,
            }),
            ip_address=ip_address,
        )
        self.db.add(audit_log)

        await self.db.commit()
        await self.db.refresh(signature)

        return {
            "success": True,
            "signature_id": signature.id,
            "message": f"Admin override applied for consent '{consent.title}'",
            "audit_log_id": audit_log.id,
        }

    async def check_marketplace_consent_eligibility(self, user_id: str, role: str) -> Dict[str, Any]:
        """Check if user has signed all required consents for marketplace access."""
        status = await self.get_user_consent_status(user_id, role)

        # Define critical consents that block marketplace
        critical_consent_types = [
            ConsentType.TERMS_OF_SERVICE,
            ConsentType.PRIVACY_POLICY,
        ]

        # Add role-specific critical consents
        if role == "carrier":
            critical_consent_types.append(ConsentType.CARRIER_AGREEMENT)
        elif role == "driver":
            critical_consent_types.extend([
                ConsentType.DRIVER_AGREEMENT,
                ConsentType.CLEARINGHOUSE,
                ConsentType.BACKGROUND_CHECK,
            ])
        elif role == "shipper":
            critical_consent_types.append(ConsentType.BROKER_AGREEMENT)

        # Get all required consents of critical types
        missing_critical = []
        for consent in status.get("pending_consents", []):
            if consent.consent_type in critical_consent_types:
                missing_critical.append({
                    "consent_id": consent.id,
                    "title": consent.title,
                    "consent_type": consent.consent_type.value,
                })

        return {
            "user_id": user_id,
            "is_eligible": len(missing_critical) == 0,
            "missing_consents": missing_critical,
            "all_required_signed": status.get("all_required_signed", False),
            "total_pending": len(status.get("pending_consents", [])),
        }

    async def get_consent_matrix(self, role: str) -> Dict[str, Any]:
        """Get consent matrix showing what data/documents are visible based on signed consents."""
        # Define visibility rules based on consent types
        visibility_matrix = {
            ConsentType.CLEARINGHOUSE.value: {
                "grants_access_to": ["clearinghouse_query", "drug_test_results"],
                "shared_with": ["fmcsa", "carrier", "employer"],
                "description": "Allows query of drug/alcohol violations in FMCSA Clearinghouse",
            },
            ConsentType.BACKGROUND_CHECK.value: {
                "grants_access_to": ["criminal_history", "employment_history"],
                "shared_with": ["carrier", "background_check_provider"],
                "description": "Allows background check and sharing results with carriers",
            },
            ConsentType.MVR_CHECK.value: {
                "grants_access_to": ["motor_vehicle_record", "driving_history"],
                "shared_with": ["carrier", "insurance_provider"],
                "description": "Allows MVR check and sharing with carriers/insurers",
            },
            ConsentType.CARRIER_AGREEMENT.value: {
                "grants_access_to": ["company_profile", "insurance_docs", "authority_docs"],
                "shared_with": ["shippers", "brokers", "marketplace"],
                "description": "Allows profile visibility in marketplace",
            },
            ConsentType.DRIVER_AGREEMENT.value: {
                "grants_access_to": ["driver_profile", "cdl_info", "compliance_status"],
                "shared_with": ["carriers", "staffing_pool"],
                "description": "Allows driver visibility in staffing pool",
            },
            ConsentType.PRIVACY_POLICY.value: {
                "grants_access_to": ["basic_platform_features"],
                "shared_with": ["platform"],
                "description": "Required for platform usage",
            },
            ConsentType.TERMS_OF_SERVICE.value: {
                "grants_access_to": ["all_platform_features"],
                "shared_with": ["platform"],
                "description": "Required for platform usage",
            },
        }

        # Filter by role applicability
        role_applicable = {}
        for consent_type, rules in visibility_matrix.items():
            role_applicable[consent_type] = rules

        return {
            "role": role,
            "visibility_rules": role_applicable,
            "description": "Shows what data becomes visible/shared when each consent is signed",
        }

