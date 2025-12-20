# File: apps/api/main.py
from fastapi import FastAPI, UploadFile, File, HTTPException, Header, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, root_validator
from typing import Dict, Any, List, Optional, Tuple
import uuid
import json
import time

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
from .database import db, log_action 

# --- NEW IMPORTS FOR CHATBOT & ONBOARDING ---
from .chat_flow import process_onboarding_chat
from .models import ChatResponse
from .onboarding import router as onboarding_router

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
    """Upload and classify a document, save to user's Firebase profile."""
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")

    data = await file.read()
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

    doc_id = str(uuid.uuid4())
    
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
        "detection": detection,
        "extraction": extraction,
        "classification": classification,
        "validation": validation,
        "score": score_snapshot,
        "fmcsa_verification": fmcsa_summary, # Save FMCSA result to document
        "coach_plan": coach,                 # Save coach plan to document
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
        
        # Update user document with new documents array
        user_ref.update({
            "onboarding_data": json.dumps(existing_data),
            "updated_at": time.time()
        })
        
        log_action(uid, "DOCUMENT_UPLOAD", f"Document uploaded: {file.filename} (Type: {doc_type_upper})")
    except Exception as e:
        print(f"Warning: Could not save document to Firebase: {e}")
        # Don't fail the upload, continue with local storage
    
    return {
        "document_id": doc_id,
        "doc_type": record["doc_type"],
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
    uid = user['uid']
    
    # 1. Find the user's latest uploaded document associated with their ID
    # NOTE: This assumes store.get_latest_document_by_owner(uid) is available
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


@app.get("/loads")
def list_loads():
    return {"loads": store.list_loads()}


@app.post("/carriers")
def create_carrier(req: CarrierCreateRequest):
    payload = req.dict()
    store.save_carrier(payload)
    return payload


@app.get("/carriers")
def list_carriers():
    return {"carriers": store.list_carriers()}


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