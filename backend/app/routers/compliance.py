"""Compliance router for compliance status, scoring, and AI recommendations."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Dict, Any, List
from datetime import datetime, timedelta

from ..core.database import get_db
from ..core.security import get_current_active_user, require_roles
from ..models.user import User, UserRole
from ..models.document import Document, DocumentType
from ..models.carrier import Carrier
from ..models.driver import Driver
from ..models.company import Company
from ..services.compliance_service import ComplianceService
from ..services.ai_service import AIService

router = APIRouter(prefix="/compliance", tags=["compliance"])


@router.get("/status")
async def get_compliance_status(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """Get comprehensive compliance status for current user with AI scoring."""
    compliance_service = ComplianceService(db)
    ai_service = AIService()
    
    # Get basic compliance status
    base_status = await compliance_service.check_user_compliance(current_user.id)

    # Get user's documents (all documents, not just active)
    doc_result = await db.execute(
        select(Document).where(Document.owner_id == current_user.id)
    )
    documents = list(doc_result.scalars().all())

    # Also get onboarding data stored on user (it's stored as JSON string)
    import json as json_module
    onboarding_data = {}
    if current_user.onboarding_data:
        try:
            onboarding_data = json_module.loads(current_user.onboarding_data)
        except:
            onboarding_data = {}
    
    # Prepare documents summary
    doc_summary = []
    for doc in documents:
        days_until_expiry = None
        if doc.expiry_date:
            days_until_expiry = (doc.expiry_date - datetime.utcnow()).days
        
        doc_summary.append({
            "id": doc.id,
            "type": doc.document_type.value if doc.document_type else "other",
            "filename": doc.original_filename,
            "status": doc.validation_status or "pending",
            "expiry_date": doc.expiry_date.isoformat() if doc.expiry_date else None,
            "days_until_expiry": days_until_expiry,
            "is_expired": days_until_expiry is not None and days_until_expiry < 0,
            "is_expiring_soon": days_until_expiry is not None and 0 <= days_until_expiry <= 30,
            "uploaded_at": doc.created_at.isoformat() if doc.created_at else None
        })
    
    # Role-specific data - combine database and onboarding data
    role_data = {}
    if current_user.role == UserRole.CARRIER:
        # Start with onboarding data (handle both camelCase and snake_case)
        role_data = {
            "dot_number": onboarding_data.get("dotNumber") or onboarding_data.get("dot_number") or current_user.dot_number or "",
            "mc_number": onboarding_data.get("mcNumber") or onboarding_data.get("mc_number") or current_user.mc_number or "",
            "company_name": onboarding_data.get("companyName") or onboarding_data.get("company_name") or current_user.company_name or "",
            "fmcsa_verified": False,
            "authority_status": "Pending",
            "insurance_status": onboarding_data.get("insuranceStatus") or onboarding_data.get("insurance_status") or "Unknown",
            "insurance_expiry": onboarding_data.get("insuranceExpiry") or onboarding_data.get("insurance_expiry"),
            "safety_rating": onboarding_data.get("safetyRating") or onboarding_data.get("safety_rating") or "N/A",
            "fleet_size": onboarding_data.get("fleetSize") or onboarding_data.get("fleet_size") or 0
        }
        # Override with carrier table data if exists
        if current_user.company_id:
            carrier_result = await db.execute(
                select(Carrier).where(Carrier.company_id == current_user.company_id)
            )
            carrier = carrier_result.scalar_one_or_none()
            if carrier:
                role_data.update({
                    "dot_number": carrier.usdot or role_data["dot_number"],
                    "mc_number": carrier.mc_number or role_data["mc_number"],
                    "fmcsa_verified": carrier.fmcsa_verified or False,
                    "authority_status": carrier.authority_status or "Pending",
                    "insurance_status": carrier.insurance_status or role_data["insurance_status"],
                    "insurance_expiry": carrier.insurance_expiry.isoformat() if carrier.insurance_expiry else role_data["insurance_expiry"],
                    "safety_rating": carrier.safety_rating or role_data["safety_rating"],
                    "fleet_size": carrier.fleet_size or role_data["fleet_size"]
                })
    elif current_user.role == UserRole.DRIVER:
        # Start with onboarding data (handle camelCase and snake_case)
        role_data = {
            "cdl_number": onboarding_data.get("cdlNumber") or onboarding_data.get("cdl_number") or "",
            "cdl_state": onboarding_data.get("cdlState") or onboarding_data.get("cdl_state") or "",
            "cdl_class": onboarding_data.get("cdlClass") or onboarding_data.get("cdl_class") or "",
            "cdl_expiry": onboarding_data.get("cdlExpiry") or onboarding_data.get("cdl_expiry"),
            "cdl_verified": False,
            "medical_card_expiry": onboarding_data.get("medicalCardExpiry") or onboarding_data.get("medical_card_expiry"),
            "medical_card_verified": False,
            "drug_test_status": onboarding_data.get("drugTestStatus") or onboarding_data.get("drug_test_status") or "pending",
            "drug_test_date": onboarding_data.get("drugTestDate") or onboarding_data.get("drug_test_date"),
            "mvr_status": onboarding_data.get("mvrStatus") or onboarding_data.get("mvr_status") or "pending",
            "clearinghouse_status": onboarding_data.get("clearinghouseStatus") or onboarding_data.get("clearinghouse_status") or "pending",
            "full_name": onboarding_data.get("fullName") or current_user.full_name or ""
        }
        # Override with driver table data if exists
        driver_result = await db.execute(
            select(Driver).where(Driver.user_id == current_user.id)
        )
        driver = driver_result.scalar_one_or_none()
        if driver:
            role_data.update({
                "cdl_number": driver.cdl_number or role_data["cdl_number"],
                "cdl_state": driver.cdl_state or role_data["cdl_state"],
                "cdl_class": driver.cdl_class or role_data["cdl_class"],
                "cdl_expiry": driver.cdl_expiry.isoformat() if driver.cdl_expiry else role_data["cdl_expiry"],
                "cdl_verified": driver.cdl_verified or False,
                "medical_card_expiry": driver.medical_card_expiry.isoformat() if driver.medical_card_expiry else role_data["medical_card_expiry"],
                "medical_card_verified": driver.medical_card_verified or False,
                "drug_test_status": driver.drug_test_status or role_data["drug_test_status"],
                "drug_test_date": driver.drug_test_date.isoformat() if driver.drug_test_date else role_data["drug_test_date"],
                "mvr_status": driver.mvr_status or role_data["mvr_status"],
                "clearinghouse_status": driver.clearinghouse_status or role_data["clearinghouse_status"]
            })
    elif current_user.role == UserRole.SHIPPER:
        # Shipper onboarding data (handle camelCase and snake_case)
        role_data = {
            "company_name": onboarding_data.get("businessName") or onboarding_data.get("company_name") or current_user.company_name or "",
            "business_type": onboarding_data.get("businessType") or onboarding_data.get("business_type") or "",
            "tax_id": onboarding_data.get("taxId") or onboarding_data.get("tax_id") or "",
            "shipping_volume": onboarding_data.get("avgMonthlyVolume") or onboarding_data.get("shipping_volume") or "",
            "freight_type": onboarding_data.get("freightType") or onboarding_data.get("freight_type") or "",
            "regions": onboarding_data.get("regionsOfOperation") or onboarding_data.get("regions") or []
        }
    
    # Calculate AI compliance score
    ai_score = await calculate_ai_compliance_score(
        base_status, doc_summary, role_data, current_user.role, ai_service
    )
    
    return {
        "user_id": current_user.id,
        "role": current_user.role.value,
        "compliance_score": ai_score["overall_score"],
        "score_breakdown": ai_score["breakdown"],
        "status_color": ai_score["status_color"],
        "is_compliant": ai_score["overall_score"] >= 80,
        "documents": doc_summary,
        "role_data": role_data,
        "issues": base_status.get("issues", []),
        "warnings": base_status.get("warnings", []),
        "recommendations": ai_score.get("recommendations", []),
        "last_checked": datetime.utcnow().isoformat()
    }


async def calculate_ai_compliance_score(
    base_status: Dict, documents: List[Dict], role_data: Dict, 
    role: UserRole, ai_service: AIService
) -> Dict[str, Any]:
    """Calculate AI-powered compliance score with breakdown."""
    breakdown = {
        "documents": 0,
        "verification": 0,
        "expiry_status": 0,
        "completeness": 0
    }
    
    # Documents score (25% weight)
    required_count = len(base_status.get("required_documents", []))
    if required_count > 0:
        uploaded_valid = sum(1 for d in documents if d["status"] == "valid")
        breakdown["documents"] = min(100, (uploaded_valid / required_count) * 100)
    else:
        breakdown["documents"] = 100
    
    # Verification score (25% weight)
    verification_checks = base_status.get("checks", {})
    if verification_checks:
        passed = sum(1 for v in verification_checks.values() if v)
        breakdown["verification"] = (passed / len(verification_checks)) * 100 if verification_checks else 100
    else:
        breakdown["verification"] = 100
    
    # Expiry status score (25% weight)
    if documents:
        valid_docs = sum(1 for d in documents if not d.get("is_expired", False))
        breakdown["expiry_status"] = (valid_docs / len(documents)) * 100
    else:
        breakdown["expiry_status"] = 50  # No documents = partial score
    
    # Completeness score (25% weight)
    breakdown["completeness"] = base_status.get("score", 0)
    
    # Calculate overall score
    overall_score = (
        breakdown["documents"] * 0.25 +
        breakdown["verification"] * 0.25 +
        breakdown["expiry_status"] * 0.25 +
        breakdown["completeness"] * 0.25
    )

    # Determine status color
    if overall_score >= 80:
        status_color = "Green"
    elif overall_score >= 50:
        status_color = "Amber"
    else:
        status_color = "Red"

    # Generate AI recommendations
    recommendations = []

    # Add recommendations based on issues
    for issue in base_status.get("issues", []):
        if "Missing" in issue:
            recommendations.append({
                "priority": "high",
                "category": "documents",
                "title": issue,
                "action": "Upload the missing document"
            })
        elif "expired" in issue.lower():
            recommendations.append({
                "priority": "critical",
                "category": "documents",
                "title": issue,
                "action": "Renew and upload new document"
            })

    # Add recommendations for expiring documents
    for doc in documents:
        if doc.get("is_expiring_soon") and not doc.get("is_expired"):
            recommendations.append({
                "priority": "medium",
                "category": "expiry",
                "title": f"{doc['type']} expires in {doc['days_until_expiry']} days",
                "action": "Prepare renewal documentation"
            })

    return {
        "overall_score": round(overall_score, 1),
        "breakdown": {k: round(v, 1) for k, v in breakdown.items()},
        "status_color": status_color,
        "recommendations": recommendations[:5]  # Limit to 5 recommendations
    }


@router.get("/tasks")
async def get_compliance_tasks(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
) -> List[Dict[str, Any]]:
    """Get prioritized compliance tasks for user."""
    compliance_service = ComplianceService(db)

    # Get documents expiring soon
    expiring_docs = await compliance_service.get_expiring_documents_report(days=60)

    # Filter for current user's documents
    user_expiring = [d for d in expiring_docs if d.get("owner_id") == current_user.id]

    tasks = []
    for doc in user_expiring:
        days = doc.get("days_until_expiry", 0)
        task_type = "critical" if days <= 7 else "warning" if days <= 30 else "info"

        tasks.append({
            "id": doc.get("document_id"),
            "type": task_type,
            "title": f"Renew {doc.get('document_type', 'Document')}",
            "description": f"Expires in {days} days - {doc.get('expiry_date', 'Unknown')}",
            "actions": ["Upload New", "Set Reminder"],
            "icon": "fa-file-shield",
            "document_type": doc.get("document_type")
        })

    # Get next best actions from compliance service
    actions = await compliance_service.get_next_best_actions(current_user.id)

    for action in actions:
        tasks.append({
            "id": f"action-{len(tasks)}",
            "type": action.get("priority", "medium"),
            "title": action.get("title", "Complete Task"),
            "description": action.get("description", ""),
            "actions": [action.get("action", "Complete").title()],
            "icon": "fa-clipboard-check",
            "category": action.get("category")
        })

    # Sort by priority
    priority_order = {"critical": 0, "high": 1, "warning": 2, "medium": 3, "info": 4, "low": 5}
    tasks.sort(key=lambda x: priority_order.get(x.get("type"), 4))

    return tasks[:10]  # Return top 10 tasks


@router.post("/ai-analyze")
async def ai_analyze_compliance(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """Get AI-powered deep compliance analysis with recommendations."""
    ai_service = AIService()

    # Get full compliance status
    status = await get_compliance_status(current_user, db)

    # Generate AI analysis
    try:
        analysis_prompt = f"""
        Analyze this freight company/driver compliance profile and provide detailed recommendations:

        Role: {status['role']}
        Compliance Score: {status['compliance_score']}
        Score Breakdown: {status['score_breakdown']}
        Documents: {len(status['documents'])} uploaded
        Issues: {status['issues']}
        Warnings: {status['warnings']}

        Provide a JSON response with:
        {{
            "summary": "2-3 sentence overall assessment",
            "risk_level": "low|medium|high",
            "immediate_actions": ["action1", "action2"],
            "improvement_tips": ["tip1", "tip2", "tip3"],
            "estimated_score_after_fixes": number
        }}
        """

        response = await ai_service.chat_completion(
            messages=[{"role": "user", "content": analysis_prompt}],
            system_prompt="You are an expert freight compliance analyst. Provide actionable, specific recommendations.",
            temperature=0.3
        )

        import json
        try:
            ai_analysis = json.loads(response)
        except:
            ai_analysis = {
                "summary": response[:200] if response else "Analysis complete.",
                "risk_level": "medium" if status['compliance_score'] < 80 else "low",
                "immediate_actions": status['recommendations'][:3] if status.get('recommendations') else [],
                "improvement_tips": ["Upload missing documents", "Verify FMCSA status", "Keep documents up to date"],
                "estimated_score_after_fixes": min(100, status['compliance_score'] + 15)
            }

        return {
            "current_score": status['compliance_score'],
            "analysis": ai_analysis,
            "generated_at": datetime.utcnow().isoformat()
        }
    except Exception as e:
        return {
            "current_score": status['compliance_score'],
            "analysis": {
                "summary": "Unable to generate AI analysis at this time.",
                "risk_level": "unknown",
                "immediate_actions": status.get('recommendations', [])[:3],
                "improvement_tips": [],
                "estimated_score_after_fixes": status['compliance_score']
            },
            "error": str(e),
            "generated_at": datetime.utcnow().isoformat()
        }

