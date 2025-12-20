"""Onboarding router for onboarding status and coach endpoints."""
from fastapi import APIRouter, Depends, HTTPException, status, Body
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Dict, Any, List
from pydantic import BaseModel
import json

from ..core.database import get_db
from ..core.security import get_current_active_user
from ..models.user import User
from ..services.onboarding_service import OnboardingService


class OnboardingDataRequest(BaseModel):
    """Request model for onboarding data."""
    role: str
    data: Dict[str, Any]


class ChatbotAccountCreationRequest(BaseModel):
    """Request model for creating account from chatbot data."""
    role: str
    collected_data: Dict[str, Any]
    document_ids: List[str] = []
    compliance_score: float = 0.0


router = APIRouter(prefix="/onboarding", tags=["onboarding"])


@router.get("/status")
async def get_onboarding_status(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """Get current user's onboarding status."""
    service = OnboardingService(db)
    return await service.get_onboarding_status(current_user.id)


@router.get("/coach-status")
async def get_coach_status(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """Get AI coach status and recommendations for onboarding."""
    service = OnboardingService(db)
    status = await service.get_coach_status(current_user.id)
    
    # Transform to match frontend expected format
    progress = status.get("progress", 0)
    
    # Determine status color based on progress
    if progress >= 80:
        status_color = "Green"
    elif progress >= 50:
        status_color = "Amber"
    else:
        status_color = "Red"
    
    # Get next best actions from incomplete steps
    next_best_actions = []
    for step in status.get("steps", []):
        if not step.get("completed"):
            next_best_actions.append(step.get("description", step.get("title", "Complete step")))
    
    if not next_best_actions:
        next_best_actions = ["All onboarding steps complete!"]
    
    # Get FMCSA status
    fmcsa_status = "N/A"
    for step in status.get("steps", []):
        if step.get("id") == "fmcsa":
            fmcsa_status = "Verified" if step.get("completed") else "Pending"
            break
    
    return {
        "status_color": status_color,
        "total_score": int(progress),
        "next_best_actions": next_best_actions[:3],  # Limit to 3 actions
        "fmcsa_status": fmcsa_status,
        "progress": progress,
        "is_complete": status.get("is_complete", False),
        "current_step": status.get("current_step"),
        "steps": status.get("steps", []),
        "coach_messages": status.get("coach_messages", [])
    }


@router.get("/data")
async def get_onboarding_data(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """Get current user's onboarding profile data including DOT/MC numbers."""
    return {
        "data": {
            "email": current_user.email,
            "fullName": current_user.full_name or current_user.name,
            "companyName": current_user.company_name or "",
            "dotNumber": current_user.dot_number or "",
            "mcNumber": current_user.mc_number or "",
            "role": current_user.role.value if current_user.role else "carrier",
            "firstName": current_user.first_name or "",
            "lastName": current_user.last_name or "",
            "phone": current_user.phone or "",
            "onboardingCompleted": current_user.onboarding_completed,
            "onboardingStep": current_user.onboarding_step or "WELCOME",
        }
    }


@router.post("/save")
async def save_onboarding_data(
    payload: OnboardingDataRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """Save onboarding data and mark onboarding as complete."""
    try:
        # Get current user from database to update
        result = await db.execute(select(User).where(User.id == current_user.id))
        user = result.scalar_one_or_none()
        
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Extract data from payload
        data = payload.data
        
        # Update user profile with onboarding data
        if data.get("companyName"):
            user.company_name = data["companyName"]
        if data.get("dotNumber"):
            user.dot_number = data["dotNumber"]
        if data.get("mcNumber"):
            user.mc_number = data["mcNumber"]
        if data.get("contactEmail"):
            # Keep original email, but store contact email if different
            pass
        if data.get("contactPhone"):
            user.phone = data["contactPhone"]
        if data.get("ownerName"):
            user.full_name = data["ownerName"]
        if data.get("ownerTitle"):
            # Store in onboarding_data JSON
            pass
        
        # Store complete onboarding data as JSON
        user.onboarding_data = json.dumps(data)
        
        # Mark onboarding as complete
        user.onboarding_completed = True
        user.onboarding_step = "COMPLETED"
        
        await db.commit()
        
        return {
            "success": True,
            "message": "Onboarding completed successfully",
            "user_id": user.id,
            "redirect_url": "/carrier-dashboard"
        }
    except HTTPException:
        await db.rollback()
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to save onboarding data: {str(e)}")


@router.post("/create-from-chatbot")
async def create_account_from_chatbot(
    payload: ChatbotAccountCreationRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """Create account directly from chatbot data (quick path)."""
    try:
        # Get current user from database to update
        result = await db.execute(select(User).where(User.id == current_user.id))
        user = result.scalar_one_or_none()
        
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Extract data from chatbot collected_data
        data = payload.collected_data
        
        # Update user profile with chatbot-collected data
        if data.get("dot_number"):
            user.dot_number = data["dot_number"]
        if data.get("mc_number"):
            user.mc_number = data["mc_number"]
        if data.get("company_name"):
            user.company_name = data["company_name"]
        if data.get("full_name"):
            user.full_name = data["full_name"]
        if data.get("cdl_number"):
            # Store CDL in onboarding_data JSON
            pass
        
        # Store complete chatbot data as JSON
        user.onboarding_data = json.dumps({
            "from_chatbot": True,
            "collected_data": data,
            "document_ids": payload.document_ids,
            "compliance_score": payload.compliance_score,
        })
        
        # Mark onboarding as complete with compliance score
        user.onboarding_completed = True
        user.onboarding_step = "COMPLETED"
        user.onboarding_score = int(payload.compliance_score)
        
        await db.commit()
        
        return {
            "success": True,
            "message": "Account created successfully from chatbot data",
            "user_id": user.id,
            "redirect_url": "/carrier-dashboard"
        }
    except HTTPException:
        await db.rollback()
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to create account: {str(e)}")



