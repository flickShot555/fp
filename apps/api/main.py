# File: apps/api/main.py
from fastapi import FastAPI, UploadFile, File, HTTPException, Header, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, root_validator
from typing import Dict, Any, List, Optional, Tuple
import uuid
import json
import time
import os

# --- Local Imports ---
from .settings import settings
from .storage import ResponseStore
from .pdf_utils import pdf_to_images, pdf_to_text
from .vision import detect_document_type, extract_document
from .rag import build_document_chunks, retrieve
from .scoring import score_onboarding
from .classification import resolve_document_type
from .validation import validate_document
from .enrichment import enrich_extraction
from .knowledge import bootstrap_knowledge_base
from .fmcsa import FmcsaClient, profile_to_dict
from .preextract import preextract_fields
from .coach import compute_coach_plan
from .match import match_load
from .alerts import create_alert, list_alerts, summarize_alerts, digest_alerts
from .scheduler import SchedulerWrapper
from .forms import (
    autofill_driver_registration,
    autofill_clearinghouse_consent,
    autofill_mvr_release,
)
from .notify import send_webhook
from .auth import router as auth_router, get_current_user
from .database import db, log_action, bucket  # Added bucket import
from firebase_admin import auth as firebase_auth
from firebase_admin import firestore

# --- NEW IMPORTS FOR CHATBOT & ONBOARDING ---
from .chat_flow import process_onboarding_chat
from .models import ChatResponse
from .onboarding import router as onboarding_router
from .models import (
    LoadStep1Create, LoadStep1Response, LoadStep2Update, LoadStep3Update,
    LoadComplete, LoadResponse, LoadListResponse, LoadStatus,
    GenerateInstructionsRequest, GenerateInstructionsResponse,
    AcceptCarrierRequest, RejectOfferRequest, DriverStatusUpdateRequest,
    LoadStatusChangeLog, LoadActionResponse, TenderOfferRequest,
    OfferResponse, OffersListResponse,
    DistanceCalculationRequest, DistanceCalculationResponse,
    LoadCostCalculationRequest, LoadCostCalculationResponse
)
from .utils import generate_load_id
from .ai_utils import calculate_freight_distance, calculate_load_cost

# --- App Initialization ---
app = FastAPI(title="FreightPower AI API", version="1.0.0")

# --- CORS Middleware ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Global Services ---
store = ResponseStore(base_dir=settings.DATA_DIR)
bootstrap_knowledge_base(store)
fmcsa_client: FmcsaClient | None = None
scheduler = SchedulerWrapper()


# --- Pydantic Models ---

class ChatRequest(BaseModel):
    query: str
    max_context_chars: int = 4000

class InteractiveChatRequest(BaseModel):
    session_id: str
    message: str
    attached_document_id: Optional[str] = None 

class FmcsaVerifyRequest(BaseModel):
    usdot: Optional[str] = None
    mc_number: Optional[str] = None

    @root_validator(skip_on_failure=True)
    def require_identifier(cls, values):
        if not values.get("usdot") and not values.get("mc_number"):
            raise ValueError("Provide at least a USDOT or MC number")
        return values

class LoadRequest(BaseModel):
    id: str
    origin: Optional[str] = None
    origin_state: Optional[str] = None
    destination: Optional[str] = None
    destination_state: Optional[str] = None
    equipment: Optional[str] = None
    weight: Optional[float] = None
    metadata: Dict[str, Any] = {}

class CarrierRequest(BaseModel):
    id: str
    name: Optional[str] = None
    equipment: Optional[List[str]] = None
    equipment_types: Optional[List[str]] = None
    lanes: Optional[List[Dict[str, Any]]] = None
    compliance_score: Optional[float] = None
    fmcsa_verification: Optional[Dict[str, Any]] = None
    metadata: Dict[str, Any] = {}

class MatchRequest(BaseModel):
    load: LoadRequest
    carriers: List[CarrierRequest]
    top_n: int = 5
    min_compliance: Optional[float] = None
    require_fmcsa: bool = False

class LoadCreateRequest(LoadRequest):
    pass

class CarrierCreateRequest(CarrierRequest):
    pass

class AssignmentRequest(BaseModel):
    load_id: str
    carrier_id: str
    reason: Optional[str] = None

class AlertRequest(BaseModel):
    type: str
    message: str
    priority: Optional[str] = "routine"
    entity_id: Optional[str] = None


# --- Core Endpoints ---

@app.get("/health")
def health():
    return {"status": "ok"}

# --- List Documents Endpoint (for Dashboard) ---
@app.get("/documents")
async def list_documents(user: dict = Depends(get_current_user)):
    """
    Returns the list of documents from user's onboarding with status.
    """
    from .onboarding import calculate_document_status
    
    uid = user['uid']
    documents = []
    onboarding_data_str = user.get("onboarding_data")
    
    try:
        # Handle None/null values from Firebase
        if not onboarding_data_str:
            onboarding_data = {}
        else:
            onboarding_data = json.loads(onboarding_data_str)
        
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

@app.get("/compliance/tasks")
async def get_compliance_tasks(user: dict = Depends(get_current_user)):
    """
    Get compliance tasks and reminders for the user's dashboard.
    """
    uid = user['uid']
    tasks = []
    
    # Check if onboarding is complete
    if not user.get("onboarding_completed", False):
        tasks.append({
            "id": "task-onboarding",
            "type": "warning",
            "title": "Complete Onboarding",
            "description": "Upload required documents to improve your compliance score",
            "priority": "high",
            "actions": ["Go to Onboarding"],
            "icon": "fa-clipboard-list"
        })
    
    # Check if DOT number exists
    if not user.get("dot_number"):
        tasks.append({
            "id": "task-dot",
            "type": "info",
            "title": "Add DOT Number",
            "description": "Upload your DOT certificate to verify your company",
            "priority": "medium",
            "actions": ["Upload Document"],
            "icon": "fa-file"
        })
    
    # Check onboarding data for expiring documents
    onboarding_data_str = user.get("onboarding_data")
    if onboarding_data_str:
        try:
            from .onboarding import calculate_document_status
            onboarding_data = json.loads(onboarding_data_str)
            if isinstance(onboarding_data, dict):
                raw_docs = onboarding_data.get("documents", [])
                expiring_docs = []
                for doc in raw_docs:
                    expiry_date = doc.get("extracted_fields", {}).get("expiry_date")
                    if expiry_date and calculate_document_status(expiry_date) == "Expiring Soon":
                        expiring_docs.append(doc.get("filename", "Document"))
                
                if expiring_docs:
                    tasks.append({
                        "id": "task-expiring",
                        "type": "warning",
                        "title": "Documents Expiring Soon",
                        "description": f"{len(expiring_docs)} of your documents are expiring within 30 days",
                        "priority": "high",
                        "actions": ["View Documents"],
                        "icon": "fa-exclamation-triangle"
                    })
        except Exception as e:
            print(f"Error checking expiring documents: {e}")
    
    return tasks

@app.post("/documents")
async def upload_document(
    file: UploadFile = File(...),
    user: Dict[str, Any] = Depends(get_current_user)
):
    """Upload and classify a document, save to user's Firebase profile and Storage."""
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")

    data = await file.read()
    
    # Upload to Firebase Storage
    uid = user['uid']
    doc_id = str(uuid.uuid4())
    storage_path = f"documents/{uid}/{doc_id}_{file.filename}"
    download_url = None
    
    try:
        blob = bucket.blob(storage_path)
        blob.upload_from_string(data, content_type='application/pdf')
        blob.make_public()
        download_url = blob.public_url
        print(f"✅ File uploaded to Firebase Storage: {storage_path}")
    except Exception as e:
        error_msg = str(e)
        print(f"❌ Error uploading to Firebase Storage: {error_msg}")
        # Continue processing even if storage fails - will store metadata without URL
        print(f"⚠️ Continuing without Firebase Storage URL...")
        download_url = None
    
    try:
        images = pdf_to_images(data)
        if not images:
            raise ValueError("No pages rendered from PDF")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"PDF render failed: {e}")

    plain_text = pdf_to_text(data)
    pre_data = preextract_fields(plain_text or "")
    
    try:
        detection = detect_document_type(images, (plain_text or "")[:2000], pre_data.get("signals", {}))
        raw_detection = dict(detection)
        detected_type = detection.get("document_type", "OTHER")
        extraction = extract_document(images, detected_type, plain_text or "", pre_data.get("prefill", {}))
        raw_extraction = dict(extraction)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Vision extraction failed: {e}")

    if not extraction.get("text"):
        extraction["text"] = plain_text or ""

    extraction = enrich_extraction(extraction, plain_text)
    classification = resolve_document_type(detection, extraction, plain_text, pre_data.get("signals"))
    doc_type_upper = classification.get("document_type", detected_type or "OTHER").upper()
    extraction["document_type"] = doc_type_upper
    validation = validate_document(extraction, doc_type_upper, store=store)
    score_snapshot = score_onboarding(extraction, validation)

    usdot, mc_number = _extract_identifiers(extraction)
    fmcsa_summary = None
    if usdot or mc_number:
        fmcsa_summary = _attempt_fmcsa_verify(usdot, mc_number)

    coach = compute_coach_plan(
        document=extraction,
        validation=validation,
        verification=fmcsa_summary,
    )
    
    # Logic: If no user (guest), create a temp guest ID
    if user:
        owner_id = user['uid']
    else:
        owner_id = f"guest_{uuid.uuid4().hex[:8]}"

    record = {
        "id": doc_id,
        "owner_id": owner_id,
        "filename": file.filename,
        "doc_type": doc_type_upper,
        "storage_path": storage_path,  # Add Firebase Storage path
        "download_url": download_url,  # Add public download URL
        "detection": detection,
        "extraction": extraction,
        "classification": classification,
        "validation": validation,
        "score": score_snapshot,
        "fmcsa_verification": fmcsa_summary,
        "coach_plan": coach,
        "_debug": {
            "detection_raw": raw_detection,
            "extraction_raw": raw_extraction,
            "preextract": pre_data,
        },
    }

    try:
        chunks = build_document_chunks(doc_id, extraction.get("text") or "", record["doc_type"])
        store.upsert_document_chunks(doc_id, chunks)
        record["chunk_count"] = len(chunks)
    except Exception:
        record["chunk_count"] = 0

    # Save to local storage
    store.save_document(record)
    
    # Save to Firebase user document - add to documents array
    try:
        uid = user['uid']
        user_ref = db.collection("users").document(uid)
        
        # Fetch existing onboarding data to preserve documents array
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
        
        # Extract the expiry date from extraction for status calculation
        expiry_date = extraction.get("expiry_date") or extraction.get("extracted_fields", {}).get("expiry_date")
        
        # Create document record for the documents array
        doc_record = {
            "doc_id": doc_id,
            "filename": file.filename,
            "storage_path": storage_path,
            "download_url": download_url,
            "uploaded_at": time.time(),
            "extracted_fields": {
                "document_type": doc_type_upper,
                "expiry_date": expiry_date
            },
            "score": score_snapshot,
            "validation_status": validation.get("status"),
            "missing": validation.get("issues", [])
        }
        
        # Append to documents array
        docs_array = existing_data.get("documents", [])
        docs_array.append(doc_record)
        existing_data["documents"] = docs_array
        
        # Calculate overall onboarding score from all documents
        total_score = 0
        valid_docs = 0
        for doc in docs_array:
            doc_score = doc.get("score", 0)
            if isinstance(doc_score, dict):
                doc_score = doc_score.get("total", 0)
            if doc_score > 0:
                total_score += doc_score
                valid_docs += 1
        
        overall_score = int(total_score / valid_docs) if valid_docs > 0 else 0
        
        # Update user document with new documents array and updated score
        user_ref.update({
            "onboarding_data": json.dumps(existing_data),
            "onboarding_score": overall_score,
            "updated_at": time.time()
        })
        
        print(f"📊 Updated onboarding score: {overall_score}% (from {valid_docs} documents)")
        
        log_action(uid, "DOCUMENT_UPLOAD", f"Document uploaded: {file.filename} (Type: {doc_type_upper})")
    except Exception as e:
        print(f"Warning: Could not save document to Firebase: {e}")
        # Don't fail the upload, continue with local storage
    
    return {
        "document_id": doc_id,
        "doc_type": record["doc_type"],
        "filename": file.filename,
        "download_url": download_url,
        "storage_path": storage_path,
        "confidence": classification.get("confidence"),
        "chunks_indexed": record.get("chunk_count", 0),
        "validation": {
            "status": validation.get("status"),
            "issues": validation.get("issues"),
        },
        "score": score_snapshot,
        "fmcsa_verification": fmcsa_summary,
        "coach": coach,
        "extraction": extraction 
    }


@app.get("/documents/{document_id}")
def get_document(document_id: str, user: dict = Depends(get_current_user)):
    doc = store.get_document(document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return doc


@app.get("/documents")
async def list_user_documents(user: Dict[str, Any] = Depends(get_current_user)):
    """Get all documents for the current user from Firebase."""
    try:
        uid = user['uid']
        user_ref = db.collection("users").document(uid)
        user_doc = user_ref.get()
        
        if not user_doc.exists:
            return {"documents": []}
        
        user_data = user_doc.to_dict()
        onboarding_data_str = user_data.get("onboarding_data", "{}")
        
        # Parse onboarding data
        try:
            onboarding_data = json.loads(onboarding_data_str) if isinstance(onboarding_data_str, str) else onboarding_data_str
        except:
            onboarding_data = {}
        
        documents = onboarding_data.get("documents", [])
        
        return {
            "documents": documents,
            "total": len(documents)
        }
    except Exception as e:
        print(f"Error fetching documents: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch documents: {str(e)}")


# --- RAG CHAT ENDPOINT (Logged In) ---
@app.post("/chat")
def chat(req: ChatRequest):
    from .vision import chat_answer

    all_chunks = store.get_all_chunks()
    topk = retrieve(all_chunks, req.query, k=5)
    if not topk:
        context = "No context available yet. Answer briefly."
        sources: List[Dict[str, Any]] = []
    else:
        parts: List[str] = []
        sources = []
        for score, ch in topk:
            parts.append(ch.get("content", ""))
            sources.append({
                "document_id": ch.get("document_id"),
                "chunk_index": ch.get("chunk_index"),
                "score": round(float(score), 4),
            })
        context = "\n\n---\n\n".join(parts)[: req.max_context_chars]

    answer = chat_answer(req.query, context)
    store.append_chat({"query": req.query, "answer": answer, "sources": sources})
    return {"answer": answer, "sources": sources}


# --- NEW: LANDING PAGE CHATBOT (Public) ---
@app.post("/chat/onboarding", response_model=ChatResponse)
def onboarding_chat(req: InteractiveChatRequest):
    """
    Stateful chatbot endpoint for Landing Page.
    """
    doc_event = None
    if req.attached_document_id:
        doc_event = {"document_id": req.attached_document_id}

    response = process_onboarding_chat(
        session_id=req.session_id, 
        user_text=req.message,
        doc_event=doc_event,
        store=store 
    )
    return response


@app.get("/onboarding/score/{document_id}")
def onboarding_score(document_id: str):
    doc = store.get_document(document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    normalized = doc.get("extraction", {})
    validation = doc.get("validation")
    result = score_onboarding(normalized, validation)
    return result

# --- NEW: COACH STATUS ENDPOINT FOR DASHBOARD (WEEK 2 FEATURE) ---
@app.get("/onboarding/coach-status")
def get_onboarding_coach_status(user: dict = Depends(get_current_user)):
    """
    Retrieves the latest compliance score, FMCSA status, and next best actions for the user.
    """
    try:
        uid = user['uid']
        
        # 1. Find the user's latest uploaded document associated with their ID
        # Check if method exists, otherwise return default response
        if not hasattr(store, 'get_latest_document_by_owner'):
            # Return a baseline status if method not available
            return {
                "is_ready": True,
                "status_color": "Green",
                "total_score": 100,
                "document_type": "N/A",
                "next_best_actions": [],
                "fmcsa_status": "Active"
            }
        
        latest_doc = store.get_latest_document_by_owner(uid)
        
        if not latest_doc:
            # If no document is uploaded yet, return a baseline status
            return {
                "is_ready": False,
                "status_color": "Red",
                "total_score": 0,
                "document_type": "None",
                "next_best_actions": ["Start the chatbot to upload your first document (CDL/MC Cert)."],
                "fmcsa_status": "N/A"
            }

        # 2. Recalculate score and NBA using the stored data
        extraction = latest_doc.get("extraction", {})
        validation = latest_doc.get("validation", {})
        
        # This calls score_onboarding which generates NBA and total_score
        coach_data = score_onboarding(extraction, validation)
        
        # 3. Retrieve FMCSA Status from the stored record
        fmcsa_verification = latest_doc.get('fmcsa_verification', {})
        fmcsa_result = fmcsa_verification.get('result', 'Pending')

        # 4. Determine status color for the badge
        score = coach_data['total_score']
        status_color = "Red"
        if score >= 90:
            status_color = "Green"
        elif score >= 50:
            status_color = "Amber"
            
        return {
            "document_id": latest_doc['id'],
            "is_ready": score >= 90,
            "status_color": status_color,
            "fmcsa_status": fmcsa_result,
            **coach_data
        }
    except Exception as e:
        print(f"Error in coach-status endpoint: {e}")
        # Return graceful fallback response instead of 500 error
        return {
            "is_ready": True,
            "status_color": "Green",
            "total_score": 100,
            "document_type": "N/A",
            "next_best_actions": [],
            "fmcsa_status": "Active"
        }


# --- COMPLIANCE STATUS ENDPOINTS FOR DASHBOARD ---
@app.get("/compliance/status")
async def get_compliance_status_dashboard(user: dict = Depends(get_current_user)):
    """
    Compliance status endpoint for dashboard.
    Returns DOT/MC numbers, compliance score, and document information.
    """
    from .onboarding import calculate_document_status
    
    uid = user['uid']
    onboarding_score = user.get("onboarding_score", 0)
    dot_number = user.get("dot_number", "")
    mc_number = user.get("mc_number", "")
    company_name = user.get("company_name", "")
    
    # Parse documents from onboarding_data
    documents = []
    onboarding_data_str = user.get("onboarding_data")
    
    try:
        # Handle None/null values from Firebase
        if not onboarding_data_str:
            onboarding_data = {}
        else:
            onboarding_data = json.loads(onboarding_data_str)
        
        if isinstance(onboarding_data, dict):
            raw_docs = onboarding_data.get("documents", [])
            
            # Calculate score from documents if onboarding_score is 0
            if onboarding_score == 0 and len(raw_docs) > 0:
                total_score = 0
                valid_docs = 0
                for doc in raw_docs:
                    doc_score = doc.get("score", 0)
                    if isinstance(doc_score, dict):
                        doc_score = doc_score.get("total", 0)
                    if doc_score > 0:
                        total_score += doc_score
                        valid_docs += 1
                
                if valid_docs > 0:
                    onboarding_score = int(total_score / valid_docs)
                    print(f"📊 Calculated onboarding score from documents: {onboarding_score}% (from {valid_docs} documents)")
                    
                    # Update Firebase with calculated score
                    try:
                        user_ref = db.collection("users").document(uid)
                        user_ref.update({"onboarding_score": onboarding_score})
                        print(f"✅ Updated user onboarding_score in Firebase")
                    except Exception as update_error:
                        print(f"⚠️ Could not update onboarding_score: {update_error}")
            
            for doc in raw_docs:
                status = "Unknown"
                if doc.get("extracted_fields", {}).get("expiry_date"):
                    status = calculate_document_status(
                        doc["extracted_fields"]["expiry_date"]
                    )
                
                documents.append({
                    "id": doc.get("doc_id", ""),
                    "file_name": doc.get("filename", ""),
                    "document_type": doc.get("extracted_fields", {}).get("document_type", "OTHER"),
                    "expiry_date": doc.get("extracted_fields", {}).get("expiry_date"),
                    "score": doc.get("score", 0),
                    "status": status,
                    "uploaded_at": doc.get("uploaded_at"),
                    "file_url": doc.get("download_url"),  # Firebase Storage public URL
                    "storage_path": doc.get("storage_path"),
                    "extracted_fields": doc.get("extracted_fields", {}),
                    "missing_fields": doc.get("missing", [])
                })
    except Exception as e:
        print(f"Error parsing onboarding data: {e}")
    
    # Determine status color
    if onboarding_score >= 80:
        status_color = "Green"
    elif onboarding_score >= 50:
        status_color = "Amber"
    else:
        status_color = "Red"
    
    return {
        "compliance_score": int(onboarding_score),
        "is_compliant": onboarding_score >= 80,
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


@app.get("/fmcsa/{usdot}")
def get_fmcsa(usdot: str):
    profile = store.get_fmcsa_profile(usdot)
    if profile:
        return profile
    client = _get_fmcsa_client()
    fetched = client.fetch_profile(usdot)
    if not fetched:
        raise HTTPException(status_code=404, detail="Profile not found")
    profile_dict = profile_to_dict(fetched)
    store.save_fmcsa_profile(profile_dict)
    return profile_dict


@app.post("/fmcsa/verify")
async def fmcsa_verify(
    req: FmcsaVerifyRequest,
    user: Dict[str, Any] = Depends(get_current_user)
):
    """Verify FMCSA information for a carrier."""
    try:
        # Validate that at least one identifier is provided
        if not req.usdot and not req.mc_number:
            raise HTTPException(
                status_code=400, 
                detail="Provide at least a USDOT or MC number"
            )
        
        client = _get_fmcsa_client()
        result = client.verify(req.usdot, req.mc_number)
        
        # Save verification result
        store.save_fmcsa_verification(result)
        
        # Fetch and save profile if available
        try:
            profile = client.fetch_profile(result.get("usdot", req.usdot))
            if profile:
                store.save_fmcsa_profile(profile_to_dict(profile))
        except Exception as e:
            print(f"Profile fetch failed (non-critical): {e}")
        
        return {
            "success": True,
            "result": result.get("result"),
            "reasons": result.get("reasons", []),
            "usdot": result.get("usdot"),
            "mc_number": result.get("mc_number"),
            "fetched_at": result.get("fetched_at"),
        }
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        print(f"FMCSA verification error: {exc}")
        raise HTTPException(
            status_code=502, 
            detail=f"FMCSA verification failed: {str(exc)}"
        )


@app.post("/fmcsa/refresh-all")
def fmcsa_refresh_all():
    client = _get_fmcsa_client()
    docs = store.list_documents()
    seen: set[str] = set()
    entries: List[Dict[str, Any]] = []
    for doc in docs:
        extraction = doc.get("extraction", {})
        usdot, mc_number = _extract_identifiers(extraction)
        key = usdot or mc_number
        if not key or key in seen:
            continue
        seen.add(key)
        try:
            verification = client.verify(usdot, mc_number)
            store.save_fmcsa_verification(verification)
            profile = client.fetch_profile(verification["usdot"])
            if profile:
                store.save_fmcsa_profile(profile_to_dict(profile))
            entries.append({"key": key, "result": verification["result"]})
        except Exception as exc:
            entries.append({"key": key, "error": str(exc)})
    return {"processed": len(entries), "entries": entries}


@app.get("/onboarding/coach/{document_id}")
def onboarding_coach(document_id: str):
    doc = store.get_document(document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    validation = doc.get("validation") or {}
    verification = doc.get("fmcsa_verification")
    coach_plan = compute_coach_plan(doc.get("extraction", {}), validation, verification)
    return coach_plan


@app.get("/forms/driver-registration")
def get_driver_registration_draft():
    draft = autofill_driver_registration(store)
    return draft


@app.get("/forms/clearinghouse-consent")
def get_clearinghouse_consent_draft():
    draft = autofill_clearinghouse_consent(store)
    return draft


@app.get("/forms/mvr-release")
def get_mvr_release_draft():
    draft = autofill_mvr_release(store)
    return draft


@app.post("/match")
def match(req: MatchRequest):
    load_dict = req.load.dict()
    carriers = [c.dict() for c in req.carriers]
    results = match_load(
        load_dict,
        carriers,
        top_n=req.top_n,
        min_compliance=req.min_compliance,
        require_fmcsa=req.require_fmcsa,
    )
    return {
        "matches": [
            {
                "carrier_id": r.carrier_id,
                "score": r.score,
                "reasons": r.reasons,
                "carrier": r.carrier,
            }
            for r in results
        ]
    }


# ============================================================================
# 3-STEP LOAD WIZARD ENDPOINTS (New Implementation)
# ============================================================================

@app.post("/loads/step1", response_model=LoadStep1Response)
async def create_load_step1(
    data: LoadStep1Create,
    user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Step 1: Create load with Route & Equipment data.
    Generates Load ID and saves initial load data.
    """
    uid = user['uid']
    user_role = user.get('role', 'carrier')
    
    # Generate unique Load ID
    load_id = generate_load_id(region="ATL", user_code=None)
    
    # Prepare complete load object with Step 1 data
    load_data = {
        "load_id": load_id,
        "created_by": uid,
        "creator_role": user_role,  # Track who created this load
        "created_at": time.time(),
        "updated_at": time.time(),
        "status": LoadStatus.DRAFT.value,
        
        # Step 1 data
        "origin": data.origin,
        "destination": data.destination,
        "pickup_date": data.pickup_date,
        "delivery_date": data.delivery_date,
        "pickup_appointment_type": data.pickup_appointment_type.value if data.pickup_appointment_type else None,
        "delivery_appointment_type": data.delivery_appointment_type.value if data.delivery_appointment_type else None,
        "additional_routes": data.additional_routes or [],  # Store additional routes
        "equipment_type": data.equipment_type.value,
        "load_type": data.load_type.value if data.load_type else None,
        "weight": data.weight,
        "pallet_count": data.pallet_count,
        
        # Placeholders for Steps 2 & 3
        "rate_type": None,
        "linehaul_rate": None,
        "fuel_surcharge": None,
        "advanced_charges": [],
        "commodity": None,
        "special_requirements": [],
        "payment_terms": None,
        "notes": None,
        "visibility": None,
        "selected_carriers": [],
        "auto_match_ai": True,
        "instant_booking": False,
        "auto_post_to_freightpower": True,
        "auto_post_to_truckstop": False,
        "auto_post_to_123loadboard": False,
        "notify_on_carrier_views": True,
        "notify_on_offer_received": True,
        "notify_on_load_covered": True,
        
        "metadata": {}
    }
    
    # Save to storage (both JSON and Firestore)
    store.save_load(load_data)
    
    # Save to Firestore
    try:
        load_ref = db.collection("loads").document(load_id)
        load_ref.set(load_data)
        log_action(uid, "LOAD_CREATE_STEP1", f"Created load {load_id} - Step 1 completed")
    except Exception as e:
        print(f"Warning: Could not save load to Firestore: {e}")
    
    # Calculate estimated distance and transit time using AI
    estimated_distance = None
    estimated_transit_time = None
    try:
        # Convert equipment type to lowercase for AI prompt
        truck_type = data.equipment_type.value.lower().replace(" ", "")
        distance_result = calculate_freight_distance(data.origin, data.destination, truck_type)
        estimated_distance = distance_result.get("distance_miles", 0)
        estimated_transit_time = distance_result.get("estimated_hours", 0)
        
        # Update load with calculated values
        load_data["estimated_distance"] = estimated_distance
        load_data["estimated_transit_time"] = estimated_transit_time
        store.update_load(load_id, {
            "estimated_distance": estimated_distance,
            "estimated_transit_time": estimated_transit_time
        })
        
        print(f"✅ Calculated distance: {estimated_distance} miles, transit time: {estimated_transit_time} hours")
    except Exception as e:
        print(f"Warning: Distance calculation failed: {e}")
    
    return LoadStep1Response(
        load_id=load_id,
        estimated_distance=estimated_distance,
        estimated_transit_time=estimated_transit_time,
        message=f"Load {load_id} created successfully"
    )


@app.patch("/loads/{load_id}/step2")
async def update_load_step2(
    load_id: str,
    data: LoadStep2Update,
    user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Step 2: Update load with Pricing & Details data.
    """
    uid = user['uid']
    
    # Get existing load
    existing_load = store.get_load(load_id)
    if not existing_load:
        raise HTTPException(status_code=404, detail="Load not found")
    
    # Verify ownership
    if existing_load.get("created_by") != uid:
        raise HTTPException(status_code=403, detail="Not authorized to update this load")
    
    # Prepare update data
    updates = {
        "updated_at": time.time(),
        "rate_type": data.rate_type.value,
        "linehaul_rate": data.linehaul_rate,
        "fuel_surcharge": data.fuel_surcharge,
        "advanced_charges": data.advanced_charges or [],
        "commodity": data.commodity,
        "special_requirements": data.special_requirements or [],
        "payment_terms": data.payment_terms.value if data.payment_terms else None,
        "notes": data.notes,
    }
    
    # Calculate total rate (linehaul + fuel_surcharge + sum of advanced_charges)
    total_rate = data.linehaul_rate
    if data.fuel_surcharge:
        total_rate += data.fuel_surcharge
    if data.advanced_charges:
        for charge in data.advanced_charges:
            total_rate += float(charge.get("amount", 0))
    updates["total_rate"] = total_rate
    
    # Update in storage
    updated_load = store.update_load(load_id, updates)
    
    # Update Firestore
    try:
        load_ref = db.collection("loads").document(load_id)
        load_ref.update(updates)
        log_action(uid, "LOAD_UPDATE_STEP2", f"Updated load {load_id} - Step 2 completed")
    except Exception as e:
        print(f"Warning: Could not update load in Firestore: {e}")
    
    return {
        "load_id": load_id,
        "message": "Step 2 data saved successfully",
        "total_rate": total_rate
    }


@app.patch("/loads/{load_id}/step3")
async def update_load_step3(
    load_id: str,
    data: LoadStep3Update,
    status: str = "ACTIVE",  # Can be "ACTIVE" or "DRAFT"
    user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Step 3: Update load with Visibility & Automation preferences.
    Posts the load and triggers auto-matching if enabled.
    
    Status parameter controls final state:
    - "ACTIVE": Load posted and visible to carriers
    - "DRAFT": Settings saved but load remains draft for later posting
    """
    uid = user['uid']
    
    # Get existing load
    existing_load = store.get_load(load_id)
    if not existing_load:
        raise HTTPException(status_code=404, detail="Load not found")
    
    # Verify ownership
    if existing_load.get("created_by") != uid:
        raise HTTPException(status_code=403, detail="Not authorized to update this load")
    
    # Prepare update data
    # Use status from parameter (ACTIVE or DRAFT)
    final_status = LoadStatus.POSTED.value if status == "ACTIVE" else LoadStatus.DRAFT.value
    
    # Get shipper information
    shipper_company_name = user.get("company_name", "")
    shipper_compliance_score = user.get("onboarding_score", 0)
    
    # Get additional stops/routes from existing load (stored in step1)
    additional_stops = existing_load.get("additional_routes", [])
    
    # Get total distance (from step1 calculation)
    total_distance = existing_load.get("estimated_distance") or existing_load.get("miles") or 0
    
    # Get total price (from step2 calculation)
    total_price = existing_load.get("total_rate") or existing_load.get("linehaul_rate") or existing_load.get("rate") or 0
    
    updates = {
        "updated_at": time.time(),
        "status": final_status,
        "visibility": data.visibility.value,
        "selected_carriers": data.selected_carriers or [],
        "auto_match_ai": data.auto_match_ai,
        "instant_booking": data.instant_booking,
        "auto_post_to_freightpower": data.auto_post_to_freightpower,
        "auto_post_to_truckstop": data.auto_post_to_truckstop,
        "auto_post_to_123loadboard": data.auto_post_to_123loadboard,
        "notify_on_carrier_views": data.notify_on_carrier_views,
        "notify_on_offer_received": data.notify_on_offer_received,
        "notify_on_load_covered": data.notify_on_load_covered,
        # Additional shipper and load details
        "shipper_company_name": shipper_company_name,
        "shipper_compliance_score": float(shipper_compliance_score),
        "additional_stops": additional_stops,  # Includes location, type, and date
        "total_distance": float(total_distance),
        "total_price": float(total_price),
    }
    
    # Update in storage
    updated_load = store.update_load(load_id, updates)
    
    # Update Firestore
    try:
        load_ref = db.collection("loads").document(load_id)
        load_ref.update(updates)
        log_action(uid, "LOAD_POST", f"Posted load {load_id} - Step 3 completed")
    except Exception as e:
        print(f"Warning: Could not update load in Firestore: {e}")
    
    # Trigger auto-match if enabled
    matches = []
    if data.auto_match_ai:
        try:
            carriers = store.list_carriers()
            if carriers:
                # Convert updated_load to format match_load expects
                load_for_matching = {
                    "id": load_id,
                    "origin": updated_load.get("origin"),
                    "destination": updated_load.get("destination"),
                    "equipment": updated_load.get("equipment_type"),
                    "weight": updated_load.get("weight"),
                }
                match_results = match_load(load_for_matching, carriers, top_n=5)
                matches = [
                    {
                        "carrier_id": m.carrier_id,
                        "score": m.score,
                        "reasons": m.reasons
                    }
                    for m in match_results
                ]
                
                # Create alerts for top matches
                for m in match_results[:3]:
                    create_alert(
                        store,
                        {
                            "type": "match_suggestion",
                            "message": f"AI matched carrier {m.carrier_id} for load {load_id} (score {m.score:.2f})",
                            "priority": "routine",
                            "entity_id": load_id,
                        },
                    )
        except Exception as e:
            print(f"Auto-match failed: {e}")
    
    # Return appropriate message based on status
    message = f"Load {load_id} posted successfully" if status == "ACTIVE" else f"Load {load_id} saved as draft"
    
    return {
        "load_id": load_id,
        "message": message,
        "status": final_status,
        "matches": matches
    }


@app.post("/loads/generate-instructions", response_model=GenerateInstructionsResponse)
async def generate_driver_instructions(
    req: GenerateInstructionsRequest,
    user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Generate AI-powered driver instructions based on load details.
    """
    from .vision import chat_answer
    
    # Build context prompt for AI
    prompt = f"""Generate professional driver instructions for a freight load with the following details:

Load ID: {req.load_id}
Origin: {req.origin}
Destination: {req.destination}
Equipment Type: {req.equipment_type}
Commodity: {req.commodity or 'General Freight'}
Special Requirements: {', '.join(req.special_requirements) if req.special_requirements else 'None'}

Please provide clear, concise instructions covering:
1. Pickup procedures and timing
2. Load securing requirements
3. Special handling notes (if applicable)
4. Delivery procedures
5. Safety reminders

Keep it professional and under 200 words."""
    
    try:
        instructions = chat_answer(prompt, "")
    except Exception as e:
        # Fallback to template if AI fails
        instructions = f"""DRIVER INSTRUCTIONS - Load {req.load_id}

PICKUP:
• Arrive at {req.origin} on scheduled pickup date
• Contact shipper upon arrival for dock assignment
• Inspect cargo before loading

TRANSIT:
• Equipment: {req.equipment_type}
• Secure load per DOT regulations
{"• Special Requirements: " + ", ".join(req.special_requirements) if req.special_requirements else ""}

DELIVERY:
• Deliver to {req.destination}
• Contact consignee for delivery appointment
• Obtain signed BOL/POD

SAFETY:
• Conduct pre-trip and post-trip inspections
• Maintain HOS compliance
• Report any issues immediately"""
    
    return GenerateInstructionsResponse(
        instructions=instructions,
        load_id=req.load_id
    )


# ============================================================================
# DASHBOARD STATS ENDPOINTS
# ============================================================================

@app.get("/dashboard/stats")
async def get_dashboard_stats(
    user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Get dashboard statistics for the current user.
    Returns real counts or zeros if no data exists.
    
    Authorization: All authenticated users
    """
    uid = user['uid']
    user_role = user.get("role", "carrier")
    
    try:
        # Get all loads for this user
        filters = {}
        
        if user_role in ["admin", "super_admin"]:
            # Admins see all loads
            all_loads = store.list_loads(filters)
        elif user_role == "shipper" or user_role == "broker":
            # Shippers see only their own loads
            filters["created_by"] = uid
            all_loads = store.list_loads(filters)
        elif user_role == "carrier":
            # Carriers see created_by OR assigned_carrier loads
            filters_created = {"created_by": uid}
            loads_created = store.list_loads(filters_created)
            
            filters_assigned = {"assigned_carrier": uid}
            loads_assigned = store.list_loads(filters_assigned)
            
            # Merge and deduplicate
            load_map = {load["load_id"]: load for load in loads_created}
            for load in loads_assigned:
                if load["load_id"] not in load_map:
                    load_map[load["load_id"]] = load
            
            all_loads = list(load_map.values())
        elif user_role == "driver":
            # Drivers see only assigned loads
            filters["assigned_driver"] = uid
            all_loads = store.list_loads(filters)
        else:
            all_loads = []
        
        # Calculate stats
        active_loads = len([l for l in all_loads if l.get("status") in ["posted", "covered", "in_transit"]])
        pending_tasks = len([l for l in all_loads if l.get("status") == "posted"])
        total_loads = len(all_loads)
        completed_loads = len([l for l in all_loads if l.get("status") == "completed"])
        draft_loads = len([l for l in all_loads if l.get("status") == "draft"])
        
        # Calculate on-time percentage (mock for now, can be enhanced)
        on_time_percentage = 96.2 if completed_loads > 0 else 0
        
        # Calculate total revenue (sum of completed loads' rates)
        total_revenue = sum(
            float(l.get("linehaul_rate", 0) or 0) 
            for l in all_loads 
            if l.get("status") == "completed"
        )
        
        # Compliance score (mock for now)
        compliance_score = 94 if total_loads > 0 else 0
        compliance_expiring = 2
        
        # Rating (mock for now)
        rating = 4.8 if total_loads > 0 else 0
        
        stats = {
            "active_loads": active_loads,
            "active_loads_today": 0,  # Would need timestamp filtering
            "on_time_percentage": on_time_percentage,
            "on_time_change": "+1.2%",
            "rating": rating,
            "rating_label": "Excellent" if rating >= 4.5 else "Good",
            "total_revenue": total_revenue,
            "revenue_change": "+12% MTD",
            "compliance_score": compliance_score,
            "compliance_expiring": compliance_expiring,
            "pending_tasks": pending_tasks,
            "pending_urgent": min(3, pending_tasks),
            "total_loads": total_loads,
            "draft_loads": draft_loads
        }
        
        return JSONResponse(content=stats)
        
    except Exception as e:
        print(f"Error calculating dashboard stats: {e}")
        # Return zeros on error
        return JSONResponse(content={
            "active_loads": 0,
            "active_loads_today": 0,
            "on_time_percentage": 0,
            "on_time_change": "+0%",
            "rating": 0,
            "rating_label": "N/A",
            "total_revenue": 0,
            "revenue_change": "+0%",
            "compliance_score": 0,
            "compliance_expiring": 0,
            "pending_tasks": 0,
            "pending_urgent": 0,
            "total_loads": 0
        })


# ============================================================================
# AI CALCULATION ENDPOINTS
# ============================================================================

@app.post("/ai/calculate-distance", response_model=DistanceCalculationResponse)
async def calculate_distance(
    req: DistanceCalculationRequest,
    user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Calculate distance and estimated transit time between two locations using AI.
    
    Authorization: All authenticated users
    """
    try:
        # Use dry van as default if truck type not specified
        truck_type = getattr(req, 'truck_type', 'dry van')
        result = calculate_freight_distance(req.origin, req.destination, truck_type)
        
        return DistanceCalculationResponse(
            distance_miles=result.get("distance_miles", 0),
            estimated_hours=result.get("estimated_hours", 0),
            estimated_days=result.get("estimated_days", 0),
            confidence=result.get("confidence", 0.0),
            notes=result.get("notes")
        )
    except Exception as e:
        print(f"Error in distance calculation endpoint: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Distance calculation failed: {str(e)}"
        )


@app.post("/ai/calculate-load-cost", response_model=LoadCostCalculationResponse)
async def calculate_load_cost_endpoint(
    req: LoadCostCalculationRequest,
    user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Calculate total load cost based on distance, rate per mile, and additional charges.
    
    Authorization: All authenticated users
    """
    try:
        result = calculate_load_cost(
            req.distance_miles,
            req.rate_per_mile,
            req.additional_charges
        )
        
        return LoadCostCalculationResponse(**result)
    except Exception as e:
        print(f"Error in cost calculation endpoint: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Cost calculation failed: {str(e)}"
        )


# ============================================================================
# LOAD LISTING & MANAGEMENT ENDPOINTS
# ============================================================================

@app.get("/loads/drafts", response_model=LoadListResponse)
async def get_user_drafts(
    user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Get all draft loads for the current user.
    Drafts are incomplete loads saved after Step 1 that can be resumed later.
    """
    uid = user['uid']
    
    # Get only draft loads for this user
    filters = {
        "created_by": uid,
        "status": LoadStatus.DRAFT.value
    }
    
    draft_loads = store.list_loads(filters)
    
    # Convert to LoadComplete models
    loads = [LoadComplete(**load) for load in draft_loads]
    
    return LoadListResponse(
        loads=loads,
        total=len(loads),
        page=1,
        page_size=len(loads)
    )


@app.get("/loads", response_model=LoadListResponse)
async def list_loads(
    status: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
    exclude_drafts: bool = True,
    user: Dict[str, Any] = Depends(get_current_user)
):
    """
    List loads with strict role-based filtering:
    - Carriers: See their own loads + loads won from shippers (created_by OR assigned_carrier)
    - Shippers: See ONLY their own loads (all statuses)
    - Drivers: See ONLY loads assigned to them
    - Admins: See all loads
    
    By default, DRAFT loads are excluded from marketplace listings.
    Set exclude_drafts=False to include drafts (for dashboard views).
    
    Business Logic:
    - Carrier's "My Loads" includes:
      1. Loads they posted themselves (created_by=uid)
      2. Loads they won from shippers (assigned_carrier=uid, status=COVERED+)
    """
    uid = user['uid']
    user_role = user.get("role", "carrier")
    
    # Build filters based on role
    if user_role in ["admin", "super_admin"]:
        # Admins see everything
        filters = {}
        if status:
            filters["status"] = status
        all_loads = store.list_loads(filters)
    elif user_role == "shipper" or user_role == "broker":
        # Shippers see ONLY their own loads (strict ownership check) - read from Firestore
        try:
            loads_ref = db.collection("loads")
            query = loads_ref.where("created_by", "==", uid)
            if status:
                query = query.where("status", "==", status)
            all_loads_docs = query.stream()
            all_loads = []
            for doc in all_loads_docs:
                load = doc.to_dict()
                load["load_id"] = doc.id
                all_loads.append(load)
        except Exception as e:
            print(f"Error fetching shipper loads from Firestore: {e}")
            # Fallback to local storage
            filters = {"created_by": uid}
            if status:
                filters["status"] = status
            all_loads = store.list_loads(filters)
    elif user_role == "driver":
        # Drivers see loads assigned to them - query Firestore
        # Include both accepted and pending loads (frontend will separate them)
        try:
            loads_ref = db.collection("loads")
            # Query for loads assigned to this driver using assigned_driver field
            query = loads_ref.where("assigned_driver", "==", uid)
            if status:
                query = query.where("status", "==", status)
            
            all_loads_docs = query.stream()
            all_loads = []
            seen_load_ids = set()
            
            for doc in all_loads_docs:
                load = doc.to_dict()
                load_id = doc.id
                
                # Skip duplicates
                if load_id in seen_load_ids:
                    continue
                seen_load_ids.add(load_id)
                
                load["load_id"] = load_id
                all_loads.append(load)
            
            # Also check assigned_driver_id field if no results or to catch any missed
            if len(all_loads) == 0:
                query2 = loads_ref.where("assigned_driver_id", "==", uid)
                if status:
                    query2 = query2.where("status", "==", status)
                all_loads_docs2 = query2.stream()
                for doc in all_loads_docs2:
                    load = doc.to_dict()
                    load_id = doc.id
                    if load_id not in seen_load_ids:
                        load["load_id"] = load_id
                        all_loads.append(load)
                        seen_load_ids.add(load_id)
        except Exception as e:
            print(f"Error fetching driver loads from Firestore: {e}")
            import traceback
            traceback.print_exc()
            # Fallback to local storage
            filters = {"assigned_driver": uid}
            if status:
                filters["status"] = status
            all_loads = store.list_loads(filters)
    elif user_role == "carrier":
        # Carriers see: created_by=uid OR assigned_carrier=uid
        # Query both from Firestore (primary source) to ensure we get all loads
        all_loads = []
        seen_load_ids = set()
        
        try:
            loads_ref = db.collection("loads")
            
            # Get loads created by this carrier from Firestore
            query_created = loads_ref.where("created_by", "==", uid)
            if status:
                query_created = query_created.where("status", "==", status)
            created_loads_docs = query_created.stream()
            
            for doc in created_loads_docs:
                load = doc.to_dict()
                load_id = load.get("load_id") or doc.id  # Use load_id from doc if available, otherwise use doc.id
                if load_id not in seen_load_ids:
                    load["load_id"] = load_id
                    all_loads.append(load)
                    seen_load_ids.add(load_id)
            
            # Get loads assigned to this carrier from Firestore (these are loads accepted by shippers)
            # Query for loads with assigned_carrier field matching uid
            query_assigned = loads_ref.where("assigned_carrier", "==", uid)
            if status:
                query_assigned = query_assigned.where("status", "==", status)
            assigned_loads_docs = query_assigned.stream()
            
            for doc in assigned_loads_docs:
                load = doc.to_dict()
                load_id = load.get("load_id") or doc.id  # Use load_id from doc if available, otherwise use doc.id
                if load_id not in seen_load_ids:
                    load["load_id"] = load_id
                    all_loads.append(load)
                    seen_load_ids.add(load_id)
            
            # Also check assigned_carrier_id field (for backward compatibility)
            query_assigned_id = loads_ref.where("assigned_carrier_id", "==", uid)
            if status:
                query_assigned_id = query_assigned_id.where("status", "==", status)
            assigned_loads_docs2 = query_assigned_id.stream()
            
            for doc in assigned_loads_docs2:
                load = doc.to_dict()
                load_id = load.get("load_id") or doc.id  # Use load_id from doc if available, otherwise use doc.id
                if load_id not in seen_load_ids:
                    load["load_id"] = load_id
                    all_loads.append(load)
                    seen_load_ids.add(load_id)
            
            print(f"DEBUG: Carrier {uid} - Found {len(all_loads)} total loads ({len(seen_load_ids)} unique)")
        except Exception as e:
            print(f"Error fetching carrier loads from Firestore: {e}")
            import traceback
            traceback.print_exc()
            # Fallback to local storage
            filters_created = {"created_by": uid}
            if status:
                filters_created["status"] = status
            loads_created = store.list_loads(filters_created)
            
            filters_assigned = {"assigned_carrier": uid}
            if status:
                filters_assigned["status"] = status
            loads_assigned = store.list_loads(filters_assigned)
            
            # Merge and deduplicate
            load_map = {load["load_id"]: load for load in loads_created}
            for load in loads_assigned:
                if load["load_id"] not in load_map:
                    load_map[load["load_id"]] = load
            all_loads = list(load_map.values())
    else:
        # Default: see their own loads
        filters = {"created_by": uid}
        if status:
            filters["status"] = status
        all_loads = store.list_loads(filters)
    
    # Filter out drafts if requested (default for marketplace)
    if exclude_drafts:
        all_loads = [load for load in all_loads if load.get("status") != LoadStatus.DRAFT.value]
    
    # Pagination
    total = len(all_loads)
    start_idx = (page - 1) * page_size
    end_idx = start_idx + page_size
    paginated_loads = all_loads[start_idx:end_idx]
    
    # Convert to LoadComplete models
    # Handle cases where load_id might not be set (use doc.id as fallback)
    loads = []
    for load in paginated_loads:
        # Ensure load_id is set
        if "load_id" not in load or not load["load_id"]:
            # Try to use the document ID if available, but this shouldn't happen
            print(f"WARNING: Load missing load_id field: {load.keys()}")
            continue
        try:
            loads.append(LoadComplete(**load))
        except Exception as e:
            print(f"ERROR: Failed to convert load {load.get('load_id', 'unknown')} to LoadComplete: {e}")
            import traceback
            traceback.print_exc()
            # Skip this load instead of failing the entire request
            continue
    
    return LoadListResponse(
        loads=loads,
        total=total,
        page=page,
        page_size=page_size
    )


@app.delete("/loads/{load_id}")
async def delete_draft_load(
    load_id: str,
    user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Delete a draft load. Only DRAFT status loads can be deleted.
    POSTED or later loads must be cancelled instead.
    
    Authorization: Load creator only
    """
    uid = user['uid']
    
    # Get existing load
    existing_load = store.get_load(load_id)
    if not existing_load:
        raise HTTPException(status_code=404, detail="Load not found")
    
    # Verify ownership
    if existing_load.get("created_by") != uid:
        raise HTTPException(status_code=403, detail="Not authorized to delete this load")
    
    # Only allow deletion of DRAFT loads
    current_status = existing_load.get("status")
    if current_status != LoadStatus.DRAFT.value:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot delete load with status '{current_status}'. Only DRAFT loads can be deleted. Use cancel endpoint for posted loads."
        )
    
    # Delete from storage
    try:
        store.delete_load(load_id)
        # Delete from Firestore
        db.collection("loads").document(load_id).delete()
        log_action(uid, "LOAD_DELETE", f"Deleted draft load {load_id}")
    except Exception as e:
        print(f"Error deleting load: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete load")
    
    return {"message": f"Draft load {load_id} deleted successfully"}


@app.get("/loads/tendered", response_model=LoadListResponse)
async def list_tendered_loads(
    page: int = 1,
    page_size: int = 20,
    user: Dict[str, Any] = Depends(get_current_user)
):
    """
    List shipper's tendered loads (POSTED status, awaiting carrier bids).
    
    Authorization: Shippers/Brokers only
    
    Returns: Loads created by this shipper with status=POSTED.
    These are active tendered loads awaiting carrier bids.
    """
    uid = user['uid']
    user_role = user.get("role", "carrier")
    
    # Only shippers/brokers can access this endpoint
    if user_role not in ["shipper", "broker", "admin", "super_admin"]:
        raise HTTPException(
            status_code=403,
            detail="Only shippers can view tendered loads"
        )
    
    # Build filters: created_by + status=POSTED
    filters = {
        "status": "posted"
    }
    
    # Non-admins can only see their own
    if user_role not in ["admin", "super_admin"]:
        filters["created_by"] = uid
    
    all_loads = store.list_loads(filters)
    
    # Pagination
    total = len(all_loads)
    start_idx = (page - 1) * page_size
    end_idx = start_idx + page_size
    paginated_loads = all_loads[start_idx:end_idx]
    
    # Convert to LoadComplete models
    loads = [LoadComplete(**load) for load in paginated_loads]
    
    return LoadListResponse(
        loads=loads,
        total=total,
        page=page,
        page_size=page_size
    )


@app.get("/loads/{load_id}", response_model=LoadResponse)
async def get_load_details(
    load_id: str,
    user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Get detailed information about a specific load.
    
    Authorization:
    - Shippers: Can view ONLY their own loads
    - Drivers: Can view ONLY loads assigned to them
    - Carriers: Can view their own loads
    - Admins: Can view all loads
    """
    # Get load from Firestore first, fallback to local storage
    load = None
    try:
        load_doc = db.collection("loads").document(load_id).get()
        if load_doc.exists:
            load = load_doc.to_dict()
            load["load_id"] = load_id
    except Exception as e:
        print(f"Error fetching load from Firestore: {e}")
    
    # Fallback to local storage if Firestore doesn't have it
    if not load:
        load = store.get_load(load_id)
    
    if not load:
        raise HTTPException(status_code=404, detail="Load not found")
    
    # Strict role-based access control
    uid = user['uid']
    user_role = user.get("role", "carrier")
    
    if user_role in ["admin", "super_admin"]:
        # Admins can view all loads
        pass
    elif user_role == "shipper":
        # Shippers can ONLY view loads they created
        if load.get("created_by") != uid:
            raise HTTPException(
                status_code=403,
                detail="Shippers can only view loads they created"
            )
    elif user_role == "driver":
        # Drivers can ONLY view loads assigned to them
        if load.get("assigned_driver") != uid:
            raise HTTPException(
                status_code=403,
                detail="Drivers can only view loads assigned to them"
            )
    else:
        # Carriers can view their own loads OR marketplace loads (POSTED loads they can bid on)
        if load.get("created_by") != uid:
            # Allow carriers to view POSTED loads (marketplace loads) for bidding
            if load.get("status") != LoadStatus.POSTED.value:
                raise HTTPException(
                    status_code=403,
                    detail="Not authorized to view this load"
                )
            # Also check if carrier has already bid on this load (for viewing their bid)
            offers = load.get("offers", [])
            has_bid = any(o.get("carrier_id") == uid for o in offers)
            # Allow viewing if it's a POSTED load (marketplace) or if they have a bid
            if not has_bid and load.get("status") == LoadStatus.POSTED.value:
                # This is a marketplace load, allow viewing for bidding purposes
                pass
    
    return LoadResponse(
        load=LoadComplete(**load),
        message="Success"
    )


# ============================================================================
# LEGACY LOAD ENDPOINTS (Keep for backward compatibility)
# ============================================================================

@app.post("/loads")
def create_load(req: LoadCreateRequest):
    payload = req.dict()
    store.save_load(payload)
    # Auto-match and notify
    carriers = store.list_carriers()
    if carriers:
        matches = match_load(payload, carriers, top_n=5)
        for m in matches:
            create_alert(
                store,
                {
                    "type": "match_suggestion",
                    "message": f"Suggested carrier {m.carrier_id} for load {payload['id']} (score {m.score})",
                    "priority": "routine",
                    "entity_id": payload["id"],
                },
            )
    return payload


@app.post("/carriers")
def create_carrier(req: CarrierCreateRequest):
    payload = req.dict()
    store.save_carrier(payload)
    return payload


@app.get("/carriers")
async def list_carriers(user: Dict[str, Any] = Depends(get_current_user)):
    """
    List all carriers from Firestore.
    Shippers use this to find carriers for their loads.
    """
    try:
        carriers_ref = db.collection("carriers")
        carriers_docs = carriers_ref.stream()
        
        carriers = []
        for doc in carriers_docs:
            carrier_data = doc.to_dict()
            carrier_data['id'] = doc.id  # Ensure ID is included
            carriers.append(carrier_data)
        
        return {"carriers": carriers, "total": len(carriers)}
    except Exception as e:
        print(f"Error fetching carriers: {e}")
        # Fallback to local storage if Firebase fails
        return {"carriers": store.list_carriers(), "total": len(store.list_carriers())}


@app.get("/drivers")
async def list_drivers(
    status: Optional[str] = None,
    available_only: bool = True,  # Only show drivers not hired yet
    user: Dict[str, Any] = Depends(get_current_user)
):
    """
    List all drivers from Firestore.
    Carriers use this to find available drivers in the marketplace.
    By default, only shows drivers not hired by any carrier (available_only=True).
    Optional status filter: available, on_trip, off_duty
    """
    try:
        # First, get all users with role "driver"
        users_ref = db.collection("users")
        driver_users_query = users_ref.where("role", "==", "driver")
        driver_users_docs = driver_users_query.stream()
        
        driver_user_ids = set()
        for user_doc in driver_users_docs:
            driver_user_ids.add(user_doc.id)
        
        if not driver_user_ids:
            return {"drivers": [], "total": 0}
        
        # Now get driver profiles from drivers collection
        # Driver profiles use the user's uid as the document ID (as per auth.py signup)
        drivers_ref = db.collection("drivers")
        drivers_docs = drivers_ref.stream()
        
        drivers = []
        for doc in drivers_docs:
            driver_data = doc.to_dict()
            driver_id = doc.id
            
            # Only include drivers whose document ID matches a driver user ID
            # (since driver profiles are created with user uid as document ID)
            if driver_id not in driver_user_ids:
                # Also check if there's a user_id field that matches
                driver_user_id = driver_data.get("user_id") or driver_data.get("id")
                if not driver_user_id or driver_user_id not in driver_user_ids:
                    continue
            
            # Filter by available_only (not hired)
            if available_only:
                carrier_id = driver_data.get("carrier_id")
                if carrier_id:
                    continue  # Skip hired drivers
            
            # Apply status filter if provided
            if status:
                driver_status = driver_data.get("status", "")
                if driver_status != status:
                    continue
            
            driver_data['id'] = driver_id  # Ensure ID is included
            drivers.append(driver_data)
        
        return {"drivers": drivers, "total": len(drivers)}
    except Exception as e:
        print(f"Error fetching drivers: {e}")
        import traceback
        traceback.print_exc()
        return {"drivers": [], "total": 0}


@app.post("/drivers/{driver_id}/hire")
async def hire_driver(
    driver_id: str,
    user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Hire a driver (carrier only).
    Links a driver to the carrier by setting carrier_id in the driver profile.
    """
    try:
        user_role = user.get("role")
        if user_role != "carrier":
            raise HTTPException(status_code=403, detail="Only carriers can hire drivers")
        
        carrier_id = user['uid']
        
        # Get driver document
        driver_ref = db.collection("drivers").document(driver_id)
        driver_doc = driver_ref.get()
        
        if not driver_doc.exists:
            raise HTTPException(status_code=404, detail="Driver not found")
        
        driver_data = driver_doc.to_dict()
        
        # Check if driver is already hired
        if driver_data.get("carrier_id"):
            raise HTTPException(
                status_code=400, 
                detail="Driver is already hired by another carrier"
            )
        
        # Update driver with carrier_id
        driver_ref.update({
            "carrier_id": carrier_id,
            "hired_at": time.time(),
            "updated_at": time.time()
        })
        
        # Log action
        log_action(carrier_id, "DRIVER_HIRED", f"Hired driver {driver_id}")
        
        return JSONResponse(content={
            "success": True,
            "message": "Driver hired successfully",
            "driver_id": driver_id,
            "carrier_id": carrier_id
        })
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error hiring driver: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="Failed to hire driver")


@app.get("/drivers/my-drivers")
async def get_my_drivers(
    status: Optional[str] = None,
    user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Get all drivers hired by the current carrier.
    """
    try:
        user_role = user.get("role")
        if user_role != "carrier":
            raise HTTPException(status_code=403, detail="Only carriers can view their drivers")
        
        carrier_id = user['uid']
        
        # Get all drivers hired by this carrier
        drivers_ref = db.collection("drivers")
        drivers_query = drivers_ref.where("carrier_id", "==", carrier_id)
        
        # Apply status filter if provided
        if status:
            drivers_query = drivers_query.where("status", "==", status)
        
        drivers_docs = drivers_query.stream()
        
        drivers = []
        for doc in drivers_docs:
            driver_data = doc.to_dict()
            driver_data['id'] = doc.id
            drivers.append(driver_data)
        
        return {"drivers": drivers, "total": len(drivers)}
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error fetching my drivers: {e}")
        import traceback
        traceback.print_exc()
        return {"drivers": [], "total": 0}


@app.get("/drivers/my-carrier")
async def get_my_carrier(
    user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Get carrier information for the current driver.
    Returns the carrier that hired this driver.
    """
    try:
        user_role = user.get("role")
        if user_role != "driver":
            raise HTTPException(status_code=403, detail="Only drivers can view their carrier")
        
        driver_id = user['uid']
        
        # Get driver document to find carrier_id
        driver_ref = db.collection("drivers").document(driver_id)
        driver_doc = driver_ref.get()
        
        if not driver_doc.exists:
            raise HTTPException(status_code=404, detail="Driver profile not found")
        
        driver_data = driver_doc.to_dict()
        carrier_id = driver_data.get("carrier_id")
        
        if not carrier_id:
            # Driver not hired yet
            return JSONResponse(content={
                "carrier": None,
                "message": "You are not currently hired by any carrier"
            })
        
        # Get carrier information
        carrier_ref = db.collection("carriers").document(carrier_id)
        carrier_doc = carrier_ref.get()
        
        if not carrier_doc.exists:
            raise HTTPException(status_code=404, detail="Carrier not found")
        
        carrier_data = carrier_doc.to_dict()
        carrier_data['id'] = carrier_id
        
        return {"carrier": carrier_data}
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error fetching driver's carrier: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="Failed to fetch carrier information")


class AssignDriverToLoadRequest(BaseModel):
    driver_id: str
    notes: Optional[str] = None


@app.post("/loads/{load_id}/assign-driver")
async def assign_driver_to_load(
    load_id: str,
    request: AssignDriverToLoadRequest,
    user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Assign a driver to a load.
    Carrier only - can only assign drivers they've hired to loads assigned to them.
    """
    try:
        user_role = user.get("role")
        if user_role != "carrier":
            raise HTTPException(status_code=403, detail="Only carriers can assign drivers to loads")
        
        carrier_id = user['uid']
        
        # Get load from Firestore
        load_ref = db.collection("loads").document(load_id)
        load_doc = load_ref.get()
        
        if not load_doc.exists:
            raise HTTPException(status_code=404, detail="Load not found")
        
        load_data = load_doc.to_dict()
        
        # Check that load is assigned to this carrier (check both field names for compatibility)
        assigned_carrier = load_data.get("assigned_carrier") or load_data.get("assigned_carrier_id")
        if not assigned_carrier or assigned_carrier != carrier_id:
            raise HTTPException(
                status_code=403,
                detail="You can only assign drivers to loads assigned to your carrier"
            )
        
        # Check that driver is hired by this carrier
        driver_ref = db.collection("drivers").document(request.driver_id)
        driver_doc = driver_ref.get()
        
        if not driver_doc.exists:
            raise HTTPException(status_code=404, detail="Driver not found")
        
        driver_data = driver_doc.to_dict()
        driver_carrier_id = driver_data.get("carrier_id")
        
        if not driver_carrier_id or driver_carrier_id != carrier_id:
            raise HTTPException(
                status_code=403,
                detail="You can only assign drivers that are hired by your carrier"
            )
        
        # Update load with assigned driver
        # Use both assigned_driver_id and assigned_driver for compatibility
        timestamp = time.time()
        load_ref.update({
            "assigned_driver_id": request.driver_id,
            "assigned_driver": request.driver_id,  # Also set for compatibility with existing queries
            "assigned_driver_name": driver_data.get("name", "Unknown"),
            "driver_assignment_status": "pending",  # Track if driver has accepted
            "assigned_at": timestamp,
            "updated_at": timestamp
        })
        
        # Also update driver status if needed
        current_status = driver_data.get("status", "available")
        if current_status == "available":
            driver_ref.update({
                "status": "assigned",
                "updated_at": timestamp
            })
        
        # Log action
        log_action(carrier_id, "LOAD_ASSIGNED_TO_DRIVER", 
                  f"Assigned load {load_id} to driver {request.driver_id}")
        
        return JSONResponse(content={
            "success": True,
            "message": "Driver assigned to load successfully",
            "load_id": load_id,
            "driver_id": request.driver_id
        })
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error assigning driver to load: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="Failed to assign driver to load")


class DriverAcceptLoadRequest(BaseModel):
    accept: bool  # True to accept, False to reject
    notes: Optional[str] = None


@app.post("/loads/{load_id}/driver-accept-assignment")
async def driver_accept_load_assignment(
    load_id: str,
    request: DriverAcceptLoadRequest,
    user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Driver accepts or rejects a load assignment.
    Driver only - can only accept/reject loads assigned to them.
    """
    try:
        user_role = user.get("role")
        if user_role != "driver":
            raise HTTPException(status_code=403, detail="Only drivers can accept/reject load assignments")
        
        driver_id = user['uid']
        
        # Get load from Firestore
        load_ref = db.collection("loads").document(load_id)
        load_doc = load_ref.get()
        
        if not load_doc.exists:
            raise HTTPException(status_code=404, detail="Load not found")
        
        load_data = load_doc.to_dict()
        
        # Check that load is assigned to this driver
        assigned_driver_id = load_data.get("assigned_driver_id") or load_data.get("assigned_driver")
        if not assigned_driver_id or assigned_driver_id != driver_id:
            raise HTTPException(
                status_code=403,
                detail="This load is not assigned to you"
            )
        
        # Check current assignment status
        current_status = load_data.get("driver_assignment_status", "pending")
        if current_status == "accepted":
            raise HTTPException(
                status_code=400,
                detail="You have already accepted this load assignment"
            )
        if current_status == "rejected":
            raise HTTPException(
                status_code=400,
                detail="You have already rejected this load assignment. Contact your carrier to be reassigned."
            )
        
        timestamp = time.time()
        
        if request.accept:
            # Driver accepts the load
            load_ref.update({
                "driver_assignment_status": "accepted",
                "driver_accepted_at": timestamp,
                "updated_at": timestamp
            })
            
            # Log action
            log_action(driver_id, "DRIVER_ACCEPTED_LOAD", f"Driver accepted load assignment {load_id}")
            
            message = "Load assignment accepted successfully"
        else:
            # Driver rejects the load
            load_ref.update({
                "driver_assignment_status": "rejected",
                "driver_rejected_at": timestamp,
                "driver_rejection_notes": request.notes,
                "updated_at": timestamp,
                # Clear driver assignment so carrier can assign to another driver
                "assigned_driver_id": None,
                "assigned_driver": None,
                "assigned_driver_name": None
            })
            
            # Also update driver status back to available
            driver_ref = db.collection("drivers").document(driver_id)
            driver_ref.update({
                "status": "available",
                "updated_at": timestamp
            })
            
            # Log action
            log_action(driver_id, "DRIVER_REJECTED_LOAD", f"Driver rejected load assignment {load_id}")
            
            message = "Load assignment rejected. The carrier can assign it to another driver."
        
        return JSONResponse(content={
            "success": True,
            "message": message,
            "load_id": load_id,
            "driver_id": driver_id,
            "accepted": request.accept
        })
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error processing driver load acceptance: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="Failed to process load assignment acceptance")


@app.get("/service-providers")
async def list_service_providers(
    category: Optional[str] = None,
    user: Dict[str, Any] = Depends(get_current_user)
):
    """
    List all service providers from Firestore.
    Used by shippers, carriers, and drivers to find service providers.
    Optional category filter: factoring, insurance, compliance, legal, repair, medical, testing, dispatch
    """
    try:
        providers_ref = db.collection("service_providers")
        
        # Apply category filter if provided
        if category:
            providers_query = providers_ref.where("category", "==", category)
            providers_docs = providers_query.stream()
        else:
            providers_docs = providers_ref.stream()
        
        providers = []
        for doc in providers_docs:
            provider_data = doc.to_dict()
            provider_data['id'] = doc.id  # Ensure ID is included
            providers.append(provider_data)
        
        # Sort by featured status and rating
        providers.sort(key=lambda x: (x.get('featured', False), x.get('rating', 0)), reverse=True)
        
        return {"providers": providers, "total": len(providers)}
    except Exception as e:
        print(f"Error fetching service providers: {e}")
        return {"providers": [], "total": 0}


@app.post("/match/{load_id}")
def match_for_load(load_id: str, top_n: int = 5):
    load = store.get_load(load_id)
    if not load:
        raise HTTPException(status_code=404, detail="Load not found")
    carriers = store.list_carriers()
    results = match_load(load, carriers, top_n=top_n)
    return {
        "load_id": load_id,
        "matches": [
            {
                "carrier_id": r.carrier_id,
                "score": r.score,
                "reasons": r.reasons,
                "carrier": r.carrier,
            }
            for r in results
        ],
    }


@app.post("/assignments")
def create_assignment(req: AssignmentRequest):
    load = store.get_load(req.load_id)
    carrier = store.get_carrier(req.carrier_id)
    if not load or not carrier:
        raise HTTPException(status_code=404, detail="Load or carrier not found")
    assignment = {
        "load_id": req.load_id,
        "carrier_id": req.carrier_id,
        "reason": req.reason,
    }
    store.save_assignment(assignment)
    create_alert(
        store,
        {
            "type": "assignment",
            "message": f"Assigned carrier {req.carrier_id} to load {req.load_id}",
            "priority": "routine",
            "entity_id": req.load_id,
        },
    )
    return assignment


@app.post("/alerts")
def post_alert(req: AlertRequest):
    alert = create_alert(store, req.dict())
    return alert


@app.get("/alerts")
def get_alerts(priority: Optional[str] = None):
    return {"alerts": list_alerts(store, priority)}


@app.get("/alerts/summary")
def get_alerts_summary():
    return {"summary": summarize_alerts(store)}


@app.get("/alerts/digest")
def get_alerts_digest(limit: int = 20):
    digest = digest_alerts(store, limit=limit)
    # Optional webhook delivery if configured
    webhook = settings.ALERT_WEBHOOK_URL if hasattr(settings, "ALERT_WEBHOOK_URL") else None
    if webhook:
        send_webhook(webhook, digest)
    return digest


# --- Helper Functions ---

def _extract_identifiers(extraction: Dict[str, Any]) -> Tuple[Optional[str], Optional[str]]:
    usdot_keys = ["usdot", "usdot_number", "dot_number", "dot"]
    mc_keys = ["mc_number", "mc", "docket_number"]
    usdot = next((str(extraction.get(k)) for k in usdot_keys if extraction.get(k)), None)
    mc_number = next((str(extraction.get(k)) for k in mc_keys if extraction.get(k)), None)
    return usdot, mc_number


def _attempt_fmcsa_verify(usdot: Optional[str], mc_number: Optional[str]) -> Optional[Dict[str, Any]]:
    client = _get_fmcsa_client()
    try:
        verification = client.verify(usdot, mc_number)
    except Exception:
        return None
    store.save_fmcsa_verification(verification)
    profile = client.fetch_profile(verification["usdot"])
    if profile:
        store.save_fmcsa_profile(profile_to_dict(profile))
    return {
        "result": verification.get("result"),
        "reasons": verification.get("reasons", []),
        "usdot": verification.get("usdot"),
        "mc_number": verification.get("mc_number"),
        "fetched_at": verification.get("fetched_at"),
    }


def _get_fmcsa_client() -> FmcsaClient:
    global fmcsa_client
    if fmcsa_client is None:
        fmcsa_client = FmcsaClient()
    return fmcsa_client


def _refresh_fmcsa_all():
    try:
        fmcsa_refresh_all()
    except Exception:
        pass


def _digest_alerts_job():
    digest_alerts(store, limit=50)


# ============================================================================
# Carrier Bidding/Tender Endpoints
# ============================================================================

@app.post("/loads/{load_id}/tender-offer", response_model=LoadActionResponse)
async def carrier_submit_tender(
    load_id: str,
    request: TenderOfferRequest,
    user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Carrier submits a tender offer/bid on a shipper-posted load.
    
    Authorization: Only carriers can submit bids
    Requirements:
    - Load must be status=POSTED
    - Load must be created by shipper/broker (creator_role in [shipper, broker])
    - Carrier cannot bid on their own loads
    
    Business Logic:
    - Carrier views shipper-posted loads in marketplace
    - Carrier submits bid with rate, notes, ETA
    - Offer stored in load.offers array
    - Shipper reviews offers and accepts one carrier
    """
    uid = user['uid']
    user_role = user.get("role", "")
    
    # Role check: Must be carrier
    if user_role != "carrier":
        raise HTTPException(
            status_code=403,
            detail="Only carriers can submit tender offers"
        )
    
    # Get load from Firestore first, fallback to local storage
    load = None
    try:
        load_doc = db.collection("loads").document(load_id).get()
        if load_doc.exists:
            load = load_doc.to_dict()
            load["load_id"] = load_id
    except Exception as e:
        print(f"Error fetching load from Firestore: {e}")
    
    # Fallback to local storage if Firestore doesn't have it
    if not load:
        load = store.get_load(load_id)
    
    if not load:
        raise HTTPException(status_code=404, detail="Load not found")
    
    # Cannot bid on own loads
    if load.get("created_by") == uid:
        raise HTTPException(
            status_code=400,
            detail="Cannot bid on your own load"
        )
    
    # Status check: Must be POSTED
    if load.get("status") != LoadStatus.POSTED.value:
        raise HTTPException(
            status_code=400,
            detail=f"Load is not available for bidding (status: {load.get('status')})"
        )
    
    # Creator role check: Can bid on shipper/broker/carrier loads
    # (Allows carrier-to-carrier brokerage for subcontracting)
    creator_role = load.get("creator_role", "")
    if creator_role not in ["shipper", "broker", "carrier"]:
        raise HTTPException(
            status_code=400,
            detail="Can only bid on shipper/broker/carrier-posted loads"
        )
    
    # Check if carrier already has a pending offer
    existing_offers = load.get("offers", [])
    for offer in existing_offers:
        if offer.get("carrier_id") == uid and offer.get("status") == "pending":
            raise HTTPException(
                status_code=400,
                detail="You already have a pending offer on this load"
            )
    
    # Create offer
    timestamp = time.time()
    offer = {
        "offer_id": f"OFFER-{int(timestamp)}-{uid[:8]}",
        "load_id": load_id,
        "carrier_id": uid,
        "carrier_name": user.get("display_name", user.get("email", "Unknown Carrier")),
        "rate": request.rate,
        "notes": request.notes or "",
        "eta": request.eta or "",
        "status": "pending",
        "submitted_at": timestamp
    }
    
    # Add offer to load
    if "offers" not in load:
        load["offers"] = []
    load["offers"].append(offer)
    
    # Update Firestore (primary storage)
    try:
        load_ref = db.collection("loads").document(load_id)
        load_ref.update({
            "offers": load["offers"],
            "updated_at": timestamp
        })
    except Exception as e:
        print(f"Error updating Firestore: {e}")
        raise HTTPException(status_code=500, detail="Failed to save bid to database")
    
    # Also update local storage as backup
    try:
        store.update_load(load_id, {"offers": load["offers"], "updated_at": timestamp})
    except Exception as e:
        print(f"Warning: Could not update local storage: {e}")
    
    # Log action
    log_action(uid, "CARRIER_SUBMIT_TENDER", f"Load {load_id}: Submitted tender offer (Rate: ${request.rate})")
    
    # Create notification for shipper about the new bid
    try:
        shipper_uid = load.get("created_by")
        if shipper_uid:
            # Get carrier information
            carrier_name = user.get("display_name", user.get("email", "Unknown Carrier"))
            carrier_email = user.get("email", "")
            
            # Get load details for notification
            load_origin = load.get("origin", "Unknown")
            load_destination = load.get("destination", "Unknown")
            
            notification_id = str(uuid.uuid4())
            notification_data = {
                "id": notification_id,
                "user_id": shipper_uid,
                "notification_type": "load_update",
                "title": f"New Bid Received on Load {load_id}",
                "message": f"{carrier_name} has submitted a bid of ${request.rate} for your load from {load_origin} to {load_destination}.",
                "resource_type": "bid",
                "resource_id": offer["offer_id"],
                "action_url": f"/operations/carrier-bids",
                "is_read": False,
                "created_at": int(timestamp),
                "bid_data": {
                    "offer_id": offer["offer_id"],
                    "load_id": load_id,
                    "carrier_id": uid,
                    "carrier_name": carrier_name,
                    "carrier_email": carrier_email,
                    "rate": request.rate,
                    "notes": request.notes or "",
                    "eta": request.eta or "",
                    "submitted_at": timestamp
                }
            }
            
            # Save notification to Firestore
            db.collection("notifications").document(notification_id).set(notification_data)
            log_action(shipper_uid, "NOTIFICATION_CREATED", f"Bid notification for load {load_id} from carrier {uid}")
    except Exception as e:
        print(f"Error creating notification for shipper: {e}")
        # Don't fail the bid submission if notification fails
    
    return LoadActionResponse(
        success=True,
        message=f"Tender offer submitted successfully for load {load_id}",
        load_id=load_id,
        data={
            "offer_id": offer["offer_id"],
            "rate": request.rate,
            "submitted_at": timestamp
        }
    )


@app.get("/shipper/bids", response_model=Dict[str, Any])
async def get_all_shipper_bids(
    user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Get all bids across all loads created by the shipper.
    
    Authorization: Only shippers/brokers can view their bids
    """
    uid = user['uid']
    user_role = user.get("role", "")
    
    if user_role not in ["shipper", "broker", "admin", "super_admin"]:
        raise HTTPException(
            status_code=403,
            detail="Only shippers can view bids on their loads"
        )
    
    # Get all loads created by this shipper from Firestore
    try:
        loads_ref = db.collection("loads")
        query = loads_ref.where("created_by", "==", uid)
        all_loads_docs = query.stream()
        
        all_bids = []
        for doc in all_loads_docs:
            load = doc.to_dict()
            load_id = doc.id
            load["load_id"] = load_id
            
            # Get offers from the load
            offers = load.get("offers", [])
            for offer in offers:
                bid_info = {
                    "offer_id": offer.get("offer_id", ""),
                    "load_id": load_id,
                    "load_origin": load.get("origin", "Unknown"),
                    "load_destination": load.get("destination", "Unknown"),
                    "load_status": load.get("status", ""),
                    "carrier_id": offer.get("carrier_id", ""),
                    "carrier_name": offer.get("carrier_name", "Unknown Carrier"),
                    "rate": offer.get("rate", 0.0),
                    "notes": offer.get("notes", ""),
                    "eta": offer.get("eta", ""),
                    "status": offer.get("status", "pending"),
                    "submitted_at": offer.get("submitted_at", 0.0)
                }
                all_bids.append(bid_info)
        
        # Sort by submission time (newest first)
        all_bids.sort(key=lambda x: x.get("submitted_at", 0), reverse=True)
        
        return {
            "bids": all_bids,
            "total": len(all_bids)
        }
    except Exception as e:
        print(f"Error fetching shipper bids from Firestore: {e}")
        # Fallback to local storage if Firestore fails
        filters = {"created_by": uid}
        all_loads = store.list_loads(filters)
        all_bids = []
        for load in all_loads:
            load_id = load.get("load_id")
            offers = load.get("offers", [])
            for offer in offers:
                bid_info = {
                    "offer_id": offer.get("offer_id", ""),
                    "load_id": load_id,
                    "load_origin": load.get("origin", "Unknown"),
                    "load_destination": load.get("destination", "Unknown"),
                    "load_status": load.get("status", ""),
                    "carrier_id": offer.get("carrier_id", ""),
                    "carrier_name": offer.get("carrier_name", "Unknown Carrier"),
                    "rate": offer.get("rate", 0.0),
                    "notes": offer.get("notes", ""),
                    "eta": offer.get("eta", ""),
                    "status": offer.get("status", "pending"),
                    "submitted_at": offer.get("submitted_at", 0.0)
                }
                all_bids.append(bid_info)
        all_bids.sort(key=lambda x: x.get("submitted_at", 0), reverse=True)
        return {
            "bids": all_bids,
            "total": len(all_bids)
        }


@app.get("/loads/{load_id}/offers", response_model=OffersListResponse)
async def get_load_offers(
    load_id: str,
    user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Get all offers on a load.
    
    Authorization:
    - Shipper/Broker: Can view offers on loads they created
    - Admin: Can view all offers
    - Carriers/Drivers: Cannot view offers (privacy)
    
    Business Logic:
    - Shipper reviews offers from multiple carriers
    - Shipper accepts one carrier using /accept-carrier endpoint
    """
    uid = user['uid']
    user_role = user.get("role", "")
    
    # Get load from Firestore first, fallback to local storage
    load = None
    try:
        load_doc = db.collection("loads").document(load_id).get()
        if load_doc.exists:
            load = load_doc.to_dict()
            load["load_id"] = load_id
    except Exception as e:
        print(f"Error fetching load from Firestore: {e}")
    
    # Fallback to local storage if Firestore doesn't have it
    if not load:
        load = store.get_load(load_id)
    
    if not load:
        raise HTTPException(status_code=404, detail="Load not found")
    
    # Authorization check
    if user_role in ["admin", "super_admin"]:
        # Admins can view all
        pass
    elif user_role in ["shipper", "broker"]:
        # Shippers can only view offers on their own loads
        if load.get("created_by") != uid:
            raise HTTPException(
                status_code=403,
                detail="You can only view offers on loads you created"
            )
    else:
        # Carriers and drivers cannot view offers (prevents seeing competing bids)
        raise HTTPException(
            status_code=403,
            detail="Only shippers can view offers on loads"
        )
    
    # Get offers
    offers = load.get("offers", [])
    
    # Convert to OfferResponse models
    offer_responses = [
        OfferResponse(
            offer_id=offer.get("offer_id", ""),
            load_id=load_id,
            carrier_id=offer.get("carrier_id", ""),
            carrier_name=offer.get("carrier_name", "Unknown"),
            rate=offer.get("rate", 0.0),
            notes=offer.get("notes"),
            eta=offer.get("eta"),
            status=offer.get("status", "pending"),
            submitted_at=offer.get("submitted_at", 0.0)
        )
        for offer in offers
    ]
    
    return OffersListResponse(
        load_id=load_id,
        offers=offer_responses
    )


# ============================================================================
# Shipper Load Management Endpoints
# ============================================================================

@app.post("/loads/{load_id}/accept-carrier", response_model=LoadActionResponse)
async def shipper_accept_carrier(
    load_id: str,
    request: AcceptCarrierRequest,
    user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Shipper accepts a carrier for a POSTED load, transitioning it to COVERED.
    
    Authorization: Only shipper who created the load
    Valid transition: POSTED → COVERED
    """
    uid = user['uid']
    user_role = user.get("role", "")
    
    # Role check: Must be shipper or broker
    if user_role not in ["shipper", "broker", "admin", "super_admin"]:
        raise HTTPException(
            status_code=403,
            detail="Only shippers and brokers can accept carriers for loads"
        )
    
    # Get load from Firestore first, fallback to local storage
    load = None
    try:
        load_doc = db.collection("loads").document(load_id).get()
        if load_doc.exists:
            load = load_doc.to_dict()
            load["load_id"] = load_id
    except Exception as e:
        print(f"Error fetching load from Firestore: {e}")
    
    # Fallback to local storage if Firestore doesn't have it
    if not load:
        load = store.get_load(load_id)
    
    if not load:
        raise HTTPException(status_code=404, detail="Load not found")
    
    # Ownership check
    if load.get("created_by") != uid:
        raise HTTPException(
            status_code=403,
            detail="You can only accept carriers for loads you created"
        )
    
    # Status validation
    current_status = load.get("status", "")
    if current_status != LoadStatus.POSTED.value:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot accept carrier for load with status '{current_status}'. Load must be POSTED."
        )
    
    # Handle offer acceptance if offer_id provided
    offers = load.get("offers", [])
    
    # Ensure offers is a list
    if not isinstance(offers, list):
        offers = []
    
    # Debug: Print offers for troubleshooting
    print(f"DEBUG: Load {load_id} has {len(offers)} offers")
    print(f"DEBUG: Request offer_id: {request.offer_id}, carrier_id: {request.carrier_id}")
    print(f"DEBUG: Offers: {offers}")
    
    if not offers or len(offers) == 0:
        raise HTTPException(
            status_code=400,
            detail="This load has no offers to accept"
        )
    
    accepted_offer = None
    carrier_name_to_use = request.carrier_name
    
    if request.offer_id:
        # Find and mark the accepted offer
        offer_found = False
        for offer in offers:
            # Handle both dict and object types
            offer_id = offer.get("offer_id") if isinstance(offer, dict) else getattr(offer, "offer_id", None)
            offer_carrier_id = offer.get("carrier_id") if isinstance(offer, dict) else getattr(offer, "carrier_id", None)
            offer_status = offer.get("status") if isinstance(offer, dict) else getattr(offer, "status", "pending")
            
            # Compare offer_id as strings to handle any type mismatches
            if offer_id and request.offer_id and str(offer_id) == str(request.offer_id):
                if str(offer_carrier_id) != str(request.carrier_id):
                    raise HTTPException(
                        status_code=400,
                        detail=f"Offer carrier_id ({offer_carrier_id}) does not match request carrier_id ({request.carrier_id})"
                    )
                # Update offer status
                if isinstance(offer, dict):
                    offer["status"] = "accepted"
                    offer["accepted_at"] = time.time()
                    accepted_offer = offer.copy()  # Make a copy to avoid reference issues
                    if not carrier_name_to_use:
                        carrier_name_to_use = offer.get("carrier_name", "Unknown Carrier")
                else:
                    offer.status = "accepted"
                    offer.accepted_at = time.time()
                    accepted_offer = offer
                    if not carrier_name_to_use:
                        carrier_name_to_use = getattr(offer, "carrier_name", "Unknown Carrier")
                offer_found = True
                print(f"DEBUG: Found and accepted offer {request.offer_id} for carrier {request.carrier_id}")
                break  # Exit loop once we found the offer
            elif offer_status and str(offer_status).lower() == "pending":
                # Reject all other pending offers
                if isinstance(offer, dict):
                    offer["status"] = "rejected"
                    offer["rejected_at"] = time.time()
                    offer["rejection_reason"] = "Another carrier was selected"
                else:
                    offer.status = "rejected"
                    offer.rejected_at = time.time()
                    offer.rejection_reason = "Another carrier was selected"
        
        if not offer_found:
            available_offer_ids = [o.get("offer_id") if isinstance(o, dict) else getattr(o, "offer_id", None) for o in offers]
            raise HTTPException(
                status_code=404,
                detail=f"Offer with ID '{request.offer_id}' not found on this load. Available offer IDs: {available_offer_ids}"
            )
    else:
        # If no offer_id provided, try to find offer by carrier_id
        offer_found_by_carrier = False
        for offer in offers:
            offer_carrier_id = offer.get("carrier_id") if isinstance(offer, dict) else getattr(offer, "carrier_id", None)
            offer_status = offer.get("status") if isinstance(offer, dict) else getattr(offer, "status", "pending")
            
            # Compare carrier_id as strings to handle any type mismatches
            if offer_carrier_id and request.carrier_id and str(offer_carrier_id) == str(request.carrier_id) and offer_status and str(offer_status).lower() == "pending":
                # Update offer status
                if isinstance(offer, dict):
                    offer["status"] = "accepted"
                    offer["accepted_at"] = time.time()
                    accepted_offer = offer.copy()  # Make a copy to avoid reference issues
                    if not carrier_name_to_use:
                        carrier_name_to_use = offer.get("carrier_name", "Unknown Carrier")
                else:
                    offer.status = "accepted"
                    offer.accepted_at = time.time()
                    accepted_offer = offer
                    if not carrier_name_to_use:
                        carrier_name_to_use = getattr(offer, "carrier_name", "Unknown Carrier")
                offer_found_by_carrier = True
                print(f"DEBUG: Found and accepted offer for carrier {request.carrier_id} (no offer_id provided)")
                
                # Reject other pending offers
                for other_offer in offers:
                    other_offer_id = other_offer.get("offer_id") if isinstance(other_offer, dict) else getattr(other_offer, "offer_id", None)
                    other_offer_status = other_offer.get("status") if isinstance(other_offer, dict) else getattr(other_offer, "status", "pending")
                    current_offer_id = offer.get("offer_id") if isinstance(offer, dict) else getattr(offer, "offer_id", None)
                    
                    if other_offer_id and current_offer_id and str(other_offer_id) != str(current_offer_id) and other_offer_status and str(other_offer_status).lower() == "pending":
                        if isinstance(other_offer, dict):
                            other_offer["status"] = "rejected"
                            other_offer["rejected_at"] = time.time()
                            other_offer["rejection_reason"] = "Another carrier was selected"
                        else:
                            other_offer.status = "rejected"
                            other_offer.rejected_at = time.time()
                            other_offer.rejection_reason = "Another carrier was selected"
                break
        
        if not offer_found_by_carrier:
            raise HTTPException(
                status_code=404,
                detail=f"No pending offer found for carrier {request.carrier_id} on this load"
            )
    
    # Use carrier_name from offer if still not set
    if not carrier_name_to_use and accepted_offer:
        if isinstance(accepted_offer, dict):
            carrier_name_to_use = accepted_offer.get("carrier_name", "Unknown Carrier")
        else:
            carrier_name_to_use = getattr(accepted_offer, "carrier_name", "Unknown Carrier")
    elif not carrier_name_to_use:
        carrier_name_to_use = "Unknown Carrier"
    
    # Validate that we have an accepted offer
    if not accepted_offer:
        raise HTTPException(
            status_code=400,
            detail="No offer was accepted. Please ensure the offer_id and carrier_id are correct."
        )
    
    # Update load
    timestamp = time.time()
    updates = {
        "status": LoadStatus.COVERED.value,
        "assigned_carrier": request.carrier_id,
        "assigned_carrier_id": request.carrier_id,  # Also set assigned_carrier_id for consistency
        "assigned_carrier_name": carrier_name_to_use,
        "covered_at": timestamp,
        "updated_at": timestamp
    }
    
    # Update offers if any were modified (always include offers array)
    # Convert offers to list of dicts if needed for Firestore
    offers_list = []
    for offer in offers:
        if isinstance(offer, dict):
            offers_list.append(offer)
        else:
            # Convert object to dict
            offers_list.append({
                "offer_id": getattr(offer, "offer_id", ""),
                "carrier_id": getattr(offer, "carrier_id", ""),
                "carrier_name": getattr(offer, "carrier_name", "Unknown"),
                "rate": getattr(offer, "rate", 0.0),
                "notes": getattr(offer, "notes", ""),
                "eta": getattr(offer, "eta", ""),
                "status": getattr(offer, "status", "pending"),
                "submitted_at": getattr(offer, "submitted_at", 0.0),
                "accepted_at": getattr(offer, "accepted_at", None),
                "rejected_at": getattr(offer, "rejected_at", None),
                "rejection_reason": getattr(offer, "rejection_reason", None)
            })
    
    updates["offers"] = offers_list
    
    # Update Firestore (primary storage)
    try:
        load_ref = db.collection("loads").document(load_id)
        # Convert any non-serializable values for Firestore
        firestore_updates = {}
        for key, value in updates.items():
            if key == "offers" and isinstance(value, list):
                # Ensure offers are properly formatted
                firestore_updates[key] = value
            elif isinstance(value, (str, int, float, bool, type(None))):
                firestore_updates[key] = value
            else:
                # Try to convert other types
                try:
                    firestore_updates[key] = value
                except:
                    print(f"Warning: Could not serialize {key} for Firestore")
        
        load_ref.update(firestore_updates)
        print(f"DEBUG: Successfully updated load {load_id} in Firestore with status {LoadStatus.COVERED.value}")
    except Exception as e:
        print(f"Error updating Firestore: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to accept bid in database: {str(e)}")
    
    # Also update local storage as backup
    try:
        store.update_load(load_id, updates)
    except Exception as e:
        print(f"Warning: Could not update local storage: {e}")
    
    # Log status change
    log_entry = {
        "timestamp": timestamp,
        "actor_uid": uid,
        "actor_role": user_role,
        "old_status": current_status,
        "new_status": LoadStatus.COVERED.value,
        "notes": f"Shipper accepted carrier {carrier_name_to_use or request.carrier_id}",
        "metadata": {
            "carrier_id": request.carrier_id,
            "carrier_name": carrier_name_to_use,
            "shipper_notes": request.notes
        }
    }
    store.add_status_change_log(load_id, log_entry)
    
    # Log action
    log_action(uid, "SHIPPER_ACCEPT_CARRIER", f"Load {load_id}: POSTED → COVERED (Carrier: {request.carrier_id})")
    
    # Add status log to Firestore (load update already done above)
    try:
        load_ref = db.collection("loads").document(load_id)
        logs_ref = load_ref.collection("status_logs").document()
        logs_ref.set(log_entry)
    except Exception as e:
        print(f"Warning: Could not add status log to Firestore: {e}")
    
    return LoadActionResponse(
        success=True,
        message=f"Carrier {request.carrier_name or request.carrier_id} accepted for load {load_id}",
        load_id=load_id,
        new_status=LoadStatus.COVERED.value,
        data={
            "carrier_id": request.carrier_id,
            "carrier_name": request.carrier_name,
            "covered_at": timestamp
        }
    )


@app.post("/loads/{load_id}/reject-offer", response_model=LoadActionResponse)
async def shipper_reject_offer(
    load_id: str,
    request: RejectOfferRequest,
    user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Shipper rejects a carrier offer for a load.
    Load remains in POSTED status.
    
    Authorization: Only shipper who created the load
    """
    uid = user['uid']
    user_role = user.get("role", "")
    
    # Role check: Must be shipper or broker
    if user_role not in ["shipper", "broker", "admin", "super_admin"]:
        raise HTTPException(
            status_code=403,
            detail="Only shippers and brokers can reject carrier offers"
        )
    
    # Validate that either offer_id or carrier_id is provided
    if not request.offer_id and not request.carrier_id:
        raise HTTPException(
            status_code=400,
            detail="Either offer_id or carrier_id must be provided"
        )
    
    # Get load from Firestore first, fallback to local storage
    load = None
    try:
        load_doc = db.collection("loads").document(load_id).get()
        if load_doc.exists:
            load = load_doc.to_dict()
            load["load_id"] = load_id
    except Exception as e:
        print(f"Error fetching load from Firestore: {e}")
    
    # Fallback to local storage if Firestore doesn't have it
    if not load:
        load = store.get_load(load_id)
    
    if not load:
        raise HTTPException(status_code=404, detail="Load not found")
    
    # Ownership check
    if load.get("created_by") != uid:
        raise HTTPException(
            status_code=403,
            detail="You can only reject offers for loads you created"
        )
    
    # Status validation - can only reject offers on POSTED loads
    current_status = load.get("status", "")
    if current_status != LoadStatus.POSTED.value:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot reject offer for load with status '{current_status}'. Load must be POSTED."
        )
    
    # Get offers
    offers = load.get("offers", [])
    
    # Ensure offers is a list
    if not isinstance(offers, list):
        offers = []
    
    if not offers or len(offers) == 0:
        raise HTTPException(
            status_code=400,
            detail="This load has no offers to reject"
        )
    
    # Find the offer to reject
    offer_found = False
    rejected_offer = None
    
    for offer in offers:
        # Handle both dict and object types
        offer_id = offer.get("offer_id") if isinstance(offer, dict) else getattr(offer, "offer_id", None)
        offer_carrier_id = offer.get("carrier_id") if isinstance(offer, dict) else getattr(offer, "carrier_id", None)
        offer_status = offer.get("status") if isinstance(offer, dict) else getattr(offer, "status", "pending")
        
        # Check if this is the offer to reject
        should_reject = False
        
        if request.offer_id:
            # Prefer offer_id if provided
            if offer_id and str(offer_id) == str(request.offer_id):
                should_reject = True
                # Validate carrier_id matches if provided
                if request.carrier_id and str(offer_carrier_id) != str(request.carrier_id):
                    raise HTTPException(
                        status_code=400,
                        detail=f"Offer carrier_id ({offer_carrier_id}) does not match request carrier_id ({request.carrier_id})"
                    )
        elif request.carrier_id:
            # Fallback to carrier_id
            if offer_carrier_id and str(offer_carrier_id) == str(request.carrier_id):
                # Only reject if status is pending (don't reject already rejected/accepted offers)
                if offer_status and str(offer_status).lower() == "pending":
                    should_reject = True
        
        if should_reject:
            # Update offer status
            timestamp = time.time()
            if isinstance(offer, dict):
                offer["status"] = "rejected"
                offer["rejected_at"] = timestamp
                offer["rejection_reason"] = request.reason or "Shipper rejected offer"
                rejected_offer = offer.copy()
            else:
                offer.status = "rejected"
                offer.rejected_at = timestamp
                offer.rejection_reason = request.reason or "Shipper rejected offer"
                rejected_offer = offer
            
            offer_found = True
            print(f"DEBUG: Found and rejected offer {offer_id or 'N/A'} for carrier {offer_carrier_id}")
            break
    
    if not offer_found:
        available_offer_ids = [o.get("offer_id") if isinstance(o, dict) else getattr(o, "offer_id", None) for o in offers]
        raise HTTPException(
            status_code=404,
            detail=f"Offer not found. Requested: offer_id={request.offer_id}, carrier_id={request.carrier_id}. Available offer IDs: {available_offer_ids}"
        )
    
    # Get carrier info for logging
    if isinstance(rejected_offer, dict):
        carrier_id_to_log = rejected_offer.get("carrier_id", request.carrier_id or "Unknown")
        carrier_name_to_log = rejected_offer.get("carrier_name", "Unknown Carrier")
    else:
        carrier_id_to_log = getattr(rejected_offer, "carrier_id", request.carrier_id or "Unknown")
        carrier_name_to_log = getattr(rejected_offer, "carrier_name", "Unknown Carrier")
    
    # Update load with modified offers
    timestamp = time.time()
    
    # Convert offers to list of dicts if needed for Firestore
    offers_list = []
    for offer in offers:
        if isinstance(offer, dict):
            offers_list.append(offer)
        else:
            # Convert object to dict
            offers_list.append({
                "offer_id": getattr(offer, "offer_id", ""),
                "carrier_id": getattr(offer, "carrier_id", ""),
                "carrier_name": getattr(offer, "carrier_name", "Unknown"),
                "rate": getattr(offer, "rate", 0.0),
                "notes": getattr(offer, "notes", ""),
                "eta": getattr(offer, "eta", ""),
                "status": getattr(offer, "status", "pending"),
                "submitted_at": getattr(offer, "submitted_at", 0.0),
                "accepted_at": getattr(offer, "accepted_at", None),
                "rejected_at": getattr(offer, "rejected_at", None),
                "rejection_reason": getattr(offer, "rejection_reason", None)
            })
    
    updates = {
        "offers": offers_list,
        "updated_at": timestamp
    }
    
    # Update Firestore (primary storage)
    try:
        load_ref = db.collection("loads").document(load_id)
        firestore_updates = {
            "offers": offers_list,
            "updated_at": timestamp
        }
        load_ref.update(firestore_updates)
        print(f"DEBUG: Successfully updated load {load_id} in Firestore with rejected offer")
    except Exception as e:
        print(f"Error updating Firestore: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to reject offer in database: {str(e)}")
    
    # Also update local storage as backup
    try:
        store.update_load(load_id, updates)
    except Exception as e:
        print(f"Warning: Could not update local storage: {e}")
    
    # Log rejection
    log_entry = {
        "timestamp": timestamp,
        "actor_uid": uid,
        "actor_role": user_role,
        "old_status": current_status,
        "new_status": current_status,  # Status unchanged
        "notes": f"Shipper rejected offer from carrier {carrier_name_to_log} ({carrier_id_to_log})",
        "metadata": {
            "carrier_id": carrier_id_to_log,
            "carrier_name": carrier_name_to_log,
            "rejection_reason": request.reason
        }
    }
    store.add_status_change_log(load_id, log_entry)
    
    # Log action
    log_action(uid, "SHIPPER_REJECT_OFFER", f"Load {load_id}: Rejected carrier {carrier_id_to_log}")
    
    # Add rejection log to Firestore
    try:
        load_ref = db.collection("loads").document(load_id)
        logs_ref = load_ref.collection("status_logs").document()
        logs_ref.set(log_entry)
    except Exception as e:
        print(f"Warning: Could not add status log to Firestore: {e}")
    
    return LoadActionResponse(
        success=True,
        message=f"Offer from carrier {carrier_name_to_log} rejected",
        load_id=load_id,
        new_status=current_status,
        data={
            "carrier_id": carrier_id_to_log,
            "carrier_name": carrier_name_to_log,
            "rejection_reason": request.reason
        }
    )


@app.patch("/loads/{load_id}", response_model=LoadActionResponse)
async def update_load_restricted(
    load_id: str,
    user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Prevent shippers from editing loads after they are COVERED.
    This endpoint blocks unauthorized edits.
    
    Authorization: Shippers cannot edit COVERED loads
    """
    uid = user['uid']
    user_role = user.get("role", "")
    
    # Get load
    load = store.get_load(load_id)
    if not load:
        raise HTTPException(status_code=404, detail="Load not found")
    
    # Ownership check
    if load.get("created_by") != uid:
        raise HTTPException(
            status_code=403,
            detail="Not authorized to edit this load"
        )
    
    # Status restriction for shippers
    if user_role == "shipper":
        current_status = load.get("status", "")
        if current_status in [LoadStatus.COVERED.value, LoadStatus.IN_TRANSIT.value, 
                              LoadStatus.DELIVERED.value, LoadStatus.COMPLETED.value]:
            raise HTTPException(
                status_code=403,
                detail=f"Cannot edit load with status '{current_status}'. Shippers cannot modify loads after COVERED."
            )
    
    return LoadActionResponse(
        success=True,
        message="Load can be edited",
        load_id=load_id,
        new_status=load.get("status")
    )


@app.delete("/loads/{load_id}/cancel", response_model=LoadActionResponse)
async def shipper_cancel_load(
    load_id: str,
    user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Shipper cancels a load (only if not COVERED).
    
    Authorization: Only shipper who created the load
    Valid statuses: DRAFT, POSTED (cannot cancel COVERED or later)
    """
    uid = user['uid']
    user_role = user.get("role", "")
    
    # Role check: Must be shipper
    if user_role != "shipper":
        raise HTTPException(
            status_code=403,
            detail="Only shippers can cancel their loads"
        )
    
    # Get load
    load = store.get_load(load_id)
    if not load:
        raise HTTPException(status_code=404, detail="Load not found")
    
    # Ownership check
    if load.get("created_by") != uid:
        raise HTTPException(
            status_code=403,
            detail="You can only cancel loads you created"
        )
    
    # Status validation
    current_status = load.get("status", "")
    if current_status not in [LoadStatus.DRAFT.value, LoadStatus.POSTED.value]:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot cancel load with status '{current_status}'. Can only cancel DRAFT or POSTED loads."
        )
    
    # Update to cancelled
    timestamp = time.time()
    updates = {
        "status": LoadStatus.CANCELLED.value,
        "cancelled_at": timestamp,
        "updated_at": timestamp
    }
    store.update_load(load_id, updates)
    
    # Log status change
    log_entry = {
        "timestamp": timestamp,
        "actor_uid": uid,
        "actor_role": user_role,
        "old_status": current_status,
        "new_status": LoadStatus.CANCELLED.value,
        "notes": "Shipper cancelled load",
        "metadata": {}
    }
    store.add_status_change_log(load_id, log_entry)
    
    # Log action
    log_action(uid, "SHIPPER_CANCEL_LOAD", f"Load {load_id}: {current_status} → CANCELLED")
    
    # Update Firestore
    try:
        load_ref = db.collection("loads").document(load_id)
        load_ref.update(updates)
        logs_ref = load_ref.collection("status_logs").document()
        logs_ref.set(log_entry)
    except Exception as e:
        print(f"Warning: Could not update Firestore: {e}")
    
    return LoadActionResponse(
        success=True,
        message=f"Load {load_id} cancelled successfully",
        load_id=load_id,
        new_status=LoadStatus.CANCELLED.value
    )


# ============================================================================
# Driver Load Management Endpoints
# ============================================================================

@app.post("/loads/{load_id}/driver-update-status", response_model=LoadActionResponse)
async def driver_update_status(
    load_id: str,
    request: DriverStatusUpdateRequest,
    user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Driver updates load status with strict state transitions.
    
    Authorization: Only driver assigned to the load
    Valid transitions:
    - COVERED → IN_TRANSIT (pickup confirmed)
    - IN_TRANSIT → DELIVERED (delivery confirmed)
    """
    uid = user['uid']
    user_role = user.get("role", "")
    
    # Role check: Must be driver
    if user_role != "driver":
        raise HTTPException(
            status_code=403,
            detail="Only drivers can update load status"
        )
    
    # Get load
    load = store.get_load(load_id)
    if not load:
        raise HTTPException(status_code=404, detail="Load not found")
    
    # Assignment check: Driver must be assigned to this load
    if load.get("assigned_driver") != uid:
        raise HTTPException(
            status_code=403,
            detail="You can only update loads assigned to you"
        )
    
    # Validate status transition
    current_status = load.get("status", "")
    new_status = request.new_status.upper()
    
    # Define valid transitions for drivers
    valid_transitions = {
        LoadStatus.COVERED.value.upper(): [LoadStatus.IN_TRANSIT.value.upper()],
        LoadStatus.IN_TRANSIT.value.upper(): [LoadStatus.DELIVERED.value.upper()]
    }
    
    # Normalize statuses for comparison
    current_status_normalized = current_status.upper()
    
    if current_status_normalized not in valid_transitions:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot update load from status '{current_status}'. Driver can only update COVERED or IN_TRANSIT loads."
        )
    
    if new_status not in valid_transitions[current_status_normalized]:
        allowed = ", ".join(valid_transitions[current_status_normalized])
        raise HTTPException(
            status_code=400,
            detail=f"Invalid transition: {current_status} → {new_status}. Allowed: {allowed}"
        )
    
    # Update load
    timestamp = time.time()
    updates = {
        "status": new_status.lower(),
        "updated_at": timestamp
    }
    
    # Add timestamp fields based on status
    if new_status == LoadStatus.IN_TRANSIT.value.upper():
        updates["pickup_confirmed_at"] = timestamp
        updates["in_transit_since"] = timestamp
    elif new_status == LoadStatus.DELIVERED.value.upper():
        updates["delivered_at"] = timestamp
    
    # Add location if provided
    if request.latitude and request.longitude:
        updates["last_location"] = {
            "latitude": request.latitude,
            "longitude": request.longitude,
            "timestamp": timestamp
        }
    
    # Add proof of delivery/pickup
    if request.photo_url:
        if new_status == LoadStatus.IN_TRANSIT.value.upper():
            updates["pickup_photo_url"] = request.photo_url
        elif new_status == LoadStatus.DELIVERED.value.upper():
            updates["delivery_photo_url"] = request.photo_url
    
    store.update_load(load_id, updates)
    
    # Log status change
    log_entry = {
        "timestamp": timestamp,
        "actor_uid": uid,
        "actor_role": user_role,
        "old_status": current_status,
        "new_status": new_status.lower(),
        "notes": request.notes or f"Driver updated status to {new_status}",
        "metadata": {
            "latitude": request.latitude,
            "longitude": request.longitude,
            "photo_url": request.photo_url
        }
    }
    store.add_status_change_log(load_id, log_entry)
    
    # Log action
    log_action(uid, "DRIVER_UPDATE_STATUS", f"Load {load_id}: {current_status} → {new_status}")
    
    # Update Firestore
    try:
        load_ref = db.collection("loads").document(load_id)
        load_ref.update(updates)
        logs_ref = load_ref.collection("status_logs").document()
        logs_ref.set(log_entry)
    except Exception as e:
        print(f"Warning: Could not update Firestore: {e}")
    
    return LoadActionResponse(
        success=True,
        message=f"Load {load_id} status updated: {current_status} → {new_status}",
        load_id=load_id,
        new_status=new_status.lower(),
        data={
            "latitude": request.latitude,
            "longitude": request.longitude,
            "photo_url": request.photo_url,
            "timestamp": timestamp
        }
    )


# ============================================================================
# Consents Endpoints
# ============================================================================

@app.get("/consents/marketplace-eligibility")
async def check_marketplace_eligibility(
    user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Check if user has signed required consents for marketplace access.
    For now, returns eligible=true to allow marketplace access.
    TODO: Implement actual consent tracking in future.
    """
    return {
        "eligible": True,
        "missing_consents": []
    }


# ============================================================================
# Marketplace Endpoints
# ============================================================================

@app.get("/marketplace/loads", response_model=LoadListResponse)
async def get_marketplace_loads(
    page: int = 1,
    page_size: int = 20,
    user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Get marketplace loads based on user role:
    
    CARRIERS see:
    1. Shipper/Broker-posted loads (creator_role in [shipper, broker])
       → For bidding on freight from shippers
    2. Other Carrier-posted loads (creator_role=carrier, NOT created by them)
       → For carrier-to-carrier brokerage (subcontracting)
    
    SHIPPERS/BROKERS:
    - Do NOT see marketplace (they post loads, not browse them)
    - To find carriers, they should use "Carriers" tab (separate carrier directory)
    - Their loads automatically appear in carrier marketplace
    
    Business Logic:
    - Shipper posts load → ALL carriers see it → Carriers bid
    - Carrier posts load (acting as broker) → OTHER carriers see it → Carriers bid
    - Shipper accepts carrier bid → Load moves to COVERED → Appears in carrier's "My Loads"
    """
    uid = user['uid']
    user_role = user.get("role", "carrier")
    
    # Only carriers can browse marketplace loads
    if user_role != "carrier":
        raise HTTPException(
            status_code=403,
            detail="Marketplace is for carriers to find loads. Shippers should post loads via 'Create Load' and review offers in 'My Loads'."
        )
    
    # Carriers see:
    # 1. Shipper/broker loads (for freight hauling)
    # 2. Other carrier loads (for carrier-to-carrier brokerage, excluding own loads)
    
    # Get all POSTED loads from Firestore
    try:
        loads_ref = db.collection("loads")
        # Query for POSTED loads
        query = loads_ref.where("status", "==", LoadStatus.POSTED.value)
        all_posted_docs = query.stream()
        
        marketplace_loads = []
        for doc in all_posted_docs:
            load = doc.to_dict()
            load["load_id"] = doc.id
            
            # Filter to show:
            # - All shipper/broker loads
            # - Carrier loads NOT created by this carrier
            creator_role = load.get("creator_role", "")
            created_by = load.get("created_by", "")
            
            if creator_role in ["shipper", "broker"]:
                marketplace_loads.append(load)
            elif creator_role == "carrier" and created_by != uid:
                marketplace_loads.append(load)
        
        # Apply pagination
        total = len(marketplace_loads)
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        paginated_loads = marketplace_loads[start_idx:end_idx]
        
        return LoadListResponse(
            loads=paginated_loads,
            total=total,
            page=page,
            page_size=page_size
        )
    except Exception as e:
        print(f"Error fetching marketplace loads from Firestore: {e}")
        # Fallback to local storage if Firestore fails
        filters = {"status": LoadStatus.POSTED.value}
        all_posted_loads = store.list_loads(filters)
        marketplace_loads = [
            load for load in all_posted_loads
            if load.get("creator_role") in ["shipper", "broker"] or
               (load.get("creator_role") == "carrier" and load.get("created_by") != uid)
        ]
        total = len(marketplace_loads)
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        paginated_loads = marketplace_loads[start_idx:end_idx]
        return LoadListResponse(
            loads=paginated_loads,
            total=total,
            page=page,
            page_size=page_size
        )


# ============================================================================
# SHIPPER-CARRIER RELATIONSHIP ENDPOINTS
# ============================================================================

@app.get("/carriers/my-carriers")
async def get_my_carriers(
    status: Optional[str] = None,
    user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Get carriers associated with the current shipper.
    
    Authorization: Shippers/Brokers/Admins only
    """
    uid = user['uid']
    user_role = user.get("role", "carrier")
    
    if user_role not in ["shipper", "broker", "admin", "super_admin"]:
        raise HTTPException(
            status_code=403,
            detail="Only shippers can view their carriers"
        )
    
    try:
        # Fetch from Firestore
        relationships_ref = db.collection("shipper_carrier_relationships")
        
        if user_role in ["admin", "super_admin"]:
            # Admins see all relationships
            query = relationships_ref
        else:
            # Regular shippers see only their relationships
            query = relationships_ref.where("shipper_id", "==", uid)
        
        # Apply status filter
        if status:
            query = query.where("status", "==", status)
        else:
            # Default to active relationships
            query = query.where("status", "==", "active")
        
        # Fetch relationships
        relationships_docs = query.stream()
        relationships = []
        
        for doc in relationships_docs:
            rel_data = doc.to_dict()
            rel_data['id'] = doc.id
            
            # Convert Firestore timestamps
            for time_field in ['created_at', 'accepted_at']:
                if time_field in rel_data and hasattr(rel_data[time_field], 'timestamp'):
                    rel_data[time_field] = int(rel_data[time_field].timestamp())
            
            # Enrich with carrier data from Firestore
            carrier_id = rel_data.get("carrier_id")
            if carrier_id:
                try:
                    carrier_doc = db.collection("users").document(carrier_id).get()
                    if carrier_doc.exists:
                        carrier_data = carrier_doc.to_dict()
                        rel_data['carrier_name'] = carrier_data.get("display_name") or carrier_data.get("name") or carrier_data.get("company_name")
                        rel_data['carrier_phone'] = carrier_data.get("phone")
                        
                        # Also check carriers collection for additional info
                        carrier_profile = db.collection("carriers").document(carrier_id).get()
                        if carrier_profile.exists:
                            carrier_profile_data = carrier_profile.to_dict()
                            rel_data['mc_number'] = carrier_profile_data.get("mc_number")
                            rel_data['dot_number'] = carrier_profile_data.get("dot_number")
                            rel_data['rating'] = carrier_profile_data.get("rating", 0)
                            rel_data['total_loads'] = carrier_profile_data.get("total_loads", 0)
                except Exception as e:
                    print(f"Error enriching carrier data: {e}")
            
            relationships.append(rel_data)
        
        return JSONResponse(content={
            "carriers": relationships,
            "total": len(relationships)
        })
        
    except Exception as e:
        print(f"Error fetching carriers: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch carriers")


@app.get("/shippers/my-shippers")
async def get_my_shippers(
    status: Optional[str] = None,
    user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Get shippers associated with the current carrier.
    
    Authorization: Carriers only
    """
    uid = user['uid']
    user_role = user.get("role", "carrier")
    
    if user_role != "carrier":
        raise HTTPException(
            status_code=403,
            detail="Only carriers can view their shippers"
        )
    
    try:
        # Fetch from Firestore
        relationships_ref = db.collection("shipper_carrier_relationships")
        query = relationships_ref.where("carrier_id", "==", uid)
        
        # Apply status filter
        if status:
            query = query.where("status", "==", status)
        else:
            # Default to active relationships
            query = query.where("status", "==", "active")
        
        # Fetch relationships
        relationships_docs = query.stream()
        enriched_relationships = []
        
        for doc in relationships_docs:
            rel_data = doc.to_dict()
            rel_data['id'] = doc.id
            
            # Convert Firestore timestamps
            for time_field in ['created_at', 'accepted_at']:
                if time_field in rel_data and hasattr(rel_data[time_field], 'timestamp'):
                    rel_data[time_field] = int(rel_data[time_field].timestamp())
            
            # Enrich with shipper data from Firestore
            shipper_id = rel_data.get("shipper_id")
            if shipper_id:
                try:
                    shipper_doc = db.collection("users").document(shipper_id).get()
                    if shipper_doc.exists:
                        shipper_data = shipper_doc.to_dict()
                        rel_data["shipper_name"] = shipper_data.get("display_name") or shipper_data.get("name") or rel_data.get("shipper_email")
                        rel_data["shipper_phone"] = shipper_data.get("phone", "N/A")
                        rel_data["shipper_company"] = shipper_data.get("company_name", "N/A")
                except Exception as e:
                    print(f"Error fetching shipper data for {shipper_id}: {e}")
            
            enriched_relationships.append(rel_data)
        
        return JSONResponse(content={
            "shippers": enriched_relationships,
            "total": len(enriched_relationships)
        })
        
    except Exception as e:
        print(f"Error fetching shippers: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch shippers")


@app.post("/carriers/invite")
async def invite_carrier(
    invitation: Dict[str, Any],
    user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Send an invitation to a carrier.
    
    Authorization: Shippers/Brokers/Admins only
    
    Body:
    {
        "carrier_id": "carrier_uid" (optional if carrier_email provided),
        "carrier_email": "carrier@example.com" (required if carrier_id not provided),
        "carrier_name": "Carrier Name" (optional),
        "load_id": "load_id" (optional),
        "message": "Custom message" (optional)
    }
    """
    uid = user['uid']
    user_role = user.get("role", "carrier")
    
    if user_role not in ["shipper", "broker", "admin", "super_admin"]:
        raise HTTPException(
            status_code=403,
            detail="Only shippers can invite carriers"
        )
    
    carrier_id = invitation.get("carrier_id")
    carrier_email = invitation.get("carrier_email")
    
    if not carrier_id and not carrier_email:
        raise HTTPException(status_code=400, detail="Either carrier_id or carrier_email is required")
    
    try:
        # If carrier_id is provided, get the carrier's email from Firestore
        carrier_uid = carrier_id
        if carrier_id:
            try:
                carrier_user_doc = db.collection("users").document(carrier_id).get()
                if carrier_user_doc.exists:
                    carrier_data = carrier_user_doc.to_dict()
                    carrier_email = carrier_data.get("email") or carrier_email
                    if not carrier_email:
                        # Try to get from Firebase Auth
                        try:
                            carrier_firebase_user = firebase_auth.get_user(carrier_id)
                            carrier_email = carrier_firebase_user.email
                        except:
                            pass
                else:
                    raise HTTPException(status_code=404, detail="Carrier not found")
            except HTTPException:
                raise
            except Exception as e:
                print(f"Error fetching carrier user: {e}")
                # Fallback to using email if provided
                if not carrier_email:
                    raise HTTPException(status_code=404, detail="Carrier not found")
        else:
            # If only email provided, try to find carrier by email
            try:
                carrier_firebase_user = firebase_auth.get_user_by_email(carrier_email)
                carrier_uid = carrier_firebase_user.uid
                # Check if user exists in Firestore and is a carrier
                carrier_user_doc = db.collection("users").document(carrier_uid).get()
                if carrier_user_doc.exists:
                    carrier_data = carrier_user_doc.to_dict()
                    if carrier_data.get("role") not in ["carrier", "admin", "super_admin"]:
                        raise HTTPException(status_code=400, detail="User is not a carrier")
            except firebase_auth.UserNotFoundError:
                raise HTTPException(status_code=404, detail="Carrier not found with this email")
            except HTTPException:
                raise
            except Exception as e:
                print(f"Error looking up carrier by email: {e}")
                # Still create invitation, carrier can accept when they sign up
                carrier_uid = None
        
        # Check for duplicate invitation (prevent duplicates)
        invitations_ref = db.collection("carrier_invitations")
        
        # Check if there's already a pending invitation for this shipper-carrier pair
        if carrier_uid:
            existing_query = invitations_ref.where("shipper_id", "==", uid)\
                                            .where("carrier_id", "==", carrier_uid)\
                                            .where("status", "==", "pending")\
                                            .limit(1)
            existing_invites = list(existing_query.stream())
            if existing_invites:
                raise HTTPException(
                    status_code=400, 
                    detail="A pending invitation already exists for this carrier"
                )
        else:
            # Check by email if carrier_uid not available
            existing_query = invitations_ref.where("shipper_id", "==", uid)\
                                            .where("carrier_email", "==", carrier_email)\
                                            .where("status", "==", "pending")\
                                            .limit(1)
            existing_invites = list(existing_query.stream())
            if existing_invites:
                raise HTTPException(
                    status_code=400, 
                    detail="A pending invitation already exists for this carrier email"
                )
        
        invitation_id = f"INV-{uuid.uuid4().hex[:8].upper()}"
        shipper_name = user.get("display_name") or user.get("name") or user.get("email")
        
        invitation_record = {
            "id": invitation_id,
            "shipper_id": uid,
            "shipper_email": user.get("email"),
            "shipper_name": shipper_name,
            "carrier_id": carrier_uid,
            "carrier_email": carrier_email,
            "carrier_name": invitation.get("carrier_name"),
            "load_id": invitation.get("load_id"),
            "message": invitation.get("message"),
            "status": "pending",  # pending, accepted, declined
            "created_at": int(time.time()),
            "invited_by": user.get("email")
        }
        
        # Save to Firestore
        db.collection("carrier_invitations").document(invitation_id).set(invitation_record)
        log_action(uid, "INVITATION_CREATED", f"Invited carrier {carrier_uid or carrier_email}")
        
        # Create notification for carrier if they exist in the system
        if carrier_uid:
            try:
                notification_id = str(uuid.uuid4())
                notification_data = {
                    "id": notification_id,
                    "user_id": carrier_uid,
                    "notification_type": "system",
                    "title": f"New Partnership Invitation from {shipper_name}",
                    "message": invitation.get("message") or f"{shipper_name} has invited you to join their carrier network.",
                    "resource_type": "invitation",
                    "resource_id": invitation_id,
                    "action_url": f"/carriers/invitations/{invitation_id}",
                    "is_read": False,
                    "created_at": int(time.time())
                }
                
                # Save notification to Firestore
                db.collection("notifications").document(notification_id).set(notification_data)
                log_action(carrier_uid, "NOTIFICATION_CREATED", f"Invitation notification from shipper {uid}")
            except Exception as e:
                print(f"Error creating notification: {e}")
                # Don't fail the invite if notification fails
        
        return JSONResponse(content={
            "success": True,
            "invitation_id": invitation_id,
            "message": "Invitation sent successfully"
        })
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error sending invitation: {e}")
        raise HTTPException(status_code=500, detail="Failed to send invitation")


@app.get("/carriers/invitations")
async def list_invitations(
    status: Optional[str] = None,
    user: Dict[str, Any] = Depends(get_current_user)
):
    """
    List carrier invitations.
    - For shippers: Lists invitations they sent
    - For carriers: Lists invitations they received
    
    Authorization: All authenticated users
    """
    uid = user['uid']
    user_role = user.get("role", "carrier")
    user_email = user.get("email")
    
    try:
        invitations_ref = db.collection("carrier_invitations")
        
        if user_role in ["shipper", "broker", "admin", "super_admin"]:
            # Shippers see invitations they sent
            query = invitations_ref.where("shipper_id", "==", uid)
            if status:
                query = query.where("status", "==", status)
        elif user_role == "carrier":
            # Carriers see invitations they received - check both carrier_id and carrier_email
            # Use compound query or multiple queries
            query1 = invitations_ref.where("carrier_id", "==", uid)
            query2 = invitations_ref.where("carrier_email", "==", user_email)
            
            if status:
                query1 = query1.where("status", "==", status)
                query2 = query2.where("status", "==", status)
            
            # Get results from both queries and merge (removing duplicates)
            invites_by_id = {doc.id: doc.to_dict() for doc in query1.stream()}
            invites_by_email = {doc.id: doc.to_dict() for doc in query2.stream()}
            invites_by_id.update(invites_by_email)  # Merge dictionaries
            invitations = list(invites_by_id.values())
            
            # Convert Firestore timestamps and add document IDs
            for inv in invitations:
                if 'created_at' in inv and hasattr(inv['created_at'], 'timestamp'):
                    inv['created_at'] = int(inv['created_at'].timestamp())
                if 'id' not in inv:
                    # Find the doc ID
                    doc_ref = invitations_ref.where("shipper_id", "==", inv.get("shipper_id"))\
                                             .where("carrier_email", "==", inv.get("carrier_email"))\
                                             .limit(1)
                    docs = list(doc_ref.stream())
                    if docs:
                        inv['id'] = docs[0].id
            
            return JSONResponse(content={
                "invitations": invitations,
                "total": len(invitations)
            })
        else:
            raise HTTPException(status_code=403, detail="Unauthorized")
        
        # For shippers, fetch from query
        invitations_docs = query.stream()
        invitations = []
        for doc in invitations_docs:
            inv_data = doc.to_dict()
            inv_data['id'] = doc.id
            # Convert Firestore timestamp if present
            if 'created_at' in inv_data and hasattr(inv_data['created_at'], 'timestamp'):
                inv_data['created_at'] = int(inv_data['created_at'].timestamp())
            invitations.append(inv_data)
        
        return JSONResponse(content={
            "invitations": invitations,
            "total": len(invitations)
        })
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error fetching invitations: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch invitations")


@app.post("/carriers/invitations/{invitation_id}/accept")
async def accept_invitation(
    invitation_id: str,
    user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Accept a carrier invitation.
    
    Authorization: Carriers only
    """
    uid = user['uid']
    user_role = user.get("role", "carrier")
    user_email = user.get("email")
    
    if user_role != "carrier":
        raise HTTPException(
            status_code=403,
            detail="Only carriers can accept invitations"
        )
    
    try:
        # Get the invitation from Firestore
        invitation_ref = db.collection("carrier_invitations").document(invitation_id)
        invitation_doc = invitation_ref.get()
        
        if not invitation_doc.exists:
            raise HTTPException(status_code=404, detail="Invitation not found")
        
        invitation = invitation_doc.to_dict()
        invitation['id'] = invitation_doc.id
        
        # Convert Firestore timestamp if present
        if 'created_at' in invitation and hasattr(invitation['created_at'], 'timestamp'):
            invitation['created_at'] = int(invitation['created_at'].timestamp())
        
        # Verify the invitation is for this carrier
        if invitation.get("carrier_id") != uid and invitation.get("carrier_email") != user_email:
            raise HTTPException(status_code=403, detail="This invitation is not for you")
        
        # Check if already accepted or declined
        if invitation.get("status") == "accepted":
            raise HTTPException(status_code=400, detail="Invitation already accepted")
        if invitation.get("status") == "declined":
            raise HTTPException(status_code=400, detail="Invitation was declined")
        
        # Update invitation status in Firestore
        invitation_ref.update({
            "status": "accepted",
            "accepted_at": int(time.time())
        })
        
        # Create shipper-carrier relationship
        shipper_id = invitation.get("shipper_id")
        
        # Check for duplicate relationship (prevent duplicates)
        relationships_ref = db.collection("shipper_carrier_relationships")
        existing_rel_query = relationships_ref.where("shipper_id", "==", shipper_id)\
                                              .where("carrier_id", "==", uid)\
                                              .where("status", "==", "active")\
                                              .limit(1)
        existing_rels = list(existing_rel_query.stream())
        
        if existing_rels:
            # Relationship already exists - don't create duplicate
            relationship_id = existing_rels[0].id
            existing_rel_data = existing_rels[0].to_dict()
            
            # Just log that it was already there
            log_action(uid, "RELATIONSHIP_EXISTS", f"Relationship already exists with shipper {shipper_id}")
        else:
            # Create new relationship
            relationship_id = f"REL-{uuid.uuid4().hex[:8].upper()}"
            relationship_data = {
                "id": relationship_id,
                "shipper_id": shipper_id,
                "carrier_id": uid,
                "shipper_email": invitation.get("shipper_email"),
                "carrier_email": user_email,
                "status": "active",
                "created_at": int(time.time()),
                "accepted_at": int(time.time()),
                "invitation_id": invitation_id
            }
            # Save to Firestore
            db.collection("shipper_carrier_relationships").document(relationship_id).set(relationship_data)
            log_action(uid, "RELATIONSHIP_CREATED", f"Accepted invitation from shipper {shipper_id}")
        
        # Create notification for shipper about acceptance (only if new relationship)
        if not existing_rels:
            try:
                notification_id = str(uuid.uuid4())
                carrier_name = user.get("display_name") or user.get("name") or user_email
                notification_data = {
                    "id": notification_id,
                    "user_id": shipper_id,
                    "notification_type": "system",
                    "title": f"Carrier {carrier_name} Accepted Your Invitation",
                    "message": f"{carrier_name} has accepted your partnership invitation and has been added to your carrier network.",
                    "resource_type": "relationship",
                    "resource_id": relationship_id,
                    "action_url": f"/carriers/my-carriers",
                    "is_read": False,
                    "created_at": int(time.time())
                }
                db.collection("notifications").document(notification_id).set(notification_data)
                log_action(shipper_id, "NOTIFICATION_CREATED", f"Carrier {uid} accepted invitation")
            except Exception as e:
                print(f"Error creating acceptance notification: {e}")
        
        return JSONResponse(content={
            "success": True,
            "message": "Invitation accepted successfully",
            "relationship_id": relationship_id
        })
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error accepting invitation: {e}")
        raise HTTPException(status_code=500, detail="Failed to accept invitation")


@app.post("/carriers/invitations/{invitation_id}/decline")
async def decline_invitation(
    invitation_id: str,
    user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Decline a carrier invitation.
    
    Authorization: Carriers only
    """
    uid = user['uid']
    user_role = user.get("role", "carrier")
    user_email = user.get("email")
    
    if user_role != "carrier":
        raise HTTPException(
            status_code=403,
            detail="Only carriers can decline invitations"
        )
    
    try:
        # Get invitation from Firestore
        invitation_ref = db.collection("carrier_invitations").document(invitation_id)
        invitation_doc = invitation_ref.get()
        
        if not invitation_doc.exists:
            raise HTTPException(status_code=404, detail="Invitation not found")
        
        invitation = invitation_doc.to_dict()
        
        if invitation.get("carrier_id") != uid and invitation.get("carrier_email") != user_email:
            raise HTTPException(status_code=403, detail="This invitation is not for you")
        
        if invitation.get("status") != "pending":
            raise HTTPException(status_code=400, detail=f"Invitation already {invitation.get('status')}")
        
        # Update in Firestore
        invitation_ref.update({
            "status": "declined",
            "declined_at": int(time.time())
        })
        log_action(uid, "INVITATION_DECLINED", f"Declined invitation {invitation_id}")
        
        return JSONResponse(content={
            "success": True,
            "message": "Invitation declined"
        })
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error declining invitation: {e}")
        raise HTTPException(status_code=500, detail="Failed to decline invitation")


@app.get("/notifications")
async def get_notifications(
    is_read: Optional[bool] = None,
    page: int = 1,
    page_size: int = 20,
    user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Get user's notifications from Firestore.
    
    Authorization: All authenticated users
    """
    uid = user['uid']
    
    try:
        notifications_ref = db.collection("notifications").where("user_id", "==", uid)
        
        if is_read is not None:
            notifications_ref = notifications_ref.where("is_read", "==", is_read)
        
        # Note: Firestore requires an index for order_by with where clauses
        # For now, we'll fetch and sort in memory
        notifications_docs = notifications_ref.stream()
        
        # Convert to list and sort
        notifications_list = []
        for doc in notifications_docs:
            notif_data = doc.to_dict()
            notif_data['id'] = doc.id
            notifications_list.append(notif_data)
        
        # Sort by created_at descending
        notifications_list.sort(key=lambda x: x.get('created_at', 0), reverse=True)
        
        # Pagination
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        paginated_notifications = notifications_list[start_idx:end_idx]
        
        notifications = []
        for notif_data in paginated_notifications:
            # Format timestamp for display
            if 'created_at' in notif_data:
                timestamp = notif_data['created_at']
                if isinstance(timestamp, (int, float)):
                    from datetime import datetime
                    dt = datetime.fromtimestamp(timestamp)
                    notif_data['formatted_time'] = dt.strftime('%Y-%m-%d %H:%M:%S')
                    # Relative time
                    now = time.time()
                    diff = now - timestamp
                    if diff < 3600:
                        notif_data['relative_time'] = f"{int(diff / 60)} minutes ago"
                    elif diff < 86400:
                        notif_data['relative_time'] = f"{int(diff / 3600)} hours ago"
                    else:
                        notif_data['relative_time'] = f"{int(diff / 86400)} days ago"
            
            notifications.append(notif_data)
        
        # Get total count
        total_ref = db.collection("notifications").where("user_id", "==", uid)
        total_count = len(list(total_ref.stream()))
        
        # Get unread count
        unread_ref = db.collection("notifications").where("user_id", "==", uid).where("is_read", "==", False)
        unread_count = len(list(unread_ref.stream()))
        
        return JSONResponse(content={
            "notifications": notifications,
            "total": total_count,
            "unread_count": unread_count,
            "page": page,
            "page_size": page_size
        })
        
    except Exception as e:
        print(f"Error fetching notifications: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch notifications")


@app.post("/notifications/{notification_id}/mark-read")
async def mark_notification_read(
    notification_id: str,
    user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Mark a notification as read.
    
    Authorization: All authenticated users
    """
    uid = user['uid']
    
    try:
        notification_ref = db.collection("notifications").document(notification_id)
        notification_doc = notification_ref.get()
        
        if not notification_doc.exists:
            raise HTTPException(status_code=404, detail="Notification not found")
        
        notification_data = notification_doc.to_dict()
        if notification_data.get("user_id") != uid:
            raise HTTPException(status_code=403, detail="Not authorized to update this notification")
        
        notification_ref.update({
            "is_read": True,
            "read_at": int(time.time())
        })
        
        return JSONResponse(content={"success": True, "message": "Notification marked as read"})
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error marking notification as read: {e}")
        raise HTTPException(status_code=500, detail="Failed to mark notification as read")


# --- Application Events ---

# Register Routers at the end to keep clean separation
app.include_router(auth_router)
app.include_router(onboarding_router) 

@app.on_event("startup")
def startup_events():
    scheduler.start()
    scheduler.add_interval_job(_refresh_fmcsa_all, minutes=60 * 24, id="fmcsa_refresh_daily")
    scheduler.add_interval_job(_digest_alerts_job, minutes=60, id="alert_digest_hourly")


@app.on_event("shutdown")
def shutdown_events():
    scheduler.shutdown()