# File: apps/api/models.py
from pydantic import BaseModel, EmailStr
from enum import Enum
from typing import Optional, Dict, Any, List
from datetime import datetime

# --- 1. Enums (Must be defined first) ---

class Role(str, Enum):
    CARRIER = "carrier"
    DRIVER = "driver"
    SHIPPER = "shipper"
    BROKER = "broker"
    ADMIN = "admin"
    SUPER_ADMIN = "super_admin"

class OnboardingStep(str, Enum):
    WELCOME = "WELCOME"
    SELECT_ROLE = "SELECT_ROLE"
    COLLECT_INFO = "COLLECT_INFO"
    UPLOAD_DOC = "UPLOAD_DOC"
    REVIEW_SCORE = "REVIEW_SCORE"
    CREATE_ACCOUNT = "CREATE_ACCOUNT"
    COMPLETED = "COMPLETED"

# --- 2. Auth Models ---

class UserSignup(BaseModel):
    email: EmailStr
    password: str
    name: str
    phone: Optional[str] = None
    role: Role
    company_name: Optional[str] = None

class SignupResponse(BaseModel):
    user_id: str
    email: str
    phone: Optional[str] = None
    role: str
    requires_email_verification: bool = True
    requires_phone_verification: bool = False
    message: str

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    user: Dict[str, Any]

class RefreshTokenRequest(BaseModel):
    refresh_token: str

class ProfileUpdate(BaseModel):
    company_name: Optional[str] = None
    dot_number: Optional[str] = None
    mc_number: Optional[str] = None
    cdl_number: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    phone: Optional[str] = None
    billing_address: Optional[str] = None

class UserProfile(BaseModel):
    uid: str
    email: str
    name: str
    phone: Optional[str] = None
    role: Role
    company_name: Optional[str] = None
    dot_number: Optional[str] = None
    mc_number: Optional[str] = None
    is_verified: bool = False
    mfa_enabled: bool = False
    onboarding_completed: bool = False
    onboarding_step: str = "WELCOME"
    onboarding_score: int = 0
    created_at: Optional[datetime] = None

# --- 3. Chat Models (Reference Enums above) ---

class ChatSession(BaseModel):
    session_id: str
    step: OnboardingStep = OnboardingStep.WELCOME
    role: Optional[Role] = None
    collected_data: Dict[str, Any] = {}
    document_ids: List[str] = []
    documents_with_scores: List[Dict[str, Any]] = []  # Track each doc with its score
    temp_score: float = 0.0  # Latest document score
    cumulative_score: float = 0.0  # Average of all documents
    missing_fields_across_docs: List[str] = []  # Aggregate missing fields
    compliance_score: float = 0.0

class ChatResponse(BaseModel):
    message: str
    next_step: OnboardingStep
    suggestions: List[str] = []
    ui_action: Optional[str] = None
    redirect_url: Optional[str] = None
    data_payload: Optional[Dict[str, Any]] = None

# --- 4. Onboarding Models ---

class OnboardingDataRequest(BaseModel):
    """Request model for onboarding data."""
    role: str
    data: Dict[str, Any]

class ChatbotAccountCreationRequest(BaseModel):
    """Request model for creating account from chatbot data."""
    role: str
    collected_data: Dict[str, Any]
    document_ids: List[str] = []
    documents: List[Dict[str, Any]] = []  # Full document data with scores
    compliance_score: float = 0.0
    missing_fields: List[str] = []  # Fields missing across all documents

class OnboardingStatusResponse(BaseModel):
    """Onboarding status response."""
    onboarding_completed: bool
    onboarding_step: str
    onboarding_score: int
    is_complete: bool
    current_step: Optional[str] = None
    progress: int = 0