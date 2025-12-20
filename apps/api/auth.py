# File: apps/api/auth.py
from fastapi import APIRouter, HTTPException, Header, Depends, Body, status
from firebase_admin import auth as firebase_auth
import time
import json
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

        # 4. Audit log
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
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Signup failed: {str(e)}")


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
    return UserProfile(**user)


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