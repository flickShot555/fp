"""AI Assistant API routes."""
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from ..core.database import get_db
from ..core.security import get_current_user, get_current_active_user
from ..models.user import User
from ..services.ai_service import AIService
from ..services.compliance_service import ComplianceService
from ..services.onboarding_service import OnboardingService


router = APIRouter(prefix="/ai", tags=["AI Assistant"])


class ChatMessage(BaseModel):
    role: str  # "user" or "assistant"
    content: str


class ChatRequest(BaseModel):
    messages: List[ChatMessage]
    context: Optional[str] = None


class ChatResponse(BaseModel):
    response: str
    suggestions: Optional[List[str]] = None


@router.post("/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Chat with AI assistant."""
    ai_service = AIService()
    
    # Build system prompt based on user role and context
    system_prompt = f"""You are FreightPower AI Assistant, helping users with freight logistics.
    
User Role: {current_user.role.value}
User Name: {current_user.first_name or 'User'}

You help with:
- Onboarding and compliance questions
- Document requirements and uploads
- Load management and marketplace
- FMCSA regulations and requirements
- General freight industry questions

Be helpful, concise, and professional. If you don't know something, say so.
Never fabricate compliance data or make up regulations."""

    if request.context:
        system_prompt += f"\n\nContext: {request.context}"
    
    # Convert messages to dict format
    messages = [{"role": m.role, "content": m.content} for m in request.messages]
    
    try:
        response = await ai_service.chat_completion(
            messages=messages,
            system_prompt=system_prompt,
            temperature=0.7,
        )
        
        return ChatResponse(
            response=response,
            suggestions=None,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"AI service error: {str(e)}"
        )


@router.post("/chat/onboarding", response_model=ChatResponse)
async def onboarding_chat(
    request: ChatRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Chat with AI assistant for onboarding help."""
    ai_service = AIService()
    onboarding_service = OnboardingService(db)
    
    # Get onboarding status for context
    status = await onboarding_service.get_onboarding_status(current_user.id)
    
    system_prompt = f"""You are FreightPower AI Onboarding Coach.

User Role: {current_user.role.value}
Onboarding Progress: {status.get('progress', 0)}%
Current Step: {status.get('current_step', 'unknown')}
Completed Steps: {', '.join(status.get('completed_steps', []))}

Help the user complete their onboarding. Guide them through:
1. Profile completion
2. Document uploads (CDL, MC Certificate, COI, W9, etc.)
3. FMCSA verification
4. Consent forms
5. Payment setup

Be encouraging and provide specific next steps."""

    messages = [{"role": m.role, "content": m.content} for m in request.messages]
    
    try:
        response = await ai_service.chat_completion(
            messages=messages,
            system_prompt=system_prompt,
            temperature=0.7,
        )
        
        # Generate suggestions based on current step
        suggestions = []
        current_step = status.get('current_step')
        if current_step == 'documents':
            suggestions = ["What documents do I need?", "How do I upload a document?", "What is a COI?"]
        elif current_step == 'fmcsa':
            suggestions = ["What is FMCSA verification?", "Where do I find my MC number?", "How long does verification take?"]
        elif current_step == 'consents':
            suggestions = ["What agreements do I need to sign?", "Is my signature legally binding?"]
        
        return ChatResponse(
            response=response,
            suggestions=suggestions,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"AI service error: {str(e)}"
        )


@router.get("/recommendations")
async def get_recommendations(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Get AI-powered recommendations for the user."""
    compliance_service = ComplianceService(db)
    
    # Get compliance status and next actions
    compliance = await compliance_service.check_user_compliance(current_user.id)
    actions = await compliance_service.get_next_best_actions(current_user.id)
    
    return {
        "compliance_score": compliance.get("score", 0),
        "is_compliant": compliance.get("is_compliant", False),
        "recommendations": actions,
        "issues": compliance.get("issues", []),
        "warnings": compliance.get("warnings", []),
    }


@router.get("/document-help/{document_type}")
async def get_document_help(
    document_type: str,
    current_user: User = Depends(get_current_active_user),
):
    """Get AI help for a specific document type."""
    document_info = {
        "cdl": {
            "name": "Commercial Driver's License",
            "description": "Your CDL is required to operate commercial vehicles.",
            "requirements": ["Must be valid and not expired", "Must match your CDL class", "Must show endorsements"],
            "tips": ["Take a clear photo of the front", "Ensure all text is readable", "Include expiration date"],
        },
        "mc_certificate": {
            "name": "Motor Carrier Authority Certificate",
            "description": "Your MC Certificate proves your authority to operate as a carrier.",
            "requirements": ["Must be active", "Must match your company name", "Must show MC number"],
            "tips": ["Download from FMCSA portal", "Ensure it shows 'AUTHORIZED'"],
        },
        "coi": {
            "name": "Certificate of Insurance",
            "description": "Proof of your liability and cargo insurance coverage.",
            "requirements": ["Must be current", "Must meet minimum coverage requirements", "Must list your company"],
            "tips": ["Request from your insurance provider", "Ensure coverage amounts are visible"],
        },
        "w9": {
            "name": "W-9 Tax Form",
            "description": "IRS form for tax identification purposes.",
            "requirements": ["Must be signed", "Must have correct EIN/SSN", "Must be current year"],
            "tips": ["Download blank form from IRS.gov", "Sign and date before uploading"],
        },
        "medical_card": {
            "name": "DOT Medical Card",
            "description": "Proof of medical fitness to operate commercial vehicles.",
            "requirements": ["Must be valid", "Must be from certified medical examiner"],
            "tips": ["Renew before expiration", "Keep a copy in your vehicle"],
        },
    }
    
    info = document_info.get(document_type, {
        "name": document_type.replace("_", " ").title(),
        "description": "Upload this document to complete your profile.",
        "requirements": ["Must be valid", "Must be readable"],
        "tips": ["Take a clear photo or scan"],
    })
    
    return info

