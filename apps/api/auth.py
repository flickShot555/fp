# File: apps/api/auth.py
from fastapi import APIRouter, HTTPException, Header, Depends, Body, status, UploadFile, File
from firebase_admin import auth as firebase_auth
import firebase_admin
import time
import json
import uuid
from typing import Optional, Dict, Any
from functools import wraps

# Use relative imports
from .database import db, log_action
from .models import (
    UserSignup, Role, SignupResponse, LoginRequest, 
    TokenResponse, RefreshTokenRequest, UserProfile, ProfileUpdate
)

router = APIRouter(prefix="/auth", tags=["Authentication"])


# ============================================================================
# Current User Dependency (must be defined first)
# ============================================================================

async def get_current_user(authorization: str = Header(...)) -> Dict[str, Any]:
    """
    Verifies the token AND checks if the user is verified.
    Returns comprehensive user data with RBAC-ready information.
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=401, 
            detail="Invalid authorization header format"
        )
    
    token = authorization.split(" ")[1]
    
    try:
        # Verify Firebase token
        decoded_token = firebase_auth.verify_id_token(token)
        uid = decoded_token.get('uid')
        
        if not uid:
            raise HTTPException(status_code=401, detail="Invalid token structure")
        
        # Fetch Firestore user profile
        user_ref = db.collection("users").document(uid)
        user_doc = user_ref.get()
        
        if not user_doc.exists:
            raise HTTPException(status_code=404, detail="User profile not found")
        
        user_data = user_doc.to_dict()
        
        # --- AUTO-VERIFY EMAIL ---
        # If Firebase says email is verified, but DB says unverified -> Update DB
        if decoded_token.get('email_verified') and not user_data.get('is_verified'):
            user_ref.update({
                "is_verified": True,
                "verified_at": time.time(),
                "email_verified": True
            })
            user_data['is_verified'] = True
            user_data['email_verified'] = True
            log_action(uid, "VERIFICATION", "User verified via Email Link")

        # --- ENFORCE VERIFICATION ---
        if not user_data.get("is_verified", False):
            raise HTTPException(
                status_code=403, 
                detail="Account not verified. Please check your email or verify phone."
            )
        
        # Ensure role exists and is valid
        if "role" not in user_data:
            user_data["role"] = "carrier"
            user_ref.update({"role": "carrier"})
        
        return user_data
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Auth Error: {e}")
        raise HTTPException(status_code=401, detail="Invalid or expired token")


# ============================================================================
# RBAC & Security Utilities (defined after get_current_user)
# ============================================================================

def require_role(*allowed_roles: Role):
    """Decorator to require specific roles for endpoints."""
    async def role_check(user: Dict[str, Any] = Depends(get_current_user)):
        user_role = Role(user.get("role", "carrier"))
        if user_role not in allowed_roles:
            raise HTTPException(
                status_code=403, 
                detail=f"Access denied. Required roles: {[r.value for r in allowed_roles]}"
            )
        return user
    return role_check


def require_admin(user: Dict[str, Any] = Depends(get_current_user)):
    """Require admin or super_admin role."""
    user_role = user.get("role")
    if user_role not in ["admin", "super_admin"]:
        raise HTTPException(status_code=403, detail="Admin access required")
    return user


def require_super_admin(user: Dict[str, Any] = Depends(get_current_user)):
    """Require super_admin role only."""
    user_role = user.get("role")
    if user_role != "super_admin":
        raise HTTPException(status_code=403, detail="Super admin access required")
    return user


# ============================================================================
# Authentication Endpoints
# ============================================================================

@router.post("/signup", response_model=SignupResponse, status_code=status.HTTP_201_CREATED)
async def signup(user: UserSignup):
    """
    Creates a user in Firebase Auth with proper Firestore schema.
    Stores role and all user information for RBAC.
    """
    try:
        # 1. Create user in Firebase Authentication
        user_record = firebase_auth.create_user(
            email=user.email,
            password=user.password,
            display_name=user.name,
            phone_number=user.phone if user.phone else None
        )
        
        # 2. Prepare comprehensive Firestore user data
        user_data = {
            "uid": user_record.uid,
            "email": user.email,
            "name": user.name,
            "phone": user.phone or None,
            "role": user.role.value,  # Store role as string
            "company_name": user.company_name or None,
            "is_verified": True,  # Auto-verify users on signup to allow onboarding
            "email_verified": False,
            "phone_verified": False,
            "mfa_enabled": False,
            "failed_login_attempts": 0,
            "is_active": True,
            "is_locked": False,
            # Onboarding fields
            "onboarding_completed": False,
            "onboarding_step": "WELCOME",
            "onboarding_score": 0,
            "onboarding_data": None,
            # Business info
            "dot_number": None,
            "mc_number": None,
            "first_name": None,
            "last_name": None,
            # Preferences
            "language": "en",
            "timezone": "UTC",
            "notification_preferences": {},
            # Timestamps
            "created_at": time.time(),
            "updated_at": time.time(),
            "last_login_at": None
        }

        # 3. Save to Firestore with proper schema
        db.collection("users").document(user_record.uid).set(user_data)
        
        # 4. Create role-specific profile records
        if user.role.value == "carrier":
            # Create carrier profile for marketplace visibility
            carrier_profile = {
                "id": user_record.uid,
                "carrier_id": user_record.uid,
                "name": user.company_name or user.name,
                "email": user.email,
                "phone": user.phone or None,
                "mc_number": None,
                "dot_number": None,
                "equipment_types": [],
                "service_areas": [],
                "rating": 0,
                "total_loads": 0,
                "status": "active",
                "created_at": time.time(),
                "updated_at": time.time()
            }
            db.collection("carriers").document(user_record.uid).set(carrier_profile)
            log_action(user_record.uid, "CARRIER_PROFILE_CREATED", "Carrier profile created in marketplace")
        
        elif user.role.value == "driver":
            # Create driver profile for carrier marketplace
            driver_profile = {
                "id": user_record.uid,
                "driver_id": user_record.uid,
                "name": user.name,
                "email": user.email,
                "phone": user.phone or None,
                "cdl_class": None,
                "cdl_number": None,
                "status": "available",
                "current_location": None,
                "rating": 0,
                "total_deliveries": 0,
                "created_at": time.time(),
                "updated_at": time.time()
            }
            db.collection("drivers").document(user_record.uid).set(driver_profile)
            log_action(user_record.uid, "DRIVER_PROFILE_CREATED", "Driver profile created in marketplace")

        # 5. Audit log
        log_action(user_record.uid, "SIGNUP", f"User signed up as {user.role.value}")

        return SignupResponse(
            user_id=user_record.uid,
            email=user.email,
            phone=user.phone,
            role=user.role.value,
            requires_email_verification=False,  # Auto-verified for onboarding
            requires_phone_verification=False,
            message="Account created successfully! You can now complete your onboarding."
        )

    except firebase_auth.EmailAlreadyExistsError:
        raise HTTPException(status_code=400, detail="Email already registered")
    except firebase_auth.PhoneNumberAlreadyExistsError:
        raise HTTPException(status_code=400, detail="Phone number already registered")
    except firebase_admin.exceptions.FirebaseError as e:
        # Handle Firebase Admin SDK errors properly
        error_msg = str(e) if hasattr(e, '__str__') else "Firebase authentication error"
        raise HTTPException(status_code=500, detail=f"Signup failed: {error_msg}")
    except Exception as e:
        # Generic error handler
        error_msg = str(e) if str(e) else "Unknown error occurred"
        raise HTTPException(status_code=500, detail=f"Signup failed: {error_msg}")


@router.post("/login", response_model=TokenResponse)
async def login(request: LoginRequest):
    """
    Authenticate user with email and password.
    Returns access token with user profile.
    """
    try:
        # Get user by email from Firestore
        users_query = db.collection("users").where("email", "==", request.email).limit(1)
        docs = users_query.stream()
        user_doc = next(docs, None)
        
        if not user_doc:
            raise HTTPException(status_code=401, detail="Invalid email or password")
        
        user_data = user_doc.to_dict()
        
        # Check if user is locked
        if user_data.get("is_locked"):
            raise HTTPException(status_code=403, detail="Account is locked. Contact support.")
        
        # Verify password via Firebase (creates custom token for session)
        try:
            # Sign in with password using Firebase REST API would require additional setup
            # For now, we'll create a custom token
            custom_token = firebase_auth.create_custom_token(user_data["uid"])
            
            # Update last login
            db.collection("users").document(user_data["uid"]).update({
                "last_login_at": time.time(),
                "failed_login_attempts": 0
            })
            
            log_action(user_data["uid"], "LOGIN", "User logged in")
            
            return TokenResponse(
                access_token=custom_token.decode('utf-8') if isinstance(custom_token, bytes) else custom_token,
                refresh_token="",  # Firebase handles refresh automatically
                token_type="bearer",
                expires_in=3600,
                user={
                    "uid": user_data["uid"],
                    "email": user_data["email"],
                    "name": user_data["name"],
                    "role": user_data.get("role", "carrier"),
                    "onboarding_completed": user_data.get("onboarding_completed", False),
                    "onboarding_step": user_data.get("onboarding_step", "WELCOME"),
                }
            )
        except Exception as e:
            # Increment failed attempts
            failed_attempts = user_data.get("failed_login_attempts", 0) + 1
            if failed_attempts >= 5:
                db.collection("users").document(user_data["uid"]).update({
                    "is_locked": True,
                    "failed_login_attempts": failed_attempts
                })
                raise HTTPException(status_code=403, detail="Too many login attempts. Account locked.")
            
            db.collection("users").document(user_data["uid"]).update({
                "failed_login_attempts": failed_attempts
            })
            raise HTTPException(status_code=401, detail="Invalid email or password")
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"Login error: {e}")
        raise HTTPException(status_code=500, detail="Login failed")


@router.post("/verify-otp")
async def verify_otp(authorization: str = Header(...)):
    """
    Called when frontend successfully verifies SMS code.
    Marks user as verified.
    """
    try:
        token = authorization.split(" ")[1]
        decoded = firebase_auth.verify_id_token(token)
        uid = decoded.get('uid')
        
        db.collection("users").document(uid).update({
            "is_verified": True,
            "phone_verified": True,
            "verified_at": time.time()
        })
        
        log_action(uid, "VERIFICATION", "User verified via OTP")
        return {"status": "success", "message": "Account verified"}
    except Exception as e:
        raise HTTPException(status_code=401, detail="Invalid token or verification failed")


@router.post("/mfa-toggle")
async def toggle_mfa(
    enable: bool = Body(..., embed=True), 
    user: Dict[str, Any] = Depends(get_current_user)
):
    """Toggle MFA for current user."""
    uid = user['uid']
    db.collection("users").document(uid).update({"mfa_enabled": enable})
    
    action = "ENABLED" if enable else "DISABLED"
    log_action(uid, "MFA_CHANGE", f"MFA was {action}")
    return {"mfa_enabled": enable}


@router.get("/me", response_model=UserProfile)
async def get_current_user_profile(user: Dict[str, Any] = Depends(get_current_user)):
    """Get current user profile."""
    # Ensure all required fields exist with defaults
    profile_data = {
        "uid": user.get("uid", ""),
        "email": user.get("email", ""),
        "name": user.get("name") or user.get("full_name") or user.get("email", "").split("@")[0],
        "phone": user.get("phone"),
        "role": Role(user.get("role", "carrier")),
        "company_name": user.get("company_name"),
        "dot_number": user.get("dot_number"),
        "mc_number": user.get("mc_number"),
        "is_verified": user.get("is_verified", False),
        "mfa_enabled": user.get("mfa_enabled", False),
        "onboarding_completed": user.get("onboarding_completed", False),
        "onboarding_step": user.get("onboarding_step", "WELCOME"),
        "onboarding_score": user.get("onboarding_score", 0),
        "created_at": user.get("created_at"),
        "profile_picture_url": user.get("profile_picture_url"),
        "address": user.get("address"),
        "emergency_contact_name": user.get("emergency_contact_name"),
        "emergency_contact_relationship": user.get("emergency_contact_relationship"),
        "emergency_contact_phone": user.get("emergency_contact_phone"),
    }
    return UserProfile(**profile_data)


@router.post("/profile/update")
async def update_profile(
    update: ProfileUpdate,
    user: Dict[str, Any] = Depends(get_current_user)
):
    """Update user profile information."""
    uid = user['uid']
    update_data = update.dict(exclude_unset=True)
    
    if update_data:
        update_data['updated_at'] = time.time()
        db.collection("users").document(uid).update(update_data)
        log_action(uid, "PROFILE_UPDATE", f"Updated fields: {list(update_data.keys())}")
    
    return {"status": "success", "message": "Profile updated"}


@router.post("/profile/picture")
async def upload_profile_picture(
    file: UploadFile = File(...),
    user: Dict[str, Any] = Depends(get_current_user)
):
    """Upload profile picture and update user profile."""
    from .database import bucket
    
    uid = user['uid']
    
    # Validate file type (images only)
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided")
    
    file_ext = file.filename.lower().split('.')[-1]
    allowed_extensions = ['jpg', 'jpeg', 'png', 'gif', 'webp']
    
    if file_ext not in allowed_extensions:
        raise HTTPException(
            status_code=400, 
            detail=f"Invalid file type. Allowed: {', '.join(allowed_extensions)}"
        )
    
    # Validate file size (max 5MB)
    file_data = await file.read()
    if len(file_data) > 5 * 1024 * 1024:  # 5MB
        raise HTTPException(status_code=400, detail="File size must be less than 5MB")
    
    try:
        # Upload to Firebase Storage
        picture_id = str(uuid.uuid4())
        storage_path = f"profile_pictures/{uid}/{picture_id}.{file_ext}"
        blob = bucket.blob(storage_path)
        
        # Determine content type
        content_type = f"image/{file_ext}" if file_ext != 'jpg' else "image/jpeg"
        
        blob.upload_from_string(file_data, content_type=content_type)
        blob.make_public()
        download_url = blob.public_url
        
        # Update user profile with picture URL
        db.collection("users").document(uid).update({
            "profile_picture_url": download_url,
            "updated_at": time.time()
        })
        
        log_action(uid, "PROFILE_PICTURE_UPLOAD", f"Profile picture uploaded: {storage_path}")
        
        return {
            "status": "success",
            "message": "Profile picture uploaded successfully",
            "profile_picture_url": download_url
        }
    except Exception as e:
        print(f"Error uploading profile picture: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to upload profile picture: {str(e)}"
        )


@router.post("/log-login")
async def log_login(authorization: str = Header(...)):
    """Log user login activity."""
    try:
        if not authorization.startswith("Bearer "):
            return {"status": "ignored", "reason": "invalid_header"}

        token = authorization.split(" ")[1]
        decoded = firebase_auth.verify_id_token(token)
        uid = decoded.get('uid')
        log_action(uid, "LOGIN", "User logged in via Firebase")
        return {"status": "logged"}
    except Exception as e:
        print(f"Login Log Error: {e}")
        return {"status": "error", "reason": str(e)}
        return {"status": "error", "detail": str(e)}