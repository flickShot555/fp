"""Stateful onboarding chatbot flow for landing page."""
import re
import json
import logging
from enum import Enum
from typing import Dict, Any, Optional, List
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class Role(str, Enum):
    CARRIER = "carrier"
    DRIVER = "driver"
    SHIPPER = "shipper"


# Role-specific required documents (string names to avoid enum dependency in frontend)
ROLE_REQUIRED_DOCS = {
    Role.CARRIER: ["MC_CERTIFICATE", "COI", "W9"],
    Role.DRIVER: ["CDL", "MEDICAL_CARD"],
    Role.SHIPPER: ["W9"],
}


class OnboardingStep(str, Enum):
    WELCOME = "WELCOME"
    SELECT_ROLE = "SELECT_ROLE"
    COLLECT_INFO = "COLLECT_INFO"
    UPLOAD_DOC = "UPLOAD_DOC"
    REVIEW_SCORE = "REVIEW_SCORE"
    CREATE_ACCOUNT = "CREATE_ACCOUNT"
    COMPLETED = "COMPLETED"


class ChatSession(BaseModel):
    session_id: str
    step: OnboardingStep = OnboardingStep.WELCOME
    role: Optional[Role] = None
    collected_data: Dict[str, Any] = {}
    document_ids: List[str] = []
    temp_score: float = 0.0
    required_docs: List[str] = []
    completed_docs: List[str] = []
    compliance_score: float = 0.0


class ChatResponse(BaseModel):
    message: str
    next_step: OnboardingStep = OnboardingStep.WELCOME
    suggestions: List[str] = []
    ui_action: Optional[str] = None
    data_payload: Optional[Dict[str, Any]] = None


# In-memory session store with Redis fallback for production
sessions: Dict[str, ChatSession] = {}
redis_client = None  # Will be injected if available


async def get_or_create_session(session_id: str) -> ChatSession:
    """Get existing session or create new one. Uses Redis if available, falls back to memory."""
    global redis_client
    
    # Try Redis first if available
    if redis_client:
        try:
            cached = await redis_client.get(f"chat_session:{session_id}")
            if cached:
                logger.debug(f"Session {session_id} retrieved from Redis")
                return ChatSession.parse_raw(cached)
        except Exception as e:
            logger.warning(f"Redis retrieval failed for session {session_id}: {e}")
    
    # Fall back to in-memory store
    if session_id not in sessions:
        sessions[session_id] = ChatSession(session_id=session_id)
        logger.debug(f"New session created: {session_id}")
    return sessions[session_id]


async def save_session(session: ChatSession) -> None:
    """Persist session to Redis and memory."""
    global redis_client
    
    # Save to memory
    sessions[session.session_id] = session
    
    # Try to persist to Redis
    if redis_client:
        try:
            await redis_client.setex(
                f"chat_session:{session.session_id}",
                86400,  # 24 hour TTL
                session.json()
            )
            logger.debug(f"Session {session.session_id} persisted to Redis")
        except Exception as e:
            logger.warning(f"Redis save failed for session {session.session_id}: {e}")


def set_redis_client(client):
    """Inject Redis client for session persistence."""
    global redis_client
    redis_client = client
    logger.info("Redis client injected for session persistence")


async def process_onboarding_chat(
    session_id: str,
    user_text: str,
    doc_event: Optional[Dict] = None,
    document_data: Optional[Dict] = None,
) -> ChatResponse:
    """Process chatbot message and return response."""
    session = await get_or_create_session(session_id)
    text = user_text.lower().strip()
    response = None  # Will be set by the flow logic

    # --- 1. RESET / WELCOME ---
    if text in ["restart", "reset", "hi", "hello", "start", ""]:
        session.step = OnboardingStep.SELECT_ROLE
        session.collected_data = {}
        session.document_ids = []
        session.required_docs = []
        session.completed_docs = []
        session.compliance_score = 0.0
        response = ChatResponse(
            message="👋 Welcome to FreightPower AI! I'll help you get onboarded in minutes.\n\nFirst, tell me your role:",
            next_step=OnboardingStep.SELECT_ROLE,
            suggestions=["Carrier", "Driver", "Shipper"]
        )
        await save_session(session)
        return response

    # --- 2. ROLE SELECTION ---
    if session.step == OnboardingStep.SELECT_ROLE:
        if "carrier" in text or "car" in text:
            session.role = Role.CARRIER
            session.required_docs = ROLE_REQUIRED_DOCS[Role.CARRIER].copy()
            session.step = OnboardingStep.COLLECT_INFO
            response = ChatResponse(
                message="🚛 Great! As a Carrier, I need your DOT Number to verify your authority.\n\nPlease enter your 6-8 digit USDOT number:",
                next_step=OnboardingStep.COLLECT_INFO,
                suggestions=["DOT 1234567", "My DOT is 2345678"]
            )
            await save_session(session)
            return response
        elif "driver" in text or "driv" in text:
            session.role = Role.DRIVER
            session.required_docs = ROLE_REQUIRED_DOCS[Role.DRIVER].copy()
            session.step = OnboardingStep.COLLECT_INFO
            response = ChatResponse(
                message="🚗 Welcome, Driver! I need your CDL License Number to get started.\n\nPlease enter your CDL number:",
                next_step=OnboardingStep.COLLECT_INFO,
                suggestions=["CDL A12345678"]
            )
            await save_session(session)
            return response
        elif "shipper" in text or "broker" in text or "ship" in text or "brok" in text:
            session.role = Role.SHIPPER
            session.required_docs = ROLE_REQUIRED_DOCS[Role.SHIPPER].copy()
            session.step = OnboardingStep.COLLECT_INFO
            response = ChatResponse(
                message="📦 Welcome, Shipper! Please provide your Company Name:",
                next_step=OnboardingStep.COLLECT_INFO,
                suggestions=["Acme Logistics", "Global Freight Co"]
            )
            await save_session(session)
            return response
        else:
            response = ChatResponse(
                message="Please select one of the following roles to continue:",
                next_step=OnboardingStep.SELECT_ROLE,
                suggestions=["Carrier", "Driver", "Shipper"]
            )
            await save_session(session)
            return response

    # --- 3. DATA CAPTURE ---
    if session.step == OnboardingStep.COLLECT_INFO:
        # FIX #4: Validate role is not None
        if session.role is None:
            response = ChatResponse(
                message="❌ Please select your role first (Carrier, Driver, or Shipper):",
                next_step=OnboardingStep.SELECT_ROLE,
                suggestions=["Carrier", "Driver", "Shipper"]
            )
            await save_session(session)
            return response
        
        if session.role == Role.CARRIER:
            dot_match = re.search(r'\b\d{6,8}\b', text)
            if dot_match:
                session.collected_data["dot_number"] = dot_match.group()
                session.collected_data["company_name"] = "Pending Verification"
                session.step = OnboardingStep.UPLOAD_DOC
                response = ChatResponse(
                    message=f"✅ Got it! DOT #{session.collected_data['dot_number']}\n\nNow upload your MC Authority Letter or Certificate of Insurance:",
                    next_step=OnboardingStep.UPLOAD_DOC,
                    ui_action="show_upload"
                )
                await save_session(session)
                return response
            else:
                response = ChatResponse(
                    message="❌ I couldn't find a valid DOT number. Please enter a 6-8 digit number (e.g., '1234567'):",
                    next_step=OnboardingStep.COLLECT_INFO
                )
                await save_session(session)
                return response

        elif session.role == Role.DRIVER:
            if len(text) >= 5:
                session.collected_data["cdl_number"] = user_text.strip()
                session.step = OnboardingStep.UPLOAD_DOC
                response = ChatResponse(
                    message=f"✅ CDL recorded: {session.collected_data['cdl_number']}\n\nNow please upload a photo of your CDL License:",
                    next_step=OnboardingStep.UPLOAD_DOC,
                    ui_action="show_upload"
                )
                await save_session(session)
                return response
            else:
                response = ChatResponse(
                    message="❌ CDL number seems too short. Please enter your full CDL number:",
                    next_step=OnboardingStep.COLLECT_INFO
                )
                await save_session(session)
                return response

        elif session.role == Role.SHIPPER:
            session.collected_data["company_name"] = user_text.strip()
            session.step = OnboardingStep.UPLOAD_DOC
            response = ChatResponse(
                message=f"✅ Company: {session.collected_data['company_name']}\n\nPlease upload your W-9 Form for business verification:",
                next_step=OnboardingStep.UPLOAD_DOC,
                ui_action="show_upload"
            )
            await save_session(session)
            return response

    # --- 4. DOCUMENT UPLOAD & SCORING ---
    if session.step == OnboardingStep.UPLOAD_DOC:
        # First check if user wants to proceed without more documents
        if text and any(phrase in text for phrase in ["proceed", "continue", "next", "finish", "create", "account", "ready", "skip"]):
            # User wants to proceed - check if all required docs are done
            remaining = [d for d in session.required_docs if d not in session.completed_docs]
            
            if remaining:
                # Still missing docs - ask for them
                session.step = OnboardingStep.REVIEW_SCORE
                next_doc = remaining[0]
                response = ChatResponse(
                    message=f"📎 You still need to upload: {next_doc.replace('_', ' ').title()}. Please upload it or type 'skip' to continue anyway.",
                    next_step=OnboardingStep.REVIEW_SCORE,
                    ui_action="show_upload",
                    suggestions=[f"Upload {next_doc.replace('_', ' ').title()}", "Skip for now"]
                )
                await save_session(session)
                return response
            else:
                # All required docs collected - proceed to account creation
                session.step = OnboardingStep.CREATE_ACCOUNT
                response = ChatResponse(
                    message="✅ Perfect! All required documents received. Ready to create your account?",
                    next_step=OnboardingStep.CREATE_ACCOUNT,
                    ui_action="show_create_account",
                    suggestions=["Yes, create account", "Upload more documents"]
                )
                await save_session(session)
                return response
        
        # Handle document upload
        if doc_event and doc_event.get("document_id"):
            doc_id = doc_event["document_id"]
            # FIX #2: Prevent duplicate documents
            if doc_id in session.document_ids:
                logger.warning(f"Duplicate document {doc_id} detected in session {session_id}")
                response = ChatResponse(
                    message="⚠️ This document was already uploaded. Please upload a different document:",
                    next_step=OnboardingStep.UPLOAD_DOC,
                    ui_action="show_upload"
                )
                await save_session(session)
                return response
            session.document_ids.append(doc_id)

            # Initialize message - will be updated if we have document_data
            msg = f"📄 Document received!\n📊 Provisional Score: 75/100"
            session.temp_score = 75
            doc_type = "UNKNOWN"

            # Calculate provisional score if we have full document data
            if document_data:
                score = document_data.get("score", {}).get("total_score", 50)
                doc_type = document_data.get("doc_type", "Document")
                filename = document_data.get("filename", "document.pdf")
                issues = document_data.get("validation", {}).get("issues", [])
                extraction = document_data.get("extraction", {}) or {}
                # Capture user-provided identifiers from extraction when available
                if extraction.get("dot_number"):
                    session.collected_data["dot_number"] = extraction.get("dot_number")
                if extraction.get("mc_number"):
                    session.collected_data["mc_number"] = extraction.get("mc_number")

                # FIX #5: Rename variable for clarity - running average calculation
                doc_count_before = len(session.document_ids) - 1
                session.compliance_score = (
                    (session.compliance_score * doc_count_before + score) / len(session.document_ids)
                )

                session.temp_score = score
                msg = f"📄 Received: {filename}\n📊 Onboarding Score: {int(score)}/100"

                if score >= 80:
                    msg += "\n\n🟢 Excellent! Your document looks great."
                elif score >= 50:
                    msg += "\n\n🟡 Good start, but some fields may need attention."
                else:
                    msg += "\n\n🔴 Some required information is missing."

                if issues:
                    msg += f"\n⚠️ Issues: {', '.join(issues[:2])}"
            else:
                logger.warning(f"Document data not found for doc_id {doc_id} in session {session_id}")
                msg = f"📄 Document received (queued for processing)\n📊 Provisional Score: 75/100"

            # Track completed docs regardless of whether we have full document_data
            doc_type_norm = doc_type.upper().replace(" ", "_").replace("-", "_")
            filename_lower = document_data.get("filename", "").lower() if document_data else ""
            
            # Handle common doc type variations - expand mapping significantly
            doc_type_mapping = {
                # Certificate of Insurance variants
                "CERTIFICATE_OF_INSURANCE": "COI",
                "COI": "COI",
                "INSURANCE": "COI",
                "CERTIFICATE": "COI",
                # MC Certificate/Authority variants
                "MC_CERTIFICATE": "MC_CERTIFICATE",
                "MC_AUTHORITY": "MC_CERTIFICATE",
                "MC_AUTHORITY_LETTER": "MC_CERTIFICATE",
                "AUTHORITY_LETTER": "MC_CERTIFICATE",
                "MC": "MC_CERTIFICATE",
                "MOTOR_CARRIER_CERTIFICATE": "MC_CERTIFICATE",
                "MOTOR_CARRIER_AUTHORITY": "MC_CERTIFICATE",
                "AUTHORITY": "MC_CERTIFICATE",  # Catch "authority" from AI
                # W-9 variants
                "W9": "W9",
                "W_9": "W9",
                "W-9": "W9",
                "FORM_W9": "W9",
                "FORM_W_9": "W9",
                # Broker agreement variants
                "BROKER_AGREEMENT": "MC_CERTIFICATE",
                "BROKER_CARRIER_AGREEMENT": "MC_CERTIFICATE",
                "AGREEMENT": "MC_CERTIFICATE",
                # CDL and Medical
                "CDL": "CDL",
                "DRIVERS_LICENSE": "CDL",
                "MEDICAL_CARD": "MEDICAL_CARD",
                "MEDICAL": "MEDICAL_CARD",
                # Unknown fallback
                "UNKNOWN": None,
            }
            mapped_doc_type = doc_type_mapping.get(doc_type_norm, None)
            
            # If not found in exact mapping, try keyword-based matching
            if not mapped_doc_type:
                if any(keyword in doc_type_norm for keyword in ["INSURANCE", "COI"]):
                    mapped_doc_type = "COI"
                elif any(keyword in doc_type_norm for keyword in ["MC_", "AUTHORITY", "MOTOR_CARRIER", "CERTIFICATE"]):
                    mapped_doc_type = "MC_CERTIFICATE"
                elif any(keyword in doc_type_norm for keyword in ["W9", "W_9", "W-9", "FORM_W"]):
                    mapped_doc_type = "W9"
                elif any(keyword in doc_type_norm for keyword in ["BROKER", "AGREEMENT"]):
                    mapped_doc_type = "MC_CERTIFICATE"
                elif any(keyword in doc_type_norm for keyword in ["CDL", "DRIVER"]):
                    mapped_doc_type = "CDL"
                elif any(keyword in doc_type_norm for keyword in ["MEDICAL"]):
                    mapped_doc_type = "MEDICAL_CARD"
                else:
                    # Default to the normalized type if still no match
                    mapped_doc_type = doc_type_norm if doc_type_norm != "UNKNOWN" else None
            
            # Fallback: check filename if AI classification didn't work
            if not mapped_doc_type or mapped_doc_type == "UNKNOWN":
                filename_norm = filename_lower.upper().replace(" ", "_").replace("-", "_")
                if any(kw in filename_norm for kw in ["COI", "INSURANCE", "CERTIFICATE_OF"]):
                    mapped_doc_type = "COI"
                elif any(kw in filename_norm for kw in ["MC_", "MC ", "AUTHORITY", "MOTOR_CARRIER", "BROKER"]):
                    mapped_doc_type = "MC_CERTIFICATE"
                elif any(kw in filename_norm for kw in ["W9", "W-9", "W_9", "FORM_W"]):
                    mapped_doc_type = "W9"
                elif any(kw in filename_norm for kw in ["CDL", "DRIVER", "LICENSE"]):
                    mapped_doc_type = "CDL"
                elif any(kw in filename_norm for kw in ["MEDICAL", "EXAM"]):
                    mapped_doc_type = "MEDICAL_CARD"
                else:
                    mapped_doc_type = None
            
            logger.info(f"📋 Document classification summary:")
            logger.info(f"   AI Type: {doc_type}")
            logger.info(f"   Normalized: {doc_type_norm}")
            logger.info(f"   Filename: {filename_lower}")
            logger.info(f"   Mapped Type: {mapped_doc_type}")
            logger.info(f"   Required Docs: {session.required_docs}")
            logger.info(f"   Completed Docs: {session.completed_docs}")
            
            if mapped_doc_type and mapped_doc_type in session.required_docs and mapped_doc_type not in session.completed_docs:
                session.completed_docs.append(mapped_doc_type)
                logger.info(f"✅ Marked {mapped_doc_type} as completed for session {session_id}")
            elif mapped_doc_type:
                logger.warning(f"⚠️ Document type {mapped_doc_type} not in required docs or already completed")
                logger.warning(f"   Required: {session.required_docs}, Completed: {session.completed_docs}")
            else:
                logger.warning(f"❌ Could not map document type: {doc_type}")

            # Determine remaining required docs
            remaining = [d for d in session.required_docs if d not in session.completed_docs]
            logger.info(f"📊 Remaining docs: {remaining}")

            if remaining:
                # FIX #1: Transition to REVIEW_SCORE step instead of staying in UPLOAD_DOC
                session.step = OnboardingStep.REVIEW_SCORE
                next_doc = remaining[0]
                response = ChatResponse(
                    message=msg + f"\n\nNext required document: {next_doc.replace('_', ' ').title()}",
                    next_step=OnboardingStep.REVIEW_SCORE,
                    ui_action="show_score_animation",
                    suggestions=[f"Upload {next_doc}", "What documents are required?"],
                    data_payload={
                        "completed_docs": session.completed_docs,
                        "required_docs": session.required_docs,
                        "remaining_docs": remaining,
                        "compliance_score": int(session.compliance_score),
                    },
                )
                await save_session(session)
                return response

            # All required docs collected -> ready to save onboarding
            session.step = OnboardingStep.CREATE_ACCOUNT
            response = ChatResponse(
                message=msg + "\n\nAll required documents received. Finalizing onboarding...",
                next_step=OnboardingStep.CREATE_ACCOUNT,
                ui_action="save_onboarding",
                data_payload={
                    "role": session.role.value if session.role else "carrier",
                    "collected_data": session.collected_data,
                    "document_ids": session.document_ids,
                    "compliance_score": int(session.compliance_score),
                    "required_docs": session.required_docs,
                    "completed_docs": session.completed_docs,
                },
                suggestions=["Finish onboarding"]
            )
            await save_session(session)
            return response
        else:
            response = ChatResponse(
                message="📎 I need a document to proceed. Please use the upload button below:",
                next_step=OnboardingStep.UPLOAD_DOC,
                ui_action="show_upload"
            )

            await save_session(session)
            return response

    # --- 5. REVIEW SCORE (New state to prevent infinite upload loop) ---
    if session.step == OnboardingStep.REVIEW_SCORE:
        if "upload" in text or "another" in text or "document" in text or "picker" in text or "media" in text:
            session.step = OnboardingStep.UPLOAD_DOC
            response = ChatResponse(
                message="📎 Ready to upload another document. Please use the upload button:",
                next_step=OnboardingStep.UPLOAD_DOC,
                ui_action="show_upload"
            )
            await save_session(session)
            return response
        elif "skip" in text or "continue" in text or "next" in text or "proceed" in text or "finish" in text or "account" in text or "create" in text or "ready" in text or "yes" in text:
            # Check if all required docs are completed or user wants to skip
            remaining = [d for d in session.required_docs if d not in session.completed_docs]
            
            if remaining and "skip" not in text:
                # Still missing docs and user didn't explicitly skip
                session.step = OnboardingStep.UPLOAD_DOC
                next_doc = remaining[0]
                response = ChatResponse(
                    message=f"📎 Still need: {next_doc.replace('_', ' ').title()}. Please use the upload button:",
                    next_step=OnboardingStep.UPLOAD_DOC,
                    ui_action="show_upload",
                    suggestions=["Upload now"]
                )
                await save_session(session)
                return response
            else:
                # All docs collected or user skipped, move to account creation
                session.step = OnboardingStep.CREATE_ACCOUNT
                response = ChatResponse(
                    message="✅ Perfect! Ready to create your account?",
                    next_step=OnboardingStep.CREATE_ACCOUNT,
                    ui_action="show_create_account",
                    suggestions=["Yes, create account", "Upload more documents"]
                )
                await save_session(session)
                return response
        else:
            response = ChatResponse(
                message="Would you like to upload another document, or proceed to account creation?",
                next_step=OnboardingStep.REVIEW_SCORE,
                suggestions=["Upload another", "Continue"]
            )
            await save_session(session)
            return response

    # --- 6. CREATE ACCOUNT (Redirect to Signup or Direct Creation) ---
    if session.step == OnboardingStep.CREATE_ACCOUNT:
        if "yes" in text or "create" in text or "account" in text or "proceed" in text or "ready" in text or "finish" in text:
            session.step = OnboardingStep.COMPLETED
            payload = {
                "role": session.role.value if session.role else "carrier",
                "collected_data": session.collected_data,
                "document_ids": session.document_ids,
                "compliance_score": int(session.compliance_score),
            }
            response = ChatResponse(
                message="🚀 Perfect! Creating your account with the collected information...",
                next_step=OnboardingStep.COMPLETED,
                ui_action="create_account_chatbot",
                data_payload=payload
            )
            await save_session(session)
            return response
        elif "upload" in text or "another" in text or "more" in text or "document" in text:
            session.step = OnboardingStep.UPLOAD_DOC
            response = ChatResponse(
                message="📎 Sure! Upload another document:",
                next_step=OnboardingStep.UPLOAD_DOC,
                ui_action="show_upload"
            )
            await save_session(session)
            return response
        else:
            response = ChatResponse(
                message="Would you like to create your account now, or upload more documents?",
                next_step=OnboardingStep.CREATE_ACCOUNT,
                suggestions=["Yes, create account", "Upload more"]
            )
            await save_session(session)
            return response

    # --- Fallback ---
    response = ChatResponse(
        message="🤔 I didn't understand that. Type 'reset' to start over, or choose an option above.",
        next_step=session.step,
        suggestions=["Reset", "Help"]
    )
    await save_session(session)
    return response

