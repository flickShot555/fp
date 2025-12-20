"""FreightPower AI Backend - Main Application."""
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
import logging

from .core.config import settings
from .core.database import engine, Base
from .routers import (
    auth, users, documents, loads, loads_applications,
    carriers, drivers, consents, messages, notifications,
    calendar, analytics, training, ai, settings as settings_router,
    onboarding, compliance
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events."""
    # Startup
    logger.info("Starting FreightPower AI Backend...")
    
    # Create database tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    logger.info("Database tables created/verified")
    
    # Start background scheduler if needed
    # scheduler.start()
    
    yield
    
    # Shutdown
    logger.info("Shutting down FreightPower AI Backend...")
    # scheduler.shutdown()
    await engine.dispose()


# Create FastAPI application
app = FastAPI(
    title="FreightPower AI API",
    description="Production-grade logistics SaaS backend for freight management",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# Custom CORS middleware that handles preflight properly
@app.middleware("http")
async def cors_handler(request: Request, call_next):
    """Handle CORS for all requests including preflight."""
    origin = request.headers.get("origin", "*")

    # Handle preflight OPTIONS request
    if request.method == "OPTIONS":
        response = JSONResponse(content={}, status_code=200)
        response.headers["Access-Control-Allow-Origin"] = "*"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS, PATCH"
        response.headers["Access-Control-Allow-Headers"] = "*"
        response.headers["Access-Control-Max-Age"] = "86400"
        return response

    # Log the request
    print(f">>> {request.method} {request.url.path} from {origin}")

    # Process the request
    response = await call_next(request)

    # Add CORS headers to response
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS, PATCH"
    response.headers["Access-Control-Allow-Headers"] = "*"

    print(f"<<< {request.method} {request.url.path} => {response.status_code}")
    return response


# Exception handlers
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle validation errors."""
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": exc.errors(), "body": exc.body},
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle general exceptions."""
    import traceback
    error_trace = traceback.format_exc()
    logger.error(f"Unhandled exception on {request.url.path}: {exc}")
    logger.error(f"Traceback: {error_trace}")
    print(f"ERROR on {request.url.path}: {exc}")
    print(f"Traceback: {error_trace}")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": f"Internal server error: {str(exc)}"},
    )


# Include routers
app.include_router(auth.router, prefix="/api/v1")
app.include_router(users.router, prefix="/api/v1")
app.include_router(documents.router, prefix="/api/v1")
app.include_router(loads.router, prefix="/api/v1")
app.include_router(loads_applications.router, prefix="/api/v1")
app.include_router(carriers.router, prefix="/api/v1")
app.include_router(drivers.router, prefix="/api/v1")
app.include_router(consents.router, prefix="/api/v1")
app.include_router(messages.router, prefix="/api/v1")
app.include_router(notifications.router, prefix="/api/v1")
app.include_router(calendar.router, prefix="/api/v1")
app.include_router(analytics.router, prefix="/api/v1")
app.include_router(training.router, prefix="/api/v1")
app.include_router(ai.router, prefix="/api/v1")
app.include_router(settings_router.router, prefix="/api/v1")
app.include_router(onboarding.router, prefix="/api/v1")
app.include_router(compliance.router, prefix="/api/v1")

# Also include routers without prefix for frontend compatibility
app.include_router(onboarding.router)
app.include_router(compliance.router)


# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "version": "1.0.0"}


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "name": "FreightPower AI API",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health",
    }


# Legacy endpoints for frontend compatibility (port 5000)
@app.post("/auth/signup")
async def legacy_signup(request: Request):
    """Legacy signup endpoint for frontend compatibility.

    Creates user in Firebase first, then in our database.
    Handles sync issues where user may exist in one system but not the other.
    """
    from .services.firebase_service import firebase_service
    from .core.database import AsyncSessionLocal
    from .models.user import UserRole, User
    from sqlalchemy import select
    from passlib.context import CryptContext

    try:
        body = await request.json()
    except Exception as e:
        logger.error(f"JSON parse error: {e}")
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    # Map frontend fields to backend fields
    email = body.get("email")
    password = body.get("password")
    name = body.get("name", "")
    phone = body.get("phone")
    role_str = body.get("role", "carrier").upper()

    if not email or not password:
        raise HTTPException(status_code=400, detail="Email and password are required")

    # Parse name into first_name and last_name
    name_parts = name.split(" ", 1) if name else ["", ""]
    first_name = name_parts[0] if len(name_parts) > 0 else ""
    last_name = name_parts[1] if len(name_parts) > 1 else ""

    # Map role string to enum
    role_mapping = {
        "CARRIER": UserRole.CARRIER,
        "DRIVER": UserRole.DRIVER,
        "SHIPPER": UserRole.SHIPPER,
        "ADMIN": UserRole.ADMIN,
        "SUPER_ADMIN": UserRole.SUPER_ADMIN,
    }
    role = role_mapping.get(role_str, UserRole.CARRIER)
    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

    # Step 1: Check if user exists in our database (email OR phone)
    async with AsyncSessionLocal() as db:
        # Check for duplicate email
        existing_result = await db.execute(select(User).where(User.email == email))
        existing_user = existing_result.scalar_one_or_none()

        if existing_user:
            # User exists in our database - they should login instead
            raise HTTPException(status_code=400, detail="This email is already registered. Please login instead.")

        # Check for duplicate phone number
        if phone:
            phone_result = await db.execute(select(User).where(User.phone == phone))
            phone_user = phone_result.scalar_one_or_none()

            if phone_user:
                raise HTTPException(status_code=400, detail="This phone number is already registered to another account.")

    # Step 2: Try to create user in Firebase
    firebase_uid = None
    try:
        firebase_user = await firebase_service.create_user(
            email=email,
            password=password,
            display_name=name,
            phone=phone,
            role=role_str.lower(),
        )
        firebase_uid = firebase_user.get("uid")
        logger.info(f"Created Firebase user: {firebase_uid}")

    except ValueError as e:
        error_msg = str(e)
        logger.warning(f"Firebase signup error: {error_msg}")

        # If user exists in Firebase but not in our DB, we need to sync
        if "EMAIL_EXISTS" in error_msg:
            # User exists in Firebase but not in our DB
            # Tell them to login - Firebase auth will work
            raise HTTPException(
                status_code=400,
                detail="This email is already registered. Please login instead."
            )
        raise HTTPException(status_code=400, detail=error_msg)
    except Exception as e:
        logger.error(f"Firebase error during signup: {e}")
        raise HTTPException(status_code=500, detail=f"Firebase error: {str(e)}")

    # Step 3: Create user in our database
    async with AsyncSessionLocal() as db:
        try:
            new_user = User(
                email=email,
                password_hash=pwd_context.hash(password),
                first_name=first_name,
                last_name=last_name,
                full_name=name,
                phone=phone,
                role=role,
                firebase_uid=firebase_uid,
                is_active=True,
                email_verified=False,
                onboarding_completed=False,
            )
            db.add(new_user)
            await db.commit()
            await db.refresh(new_user)

            logger.info(f"Created local user: {new_user.id} for {email}")

            return {
                "user_id": new_user.id,
                "firebase_uid": firebase_uid,
                "email": new_user.email,
                "phone": new_user.phone,
                "role": new_user.role.value,
                "requires_email_verification": True,
                "requires_phone_verification": False,
                "message": "User created successfully. Please verify your email."
            }
        except Exception as e:
            logger.error(f"Database error during signup: {e}")
            raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@app.post("/auth/verify-otp")
async def legacy_verify_otp(request: Request):
    """Legacy OTP verification endpoint."""
    from .services.auth_service import AuthService
    from .core.database import AsyncSessionLocal

    # Get token from Authorization header
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return {"verified": True, "message": "Verification successful"}

    try:
        body = await request.json()
    except:
        body = {}

    async with AsyncSessionLocal() as db:
        auth_service = AuthService(db)
        # For Firebase auth, we trust the token and mark as verified
        return {"verified": True, "message": "OTP verified successfully"}


@app.post("/auth/log-login")
async def legacy_log_login(request: Request):
    """Legacy login logging endpoint for frontend compatibility.

    Also handles syncing Firebase users to local database if they don't exist.
    """
    from .services.firebase_service import verify_firebase_token
    from .core.database import AsyncSessionLocal
    from .models.user import User, UserRole
    from sqlalchemy import select
    from passlib.context import CryptContext

    # Get token from Authorization header
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return {"message": "Login logged"}

    token = auth_header.split(" ")[1]

    try:
        # Verify the Firebase token
        payload = await verify_firebase_token(token)
        if not payload:
            return {"message": "Login logged"}

        firebase_uid = payload.get("uid")
        email = payload.get("email")

        if not firebase_uid or not email:
            return {"message": "Login logged"}

        # Check if user exists in our database
        async with AsyncSessionLocal() as db:
            result = await db.execute(select(User).where(User.firebase_uid == firebase_uid))
            user = result.scalar_one_or_none()

            if not user:
                # Also check by email
                result = await db.execute(select(User).where(User.email == email))
                user = result.scalar_one_or_none()

            if not user:
                # User exists in Firebase but not in our database - sync them
                logger.info(f"Syncing Firebase user to local DB: {email}")
                pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

                # Try to get role from Firestore via the payload
                role_str = payload.get("role", "carrier").upper()
                role_mapping = {
                    "CARRIER": UserRole.CARRIER,
                    "DRIVER": UserRole.DRIVER,
                    "SHIPPER": UserRole.SHIPPER,
                    "ADMIN": UserRole.ADMIN,
                    "SUPER_ADMIN": UserRole.SUPER_ADMIN,
                }
                role = role_mapping.get(role_str, UserRole.CARRIER)

                new_user = User(
                    email=email,
                    password_hash=pwd_context.hash("firebase-auth"),  # Placeholder
                    full_name=payload.get("name", ""),
                    first_name=payload.get("name", "").split(" ")[0] if payload.get("name") else "",
                    last_name=" ".join(payload.get("name", "").split(" ")[1:]) if payload.get("name") else "",
                    phone=payload.get("phone_number"),
                    role=role,
                    firebase_uid=firebase_uid,
                    is_active=True,
                    email_verified=payload.get("email_verified", False),
                    onboarding_completed=False,
                )
                db.add(new_user)
                await db.commit()
                logger.info(f"Created local user from Firebase: {email}")

        return {"message": "Login logged successfully"}
    except Exception as e:
        logger.error(f"Error in log-login: {e}")
        # Don't fail the request if logging fails
        return {"message": "Login logged"}


@app.get("/onboarding/coach-status")
async def get_coach_status(request: Request):
    """
    Get onboarding coach status with score, checklist, and next best actions.
    Returns data for the Dashboard Onboarding Coach component.
    """
    from .services.firebase_service import verify_firebase_token
    from .core.database import get_db
    from .services.onboarding_service import OnboardingService
    from sqlalchemy import select
    from .models.user import User
    from .models.document import Document

    # Get Firebase token from Authorization header
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        # Return default state for unauthenticated users
        return {
            "status_color": "Red",
            "total_score": 0,
            "checklist": [],
            "next_best_actions": ["Please log in to view your onboarding status"],
            "is_marketplace_ready": False,
            "fmcsa_status": "N/A"
        }

    token = auth_header.split(" ")[1]

    try:
        # Verify Firebase token
        firebase_user = await verify_firebase_token(token)
        email = firebase_user.get("email", "")
        email_verified = firebase_user.get("email_verified", False)

        # Get user from database
        async for db in get_db():
            onboarding_service = OnboardingService(db)

            # Find user by email
            result = await db.execute(select(User).where(User.email == email))
            user = result.scalar_one_or_none()

            if not user:
                return {
                    "status_color": "Red",
                    "total_score": 0,
                    "checklist": [],
                    "next_best_actions": ["Complete your account registration"],
                    "is_marketplace_ready": False,
                    "fmcsa_status": "N/A"
                }

            # Get documents for user
            docs_result = await db.execute(select(Document).where(Document.owner_id == user.id))
            documents = list(docs_result.scalars().all())

            # Build user data dict
            user_data = {
                "email": user.email,
                "email_verified": email_verified,
                "phone": user.phone,
                "phone_verified": user.phone_verified if hasattr(user, "phone_verified") else False,
                "mfa_enabled": user.mfa_enabled if hasattr(user, "mfa_enabled") else False,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "company_name": getattr(user, "company_name", None),
                "dot_number": getattr(user, "dot_number", None),
                "mc_number": getattr(user, "mc_number", None),
                "cdl_number": getattr(user, "cdl_number", None),
                "billing_address": getattr(user, "billing_address", None),
            }

            # Get role
            role = user.role.value if user.role else "carrier"

            # Calculate onboarding status using service
            status = await onboarding_service.get_onboarding_status(user.id)

            # Calculate score and status color
            progress = status.get("progress", 0)
            total_score = int(progress)

            if total_score >= 80:
                status_color = "Green"
            elif total_score >= 50:
                status_color = "Amber"
            else:
                status_color = "Red"

            # Build checklist from steps
            checklist = []
            for step in status.get("steps", []):
                checklist.append({
                    "id": step.get("id"),
                    "label": step.get("title"),
                    "completed": step.get("completed", False),
                    "description": step.get("description")
                })

            # Build next best actions
            next_best_actions = []
            next_action = status.get("next_action", {})
            if next_action.get("message"):
                next_best_actions.append(next_action["message"])

            # Add more actions based on incomplete steps
            for step in status.get("steps", []):
                if not step.get("completed"):
                    next_best_actions.append(f"{step.get('title')}: {step.get('description')}")
                if len(next_best_actions) >= 3:
                    break

            # Check FMCSA status (for carriers)
            fmcsa_status = "N/A"
            if role == "carrier" and getattr(user, "dot_number", None):
                fmcsa_status = "Pending Verification"
                # TODO: Actually check FMCSA API

            # Marketplace is gated until score >= 60
            is_marketplace_ready = total_score >= 60

            return {
                "status_color": status_color,
                "total_score": total_score,
                "checklist": checklist,
                "next_best_actions": next_best_actions if next_best_actions else ["All steps completed!"],
                "is_marketplace_ready": is_marketplace_ready,
                "is_ready": is_marketplace_ready,
                "fmcsa_status": fmcsa_status,
                "role": role,
                "progress": progress
            }

    except Exception as e:
        import traceback
        traceback.print_exc()
        return {
            "status_color": "Gray",
            "total_score": 0,
            "checklist": [],
            "next_best_actions": [f"Error loading status: {str(e)}"],
            "is_marketplace_ready": False,
            "fmcsa_status": "N/A"
        }


# In-memory document store for chatbot (temporary for guest users)
_temp_documents: dict = {}


@app.post("/chat/onboarding")
async def chat_onboarding(request: Request):
    """Stateful chatbot endpoint for landing page onboarding."""
    from .services.chat_flow import process_onboarding_chat

    try:
        body = await request.json()
    except:
        body = {}

    session_id = body.get("session_id", "default")
    message = body.get("message", "")
    attached_doc_id = body.get("attached_document_id")

    logger.info(f"📨 Chat message received: session_id={session_id}, message='{message[:50]}...', attached_doc_id={attached_doc_id}")

    # If document was attached, get its data
    doc_event = None
    document_data = None
    if attached_doc_id:
        doc_event = {"document_id": attached_doc_id}
        document_data = _temp_documents.get(attached_doc_id)
        
        if document_data:
            logger.info(f"✅ Document found in cache: doc_id={attached_doc_id}, doc_type={document_data.get('doc_type')}")
        else:
            logger.warning(f"❌ Document NOT found in cache: doc_id={attached_doc_id}, available_docs={list(_temp_documents.keys())}")

    # Process through chat flow (now async)
    response = await process_onboarding_chat(
        session_id=session_id,
        user_text=message,
        doc_event=doc_event,
        document_data=document_data,
    )

    logger.info(f"💬 Chat response: message='{response.message[:50]}...', next_step={response.next_step}")

    return {
        "message": response.message,
        "next_step": response.next_step,
        "suggestions": response.suggestions,
        "ui_action": response.ui_action,
        "data_payload": response.data_payload,
    }


@app.post("/documents")
@app.post("/documents/upload")
async def upload_document(request: Request):
    """Document upload endpoint for chatbot and dashboard with Firebase auth."""
    import uuid
    from .services.ai_service import AIService
    from .services.firebase_service import verify_firebase_token
    from .services.document_service import DocumentService
    from .models.document import DocumentType

    # Verify Firebase token
    auth_header = request.headers.get("Authorization")
    user_email = None
    user_id = None

    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.split(" ")[1]
        try:
            firebase_user = await verify_firebase_token(token)
            user_email = firebase_user.get("email", "")
            firebase_uid = firebase_user.get("uid", "")

            # Get or create user from database
            async for db in get_db():
                result = await db.execute(select(User).where(User.email == user_email))
                user = result.scalar_one_or_none()
                if user:
                    user_id = user.id
                elif firebase_uid:
                    # Create user if doesn't exist
                    from .models.user import UserRole
                    new_user = User(
                        email=user_email,
                        firebase_uid=firebase_uid,
                        full_name=firebase_user.get("name", user_email.split("@")[0]),
                        role=UserRole.CARRIER,  # Default role
                        is_active=True,
                        is_verified=True,
                    )
                    db.add(new_user)
                    await db.commit()
                    await db.refresh(new_user)
                    user_id = new_user.id
                    logger.info(f"Created new user {user_email} with id {user_id}")
                break
        except Exception as e:
            logger.warning(f"Auth error: {e}")

    # Handle multipart form data
    form = await request.form()
    file = form.get("file")
    document_type_str = form.get("document_type", "other")
    expiry_date_str = form.get("expiry_date")

    if not file:
        raise HTTPException(status_code=400, detail="No file provided")

    try:
        # Read file content
        file_content = await file.read()
        filename = file.filename or "document.pdf"
        mime_type = file.content_type or "application/octet-stream"

        logger.info(f"📄 Document upload received: filename={filename}, mime_type={mime_type}, size={len(file_content)} bytes")

        # Generate unique document ID
        doc_id = str(uuid.uuid4())

        # Perform AI document classification and OCR
        ai_service = AIService()

        # Try to classify the document
        try:
            logger.info(f"🤖 Starting AI classification for {filename}")
            classification = await ai_service.classify_document(file_content, mime_type)
            doc_type = classification.get("type", document_type_str)
            confidence = classification.get("confidence", 0.0)
            logger.info(f"✅ AI Classification complete: doc_type={doc_type}, confidence={confidence}")
        except Exception as e:
            logger.error(f"❌ AI classification failed: {e}")
            doc_type = document_type_str
            confidence = 0.0

        # Try to extract data (including expiry dates)
        try:
            logger.info(f"🔍 Starting data extraction for doc_type={doc_type}")
            extraction = await ai_service.extract_document_data(file_content, mime_type, doc_type)
            extracted_data = extraction.get("data", {})
            logger.info(f"✅ Data extraction complete: {list(extracted_data.keys())}")
        except Exception as e:
            logger.error(f"❌ Data extraction failed: {e}")
            extracted_data = {}

        # Calculate provisional onboarding score (0-100)
        score = 50  # Base score
        if confidence > 0.8:
            score += 20
        if extracted_data:
            score += min(len(extracted_data) * 5, 30)  # Up to 30 points for extracted fields

        # Check for expiry dates - use extracted or provided
        expiry_date = extracted_data.get("expiry_date") or extracted_data.get("expires_at") or expiry_date_str
        validation_issues = []
        parsed_expiry = None

        if expiry_date:
            try:
                from datetime import datetime
                if isinstance(expiry_date, str):
                    parsed_expiry = datetime.strptime(str(expiry_date), "%Y-%m-%d")
                else:
                    parsed_expiry = expiry_date

                if parsed_expiry < datetime.now():
                    validation_issues.append("Document is expired")
                    score -= 20
            except:
                pass

        # Save to database if user is authenticated
        if user_id:
            async for db in get_db():
                try:
                    document_service = DocumentService(db)

                    # Map document type string to enum
                    try:
                        doc_type_enum = DocumentType(doc_type.lower())
                    except:
                        doc_type_enum = DocumentType.OTHER

                    saved_doc = await document_service.upload_document(
                        file_content=file_content,
                        filename=filename,
                        mime_type=mime_type,
                        owner_id=user_id,
                        document_type=doc_type_enum,
                        expiry_date=parsed_expiry,
                    )
                    doc_id = saved_doc.id
                except Exception as e:
                    logger.warning(f"Failed to save document to DB: {e}")
                break

        # Store document data for chatbot
        document_data = {
            "document_id": doc_id,
            "filename": filename,
            "doc_type": doc_type.upper(),
            "confidence": confidence,
            "extraction": extracted_data,
            "validation": {"status": "valid" if not validation_issues else "issues", "issues": validation_issues},
            "score": {"total_score": max(0, min(100, score))},
        }
        _temp_documents[doc_id] = document_data
        logger.info(f"💾 Document stored in temp cache: doc_id={doc_id}, doc_type={document_data['doc_type']}")

        # Update user profile with extracted DOT/MC numbers if present
        if user_id and extracted_data:
            async for db in get_db():
                try:
                    result = await db.execute(select(User).where(User.id == user_id))
                    user = result.scalar_one_or_none()
                    if user:
                        # Update DOT number if present in extraction
                        if extracted_data.get("dot_number") and not user.dot_number:
                            user.dot_number = extracted_data.get("dot_number")
                        # Update MC number if present in extraction
                        if extracted_data.get("mc_number") and not user.mc_number:
                            user.mc_number = extracted_data.get("mc_number")
                        # Update company name if present in extraction
                        if extracted_data.get("company_name") and not user.company_name:
                            user.company_name = extracted_data.get("company_name")
                        await db.commit()
                        logger.info(f"✅ User profile updated with extracted data: {list(extracted_data.keys())}")
                except Exception as e:
                    logger.warning(f"Failed to update user profile with extracted data: {e}")
                break

        logger.info(f"📤 Returning document response: doc_id={doc_id}, doc_type={doc_type.upper()}, confidence={confidence}")
        return {
            "document_id": doc_id,
            "id": doc_id,
            "filename": filename,
            "doc_type": doc_type.upper(),
            "confidence": confidence,
            "score": {"total_score": score},
            "validation": {"status": "valid" if not validation_issues else "issues", "issues": validation_issues},
            "extraction": extracted_data,
            "expiry_date": str(parsed_expiry.date()) if parsed_expiry else None,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Document processing failed: {str(e)}")


@app.get("/documents")
async def legacy_list_documents(request: Request):
    """Document list endpoint with Firebase auth."""
    from .services.document_service import DocumentService
    from .services.firebase_service import verify_firebase_token

    # Verify Firebase token to get user's documents
    auth_header = request.headers.get("Authorization")
    user_id = None

    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.split(" ")[1]
        try:
            firebase_user = await verify_firebase_token(token)
            user_email = firebase_user.get("email", "")
            firebase_uid = firebase_user.get("uid", "")

            # Get or create user from database
            async for db in get_db():
                result = await db.execute(select(User).where(User.email == user_email))
                user = result.scalar_one_or_none()
                if user:
                    user_id = user.id
                elif firebase_uid:
                    # Create user if doesn't exist
                    from .models.user import UserRole
                    new_user = User(
                        email=user_email,
                        firebase_uid=firebase_uid,
                        full_name=firebase_user.get("name", user_email.split("@")[0]),
                        role=UserRole.CARRIER,
                        is_active=True,
                        is_verified=True,
                    )
                    db.add(new_user)
                    await db.commit()
                    await db.refresh(new_user)
                    user_id = new_user.id
                break
        except Exception as e:
            logger.warning(f"Firebase token verification failed: {e}")
            return {"documents": [], "total": 0, "error": "Invalid or expired token"}

    try:
        async for db in get_db():
            document_service = DocumentService(db)
            documents, total = await document_service.list_documents(owner_id=user_id)
            # Convert to dict for JSON response
            docs_list = [
                {
                    "id": doc.id,
                    "filename": doc.original_filename or doc.filename,
                    "type": doc.document_type.value if doc.document_type else "other",
                    "status": doc.status or "uploaded",
                    "expiry_date": doc.expiry_date.isoformat() if doc.expiry_date else None,
                    "file_size": doc.file_size,
                    "validation_score": doc.validation_score,
                    "created_at": doc.created_at.isoformat() if doc.created_at else None,
                }
                for doc in documents
            ]
            return {"documents": docs_list, "total": total}
    except Exception as e:
        logger.error(f"Error listing documents: {e}")
        return {"documents": [], "total": 0}


@app.get("/auth/me")
async def legacy_get_current_user(request: Request):
    """Legacy get current user endpoint."""
    from .core.security import decode_access_token

    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return {"error": "Not authenticated"}

    token = auth_header.split(" ")[1]
    payload = decode_access_token(token)

    if not payload:
        return {"error": "Invalid token"}

    return {
        "id": payload.get("sub"),
        "email": payload.get("email"),
        "role": payload.get("role"),
    }


# FMCSA Verification Endpoint
@app.post("/fmcsa/verify")
async def verify_fmcsa(request: Request):
    """Verify carrier FMCSA status by DOT/MC number."""
    from .services.firebase_service import verify_firebase_token
    from .services.fmcsa_service import FMCSAService

    # Verify Firebase token
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Authorization required")

    token = auth_header.split(" ")[1]
    try:
        await verify_firebase_token(token)
    except Exception as e:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    try:
        body = await request.json()
        usdot = body.get("usdot")
        mc_number = body.get("mc_number")

        if not usdot and not mc_number:
            raise HTTPException(status_code=400, detail="Either usdot or mc_number is required")

        fmcsa_service = FMCSAService()

        if usdot:
            result = await fmcsa_service.lookup_carrier_by_usdot(usdot)
        else:
            result = await fmcsa_service.lookup_carrier_by_mc(mc_number)

        if result:
            return {
                "result": "Verified",
                "carrier_name": result.get("legalName", ""),
                "dot_number": result.get("dotNumber", usdot),
                "mc_number": result.get("mcNumber", mc_number),
                "status": result.get("carrierOperation", {}).get("carrierOperationDesc", "Unknown"),
                "safety_rating": result.get("safetyRating", "Not Rated"),
                "last_updated": result.get("lastUpdated", None),
                "data": result
            }
        else:
            return {
                "result": "Not Found",
                "message": "Carrier not found in FMCSA database"
            }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"FMCSA verification error: {e}")
        return {
            "result": "Error",
            "message": str(e)
        }


@app.get("/fmcsa/{usdot}")
async def get_fmcsa_carrier(usdot: str, request: Request):
    """Get carrier info from FMCSA by DOT number."""
    from .services.firebase_service import verify_firebase_token
    from .services.fmcsa_service import FMCSAService

    # Verify Firebase token
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Authorization required")

    token = auth_header.split(" ")[1]
    try:
        await verify_firebase_token(token)
    except Exception as e:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    try:
        fmcsa_service = FMCSAService()
        result = await fmcsa_service.lookup_carrier_by_usdot(usdot)

        if result:
            return result
        else:
            raise HTTPException(status_code=404, detail="Carrier not found")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"FMCSA lookup error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Onboarding Save Endpoint
@app.post("/onboarding/save")
async def save_onboarding_data(request: Request):
    """Save onboarding data for carrier/driver/shipper with AI-calculated score."""
    from .services.firebase_service import verify_firebase_token
    from .core.database import AsyncSessionLocal
    from .models.user import User
    from sqlalchemy import select
    import json

    # Verify Firebase token
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Authorization required")

    token = auth_header.split(" ")[1]
    try:
        firebase_user = await verify_firebase_token(token)
        firebase_uid = firebase_user.get("uid")
        email = firebase_user.get("email")
    except Exception as e:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    try:
        body = await request.json()
        role = body.get("role", "carrier")
        onboarding_data = body.get("data", {})

        async with AsyncSessionLocal() as db:
            # Find user by Firebase UID or email
            result = await db.execute(
                select(User).where(
                    (User.firebase_uid == firebase_uid) | (User.email == email)
                )
            )
            user = result.scalar_one_or_none()

            if not user:
                raise HTTPException(status_code=404, detail="User not found")

            # Calculate AI-based onboarding score
            onboarding_score = calculate_onboarding_score(role, onboarding_data)

            # Save onboarding data as JSON in a new column or update profile fields
            user.onboarding_data = json.dumps(onboarding_data)
            user.onboarding_completed = True
            user.onboarding_score = onboarding_score

            # Also update specific fields if provided
            if onboarding_data.get("companyName"):
                user.company_name = onboarding_data.get("companyName")
            if onboarding_data.get("dotNumber"):
                user.dot_number = onboarding_data.get("dotNumber")
            if onboarding_data.get("mcNumber"):
                user.mc_number = onboarding_data.get("mcNumber")
            if onboarding_data.get("fullName"):
                user.full_name = onboarding_data.get("fullName")
            if onboarding_data.get("businessName"):
                user.company_name = onboarding_data.get("businessName")

            await db.commit()

            return {
                "success": True,
                "message": "Onboarding data saved successfully",
                "onboarding_completed": True,
                "onboarding_score": onboarding_score
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error saving onboarding data: {e}")
        raise HTTPException(status_code=500, detail=str(e))


def calculate_onboarding_score(role: str, data: dict) -> int:
    """
    AI-based onboarding score calculation.
    Scores are based on completeness and quality of provided data.
    """
    score = 0
    max_score = 100

    if role == "carrier":
        # Carrier scoring weights
        fields = {
            "companyName": 15,
            "dotNumber": 15,
            "mcNumber": 10,
            "einNumber": 10,
            "companyAddress": 5,
            "contactEmail": 5,
            "contactPhone": 5,
            "ownerName": 5,
            "fleetSize": 10,
            "equipmentType": 5,
            "insuranceProvider": 10,
            "eldProvider": 5,
        }
    elif role == "driver":
        # Driver scoring weights
        fields = {
            "fullName": 15,
            "phone": 10,
            "email": 10,
            "cdlNumber": 20,
            "issuingState": 10,
            "cdlClass": 10,
            "endorsements": 5,
            "preferredRegions": 5,
            "availableStartDate": 5,
            "equipmentExperience": 10,
        }
    elif role == "shipper":
        # Shipper scoring weights
        fields = {
            "businessName": 15,
            "businessType": 5,
            "taxId": 10,
            "businessAddress": 10,
            "businessEmail": 10,
            "contactFullName": 10,
            "contactEmail": 10,
            "freightType": 10,
            "avgMonthlyVolume": 10,
            "regionsOfOperation": 10,
        }
    else:
        return 50  # Default score for unknown roles

    # Calculate score based on filled fields
    for field, weight in fields.items():
        value = data.get(field)
        if value and str(value).strip():
            score += weight

    # Ensure score doesn't exceed max
    return min(score, max_score)


# Get Onboarding Data Endpoint
@app.get("/onboarding/data")
async def get_onboarding_data(request: Request):
    """Get onboarding data for current user."""
    from .services.firebase_service import verify_firebase_token
    from .core.database import AsyncSessionLocal
    from .models.user import User
    from sqlalchemy import select
    import json

    # Verify Firebase token
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Authorization required")

    token = auth_header.split(" ")[1]
    try:
        firebase_user = await verify_firebase_token(token)
        firebase_uid = firebase_user.get("uid")
        email = firebase_user.get("email")
    except Exception as e:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    try:
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(User).where(
                    (User.firebase_uid == firebase_uid) | (User.email == email)
                )
            )
            user = result.scalar_one_or_none()

            if not user:
                raise HTTPException(status_code=404, detail="User not found")

            onboarding_data = {}
            if user.onboarding_data:
                try:
                    onboarding_data = json.loads(user.onboarding_data)
                except:
                    pass

            return {
                "onboarding_completed": user.onboarding_completed,
                "onboarding_score": user.onboarding_score if hasattr(user, 'onboarding_score') else 0,
                "data": onboarding_data,
                "company_name": user.company_name,
                "dot_number": user.dot_number,
                "mc_number": user.mc_number,
                "full_name": user.full_name if hasattr(user, 'full_name') else None
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting onboarding data: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# WebSocket endpoint
from fastapi import WebSocket

@app.websocket("/ws/{token}")
async def websocket_route(websocket: WebSocket, token: str):
    """WebSocket endpoint for real-time communication."""
    from .websocket import websocket_endpoint
    await websocket_endpoint(websocket, token)

