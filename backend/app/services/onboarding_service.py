"""Onboarding service for role-specific onboarding flows."""
from datetime import datetime
from typing import Optional, Dict, Any, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import json

from ..models.user import User, UserRole
from ..models.document import Document, DocumentType
from ..models.consent import ESignature
from ..models.carrier import Carrier
from ..models.driver import Driver
from ..models.company import Company


class OnboardingService:
    """Service for managing onboarding flows."""
    
    # Onboarding steps by role
    ONBOARDING_STEPS = {
        UserRole.CARRIER: [
            {"id": "profile", "title": "Complete Profile", "description": "Fill in your company information"},
            {"id": "fmcsa", "title": "FMCSA Verification", "description": "Verify your MC/USDOT number"},
            {"id": "documents", "title": "Upload Documents", "description": "Upload required documents (MC Certificate, COI, W9)"},
            {"id": "consents", "title": "Sign Agreements", "description": "Review and sign required agreements"},
            {"id": "payment", "title": "Payment Setup", "description": "Set up payment information"},
        ],
        UserRole.DRIVER: [
            {"id": "profile", "title": "Complete Profile", "description": "Fill in your personal information"},
            {"id": "cdl", "title": "CDL Verification", "description": "Upload and verify your CDL"},
            {"id": "medical", "title": "Medical Card", "description": "Upload your DOT medical card"},
            {"id": "documents", "title": "Additional Documents", "description": "Upload MVR and other required documents"},
            {"id": "consents", "title": "Sign Agreements", "description": "Review and sign required agreements"},
        ],
        UserRole.SHIPPER: [
            {"id": "profile", "title": "Complete Profile", "description": "Fill in your company information"},
            {"id": "documents", "title": "Upload Documents", "description": "Upload W9 and other documents"},
            {"id": "consents", "title": "Sign Agreements", "description": "Review and sign required agreements"},
            {"id": "preferences", "title": "Set Preferences", "description": "Configure your shipping preferences"},
        ],
    }
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def get_onboarding_status(self, user_id: str) -> Dict[str, Any]:
        """Get current onboarding status for user."""
        # Get user
        result = await self.db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        
        if not user:
            return {"error": "User not found"}
        
        steps = self.ONBOARDING_STEPS.get(user.role, [])
        completed_steps = []
        current_step = None
        
        for step in steps:
            is_complete = await self._check_step_complete(user, step["id"])
            step_status = {**step, "completed": is_complete}
            
            if is_complete:
                completed_steps.append(step["id"])
            elif current_step is None:
                current_step = step["id"]
            
            step["completed"] = is_complete
        
        progress = (len(completed_steps) / len(steps)) * 100 if steps else 100
        
        return {
            "user_id": user_id,
            "role": user.role.value,
            "is_complete": len(completed_steps) == len(steps),
            "progress": progress,
            "current_step": current_step,
            "completed_steps": completed_steps,
            "steps": steps,
            "next_action": await self._get_next_action(user, current_step),
        }
    
    async def _check_step_complete(self, user: User, step_id: str) -> bool:
        """Check if a specific onboarding step is complete."""
        if step_id == "profile":
            return user.first_name and user.last_name and user.email_verified
        
        elif step_id == "fmcsa":
            if user.role == UserRole.CARRIER:
                # Find carrier through user's company_id
                if user.company_id:
                    carrier = await self.db.execute(
                        select(Carrier).where(Carrier.company_id == user.company_id)
                    )
                    carrier = carrier.scalar_one_or_none()
                    return carrier and carrier.fmcsa_verified
                return False
            return True
        
        elif step_id == "cdl":
            if user.role == UserRole.DRIVER:
                driver = await self.db.execute(select(Driver).where(Driver.user_id == user.id))
                driver = driver.scalar_one_or_none()
                return driver and driver.cdl_verified
            return True
        
        elif step_id == "medical":
            if user.role == UserRole.DRIVER:
                driver = await self.db.execute(select(Driver).where(Driver.user_id == user.id))
                driver = driver.scalar_one_or_none()
                return driver and driver.medical_card_verified
            return True
        
        elif step_id == "documents":
            required_docs = self._get_required_documents(user.role)
            docs = await self.db.execute(
                select(Document).where(
                    Document.owner_id == user.id,
                    Document.status == "active",
                    Document.validation_status == "valid"
                )
            )
            docs = list(docs.scalars().all())
            doc_types = {d.document_type for d in docs}
            return all(dt in doc_types for dt in required_docs)
        
        elif step_id == "consents":
            signatures = await self.db.execute(
                select(ESignature).where(ESignature.user_id == user.id)
            )
            return len(list(signatures.scalars().all())) > 0
        
        elif step_id == "payment":
            # Check if payment method is set up
            return user.payment_method_id is not None if hasattr(user, 'payment_method_id') else False
        
        elif step_id == "preferences":
            return True  # Preferences are optional
        
        return False
    
    def _get_required_documents(self, role: UserRole) -> List[DocumentType]:
        """Get required documents for role."""
        if role == UserRole.CARRIER:
            return [DocumentType.MC_CERTIFICATE, DocumentType.COI, DocumentType.W9]
        elif role == UserRole.DRIVER:
            return [DocumentType.CDL, DocumentType.MEDICAL_CARD]
        elif role == UserRole.SHIPPER:
            return [DocumentType.W9]
        return []
    
    async def _get_next_action(self, user: User, current_step: str) -> Dict[str, Any]:
        """Get the next action for the user to complete."""
        if not current_step:
            return {"action": "complete", "message": "Onboarding complete!"}
        
        actions = {
            "profile": {"action": "navigate", "path": "/settings/profile", "message": "Complete your profile"},
            "fmcsa": {"action": "navigate", "path": "/onboarding/fmcsa", "message": "Verify your FMCSA credentials"},
            "cdl": {"action": "navigate", "path": "/documents/upload?type=cdl", "message": "Upload your CDL"},
            "medical": {"action": "navigate", "path": "/documents/upload?type=medical_card", "message": "Upload your medical card"},
            "documents": {"action": "navigate", "path": "/documents", "message": "Upload required documents"},
            "consents": {"action": "navigate", "path": "/consents", "message": "Review and sign agreements"},
            "payment": {"action": "navigate", "path": "/settings/payment", "message": "Set up payment method"},
            "preferences": {"action": "navigate", "path": "/settings/preferences", "message": "Configure preferences"},
        }
        
        return actions.get(current_step, {"action": "unknown", "message": "Continue onboarding"})
    
    async def get_coach_status(self, user_id: str) -> Dict[str, Any]:
        """Get AI coach status and recommendations."""
        status = await self.get_onboarding_status(user_id)
        
        if status.get("error"):
            return status
        
        # Generate coaching messages
        messages = []
        
        if not status["is_complete"]:
            current = status["current_step"]
            progress = status["progress"]
            
            if progress < 25:
                messages.append({
                    "type": "welcome",
                    "message": "Welcome to FreightPower AI! Let's get you set up.",
                })
            elif progress < 50:
                messages.append({
                    "type": "encouragement",
                    "message": "Great progress! You're almost halfway there.",
                })
            elif progress < 75:
                messages.append({
                    "type": "encouragement",
                    "message": "You're doing great! Just a few more steps.",
                })
            else:
                messages.append({
                    "type": "almost_done",
                    "message": "Almost there! Complete the final steps to finish.",
                })
        else:
            messages.append({
                "type": "complete",
                "message": "Congratulations! Your onboarding is complete.",
            })
        
        return {
            **status,
            "coach_messages": messages,
        }

