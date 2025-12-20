"""Consent and E-Signature API routes."""
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.database import get_db
from ..core.security import get_current_user, get_current_active_user, require_roles
from ..models.user import User, UserRole
from ..models.consent import ConsentType
from ..schemas.consent import (
    ConsentCreate, ConsentResponse, ConsentListResponse,
    ESignatureCreate, ESignatureResponse, UserConsentStatus
)
from ..services.consent_service import ConsentService


router = APIRouter(prefix="/consents", tags=["Consents"])


@router.get("", response_model=ConsentListResponse)
async def list_consents(
    consent_type: Optional[str] = None,
    is_active: bool = True,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """List available consent forms."""
    consent_service = ConsentService(db)
    
    c_type = None
    if consent_type:
        try:
            c_type = ConsentType(consent_type)
        except ValueError:
            pass
    
    consents, total = await consent_service.list_consents(
        consent_type=c_type,
        is_active=is_active,
        role=current_user.role.value,
        page=page,
        page_size=page_size,
    )
    
    return ConsentListResponse(
        consents=consents,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/required")
async def get_required_consents(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Get required consents for current user's role."""
    consent_service = ConsentService(db)
    
    consents = await consent_service.get_required_consents_for_role(current_user.role.value)
    return {"consents": consents}


@router.get("/status", response_model=UserConsentStatus)
async def get_my_consent_status(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Get current user's consent status."""
    consent_service = ConsentService(db)
    
    status = await consent_service.get_user_consent_status(current_user.id, current_user.role.value)
    return status


@router.get("/{consent_id}", response_model=ConsentResponse)
async def get_consent(
    consent_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Get consent form by ID."""
    consent_service = ConsentService(db)
    
    consent = await consent_service.get_consent(consent_id)
    if not consent:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Consent not found")
    
    return consent


@router.post("/sign", response_model=ESignatureResponse, status_code=status.HTTP_201_CREATED)
async def sign_consent(
    data: ESignatureCreate,
    request: Request,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Sign a consent form."""
    consent_service = ConsentService(db)
    
    try:
        signature = await consent_service.sign_consent(
            user_id=current_user.id,
            data=data,
            ip_address=request.client.host,
            user_agent=request.headers.get("user-agent"),
        )
        return signature
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/signatures/my", response_model=List[ESignatureResponse])
async def get_my_signatures(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Get current user's signatures."""
    consent_service = ConsentService(db)
    
    signatures = await consent_service.get_user_signatures(current_user.id)
    return signatures


@router.get("/signatures/{signature_id}/verify")
async def verify_signature(
    signature_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Verify a signature's authenticity."""
    consent_service = ConsentService(db)
    
    result = await consent_service.verify_signature(signature_id)
    return result


# Admin endpoints
@router.post("", response_model=ConsentResponse, status_code=status.HTTP_201_CREATED)
async def create_consent(
    data: ConsentCreate,
    current_user: User = Depends(require_roles([UserRole.ADMIN, UserRole.SUPER_ADMIN])),
    db: AsyncSession = Depends(get_db)
):
    """Create a new consent form (admin only)."""
    consent_service = ConsentService(db)

    try:
        consent = await consent_service.create_consent(data)
        return consent
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/admin/override")
async def admin_override_consent(
    user_id: str,
    consent_id: str,
    reason: str,
    request: Request,
    current_user: User = Depends(require_roles([UserRole.ADMIN, UserRole.SUPER_ADMIN])),
    db: AsyncSession = Depends(get_db)
):
    """Admin override to grant consent on behalf of user (requires reason, logged)."""
    if not reason or len(reason.strip()) < 10:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Override reason must be at least 10 characters"
        )

    consent_service = ConsentService(db)

    try:
        result = await consent_service.admin_override_consent(
            user_id=user_id,
            consent_id=consent_id,
            admin_id=current_user.id,
            reason=reason.strip(),
            ip_address=request.client.host,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/marketplace-eligibility")
async def check_marketplace_eligibility(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Check if user has signed all consents required for marketplace access."""
    consent_service = ConsentService(db)

    result = await consent_service.check_marketplace_consent_eligibility(
        user_id=current_user.id,
        role=current_user.role.value
    )
    return result


@router.get("/matrix/{role}")
async def get_consent_matrix(
    role: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Get consent matrix showing data visibility rules based on signed consents."""
    consent_service = ConsentService(db)

    result = await consent_service.get_consent_matrix(role)
    return result

