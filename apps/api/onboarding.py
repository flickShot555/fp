# File: apps/api/onboarding.py
"""Onboarding router for manual onboarding and account creation endpoints."""
from fastapi import APIRouter, Depends, HTTPException, status
from typing import Dict, Any, List
import json
import time
from datetime import datetime, timedelta

from .auth import get_current_user
from .database import db, log_action
from .models import (
    OnboardingDataRequest, ChatbotAccountCreationRequest, OnboardingStatusResponse
)

router = APIRouter(prefix="/onboarding", tags=["Onboarding"])


def calculate_document_status(expiry_date_str: str) -> str:
    """
    Calculate document status based on expiry date.
    Returns: "Valid", "Expiring Soon", or "Expired"
    """
    try:
        if not expiry_date_str:
            return "Unknown"
        
        # Parse the expiry date (handles formats like "2026-04-03" or "2026-04-03T00:00:00Z")
        if isinstance(expiry_date_str, str):
            if 'T' in expiry_date_str:
                expiry_date = datetime.fromisoformat(expiry_date_str.replace('Z', '+00:00')).date()
            else:
                expiry_date = datetime.strptime(expiry_date_str, "%Y-%m-%d").date()
        else:
            expiry_date = expiry_date_str
        
        today = datetime.now().date()
        days_until_expiry = (expiry_date - today).days
        
        if days_until_expiry < 0:
            return "Expired"
        elif days_until_expiry <= 30:
            return "Expiring Soon"
        else:
            return "Valid"
    except Exception as e:
        print(f"Error calculating document status: {e}")
        return "Unknown"


@router.get("/status", response_model=OnboardingStatusResponse)
async def get_onboarding_status(
    user: Dict[str, Any] = Depends(get_current_user)
) -> Dict[str, Any]:
    """Get current user's onboarding status."""
    uid = user['uid']
    
    return OnboardingStatusResponse(
        onboarding_completed=user.get("onboarding_completed", False),
        onboarding_step=user.get("onboarding_step", "WELCOME"),
        onboarding_score=user.get("onboarding_score", 0),
        is_complete=user.get("onboarding_completed", False),
        current_step=user.get("onboarding_step", "WELCOME"),
        progress=user.get("onboarding_score", 0)
    )


@router.get("/coach-status")
async def get_coach_status(
    user: Dict[str, Any] = Depends(get_current_user)
) -> Dict[str, Any]:
    """Get AI coach status and recommendations for onboarding."""
    progress = user.get("onboarding_score", 0)
    
    # Determine status color based on progress
    if progress >= 80:
        status_color = "Green"
    elif progress >= 50:
        status_color = "Amber"
    else:
        status_color = "Red"
    
    # Determine FMCSA status
    fmcsa_status = "Verified" if user.get("dot_number") or user.get("mc_number") else "Pending"
    
    # Get next best actions
    next_best_actions = []
    if not user.get("dot_number") and not user.get("mc_number"):
        next_best_actions.append("Complete FMCSA verification")
    if not user.get("onboarding_completed"):
        next_best_actions.append("Complete onboarding form")
    
    if not next_best_actions:
        next_best_actions = ["All onboarding steps complete!"]
    
    return {
        "status_color": status_color,
        "total_score": int(progress),
        "next_best_actions": next_best_actions[:3],
        "fmcsa_status": fmcsa_status,
        "progress": progress,
        "is_complete": user.get("onboarding_completed", False),
        "current_step": user.get("onboarding_step", "WELCOME"),
        "coach_messages": []
    }


@router.get("/data")
async def get_onboarding_data(
    user: Dict[str, Any] = Depends(get_current_user)
) -> Dict[str, Any]:
    """Get current user's onboarding profile data including DOT/MC numbers."""
    return {
        "data": {
            "email": user.get("email"),
            "fullName": user.get("name"),
            "firstName": user.get("first_name"),
            "lastName": user.get("last_name"),
            "companyName": user.get("company_name"),
            "dotNumber": user.get("dot_number"),
            "mcNumber": user.get("mc_number"),
            "phone": user.get("phone"),
            "role": user.get("role", "carrier"),
            "onboarding_completed": user.get("onboarding_completed", False),
            "onboarding_step": user.get("onboarding_step", "WELCOME"),
            "onboarding_score": user.get("onboarding_score", 0),
        }
    }


@router.post("/save")
async def save_onboarding_data(
    payload: OnboardingDataRequest,
    user: Dict[str, Any] = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Save onboarding data with APPEND logic instead of OVERRIDE.
    This preserves previously extracted document data AND uploaded documents.
    """
    try:
        uid = user['uid']
        user_ref = db.collection("users").document(uid)
        
        # Fetch existing user data to preserve previously extracted data
        existing_user = user_ref.get().to_dict() if user_ref.get().exists else {}
        existing_onboarding_data = existing_user.get("onboarding_data")
        
        # Parse existing onboarding data if it exists
        if existing_onboarding_data and isinstance(existing_onboarding_data, str):
            try:
                existing_data = json.loads(existing_onboarding_data)
            except:
                existing_data = {}
        else:
            existing_data = {}
        
        # Extract data from new payload
        data = payload.data
        
        # APPEND logic: merge new data with existing data
        # New data fills in gaps but doesn't override previously extracted fields
        # CRITICAL: Preserve the documents array from previous uploads
        merged_data = {
            **existing_data,
            **{k: v for k, v in data.items() if v}  # Only add non-empty values
        }
        
        # IMPORTANT: If existing data had documents array, keep it
        # (Don't let new data overwrite previously uploaded documents)
        if "documents" in existing_data and "documents" not in data:
            merged_data["documents"] = existing_data["documents"]
        
        # Build update dictionary - only update non-extracted fields
        # Preserve extracted DOT/MC/Company if they were from documents
        update_data = {
            "updated_at": time.time(),
            "onboarding_completed": True,
            "onboarding_step": "COMPLETED",
            "role": payload.role,
            "is_verified": True,
            "email_verified": True,
        }
        
        # Only update fields that aren't already extracted from documents
        # If DOT/MC came from documents, they stay locked
        if data.get("companyName") and not existing_user.get("company_name"):
            update_data["company_name"] = data["companyName"]
        elif data.get("companyName"):
            # If already exists (from documents), keep the extracted value
            update_data["company_name"] = existing_user.get("company_name")
        
        if data.get("dotNumber") and not existing_user.get("dot_number"):
            update_data["dot_number"] = data["dotNumber"]
        elif existing_user.get("dot_number"):
            # Keep existing extracted DOT
            update_data["dot_number"] = existing_user.get("dot_number")
        
        if data.get("mcNumber") and not existing_user.get("mc_number"):
            update_data["mc_number"] = data["mcNumber"]
        elif existing_user.get("mc_number"):
            # Keep existing extracted MC
            update_data["mc_number"] = existing_user.get("mc_number")
        
        # These fields can be updated (not extracted from documents)
        if data.get("contactPhone"):
            update_data["phone"] = data["contactPhone"]
        if data.get("ownerName"):
            update_data["full_name"] = data["ownerName"]
        if data.get("firstName"):
            update_data["first_name"] = data["firstName"]
        if data.get("lastName"):
            update_data["last_name"] = data["lastName"]
        
        # Store merged onboarding data as JSON (both extracted and manually entered)
        # This includes documents array from previous uploads
        update_data["onboarding_data"] = json.dumps(merged_data)
        
        # Update user document
        user_ref.update(update_data)
        
        log_action(uid, "ONBOARDING_SAVE", f"Manual onboarding completed (appended to existing data) for role: {payload.role}")
        
        return {
            "success": True,
            "message": "Onboarding updated successfully (data and documents preserved)",
            "user_id": uid,
            "redirect_url": f"/{payload.role}-dashboard"
        }
    except Exception as e:
        print(f"Error saving onboarding data: {e}")
        raise HTTPException(
            status_code=500, 
            detail=f"Failed to save onboarding data: {str(e)}"
        )


@router.post("/create-from-chatbot")
async def create_account_from_chatbot(
    payload: ChatbotAccountCreationRequest,
    user: Dict[str, Any] = Depends(get_current_user)
) -> Dict[str, Any]:
    """Create account directly from chatbot data (quick path from AI Chatbot)."""
    try:
        uid = user['uid']
        user_ref = db.collection("users").document(uid)
        
        # Extract data from chatbot collected_data
        data = payload.collected_data
        
        # Build update dictionary
        update_data = {
            "updated_at": time.time(),
            "onboarding_completed": True,
            "onboarding_step": "COMPLETED",
            "role": payload.role,
            "onboarding_score": int(payload.compliance_score),
            "is_verified": True,  # Mark as verified after onboarding
            "email_verified": True,
        }
        
        # Map chatbot-collected data to user document
        if data.get("dot_number"):
            update_data["dot_number"] = data["dot_number"]
        if data.get("mc_number"):
            update_data["mc_number"] = data["mc_number"]
        if data.get("company_name"):
            update_data["company_name"] = data["company_name"]
        if data.get("full_name"):
            update_data["full_name"] = data["full_name"]
        if data.get("first_name"):
            update_data["first_name"] = data["first_name"]
        if data.get("last_name"):
            update_data["last_name"] = data["last_name"]
        if data.get("phone"):
            update_data["phone"] = data["phone"]
        
        # Store complete chatbot data as JSON (includes documents with their scores)
        # The payload includes documents array with all document info and scores
        chatbot_record = {
            "from_chatbot": True,
            "collected_data": data,
            "document_ids": payload.document_ids,
            "documents": payload.documents if hasattr(payload, 'documents') else [],  # Include full document data
            "compliance_score": payload.compliance_score,
            "missing_fields": payload.missing_fields if hasattr(payload, 'missing_fields') else [],
        }
        update_data["onboarding_data"] = json.dumps(chatbot_record)
        
        # Update user document
        user_ref.update(update_data)
        
        log_action(
            uid, 
            "ONBOARDING_CHATBOT", 
            f"Account created from chatbot with score: {payload.compliance_score}"
        )
        
        return {
            "success": True,
            "message": "Account created successfully from chatbot data",
            "user_id": uid,
            "redirect_url": f"/{payload.role}-dashboard"
        }
    except Exception as e:
        print(f"Error creating account from chatbot: {e}")
        raise HTTPException(
            status_code=500, 
            detail=f"Failed to create account: {str(e)}"
        )


@router.post("/update-profile")
async def update_profile_with_data(
    data: Dict[str, Any],
    user: Dict[str, Any] = Depends(get_current_user)
) -> Dict[str, Any]:
    """Update user profile with specific fields during onboarding."""
    try:
        uid = user['uid']
        user_ref = db.collection("users").document(uid)
        
        # Build update from provided data
        update_data = {"updated_at": time.time()}
        
        # Map common field names
        field_mapping = {
            "companyName": "company_name",
            "dotNumber": "dot_number",
            "mcNumber": "mc_number",
            "fullName": "full_name",
            "firstName": "first_name",
            "lastName": "last_name",
            "phone": "phone",
            "cdlNumber": "cdl_number",
        }
        
        for frontend_field, db_field in field_mapping.items():
            if frontend_field in data and data[frontend_field]:
                update_data[db_field] = data[frontend_field]
        
        # Update user document
        user_ref.update(update_data)
        
        log_action(uid, "PROFILE_UPDATE", f"Updated fields: {list(update_data.keys())}")
        
        return {
            "success": True,
            "message": "Profile updated successfully",
            "updated_fields": list(update_data.keys())
        }
    except Exception as e:
        print(f"Error updating profile: {e}")
        raise HTTPException(
            status_code=500, 
            detail=f"Failed to update profile: {str(e)}"
        )


# --- NEW COMPLIANCE ENDPOINTS FOR DASHBOARD ---

@router.get("/compliance/status")
async def get_compliance_status(
    user: Dict[str, Any] = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Get compliance status for dashboard display.
    Returns DOT/MC numbers, compliance score, documents with status.
    """
    try:
        uid = user['uid']
        
        # Get onboarding data from user profile
        onboarding_score = user.get("onboarding_score", 0)
        dot_number = user.get("dot_number", "")
        mc_number = user.get("mc_number", "")
        company_name = user.get("company_name", "")
        
        # Parse documents from onboarding_data if available
        documents = []
        onboarding_data_str = user.get("onboarding_data", "{}")
        
        try:
            onboarding_data = json.loads(onboarding_data_str)
            
            # Extract documents array if present (from chatbot)
            if isinstance(onboarding_data, dict):
                if "documents" in onboarding_data:
                    raw_docs = onboarding_data.get("documents", [])
                    for doc in raw_docs:
                        status = "Unknown"
                        if doc.get("extracted_fields", {}).get("expiry_date"):
                            status = calculate_document_status(
                                doc["extracted_fields"]["expiry_date"]
                            )
                        
                        documents.append({
                            "id": doc.get("doc_id", ""),
                            "filename": doc.get("filename", ""),
                            "score": doc.get("score", 0),
                            "status": status,
                            "extracted_fields": doc.get("extracted_fields", {}),
                            "missing_fields": doc.get("missing", [])
                        })
        except Exception as e:
            print(f"Error parsing onboarding data: {e}")
        
        # Determine status color based on score
        if onboarding_score >= 80:
            status_color = "Green"
        elif onboarding_score >= 50:
            status_color = "Amber"
        else:
            status_color = "Red"
        
        return {
            "compliance_score": int(onboarding_score),
            "dot_number": dot_number,
            "mc_number": mc_number,
            "company_name": company_name,
            "status_color": status_color,
            "documents": documents,
            "score_breakdown": {
                "document_completeness": int(onboarding_score * 0.4),
                "data_accuracy": int(onboarding_score * 0.3),
                "regulatory_compliance": int(onboarding_score * 0.3)
            },
            "issues": [],
            "warnings": [],
            "recommendations": [],
            "role_data": {
                "carrier": {
                    "dot_number": dot_number,
                    "mc_number": mc_number
                },
                "driver": {
                    "license_verified": bool(user.get("cdl_number"))
                },
                "shipper": {
                    "company_verified": bool(company_name)
                }
            }
        }
    except Exception as e:
        print(f"Error fetching compliance status: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch compliance status: {str(e)}"
        )


@router.get("/documents")
async def get_documents(
    user: Dict[str, Any] = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Get list of documents with scores and status for document vault.
    """
    try:
        uid = user['uid']
        
        documents = []
        onboarding_data_str = user.get("onboarding_data", "{}")
        
        try:
            onboarding_data = json.loads(onboarding_data_str)
            
            # Extract documents array
            if isinstance(onboarding_data, dict):
                raw_docs = onboarding_data.get("documents", [])
                for doc in raw_docs:
                    status = "Unknown"
                    expiry_date = doc.get("extracted_fields", {}).get("expiry_date")
                    
                    if expiry_date:
                        status = calculate_document_status(expiry_date)
                    
                    doc_type = doc.get("extracted_fields", {}).get("document_type", "Unknown")
                    
                    documents.append({
                        "id": doc.get("doc_id", ""),
                        "filename": doc.get("filename", ""),
                        "type": doc_type,
                        "score": doc.get("score", 0),
                        "status": status,
                        "expiry_date": expiry_date,
                        "uploaded_at": doc.get("uploaded_at", ""),
                        "extracted_fields": doc.get("extracted_fields", {}),
                        "missing_fields": doc.get("missing", []),
                        "warnings": []
                    })
        except Exception as e:
            print(f"Error parsing onboarding data: {e}")
        
        return {
            "documents": documents,
            "total_count": len(documents),
            "valid_count": sum(1 for d in documents if d["status"] == "Valid"),
            "expiring_soon_count": sum(1 for d in documents if d["status"] == "Expiring Soon"),
            "expired_count": sum(1 for d in documents if d["status"] == "Expired")
        }
    except Exception as e:
        print(f"Error fetching documents: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch documents: {str(e)}"
        )

