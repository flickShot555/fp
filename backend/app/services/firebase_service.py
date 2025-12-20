"""Firebase service for user authentication."""
import httpx
from typing import Optional, Dict, Any


# Firebase Web API Key (from frontend config)
FIREBASE_API_KEY = "AIzaSyClzYECMNer89EjBs_h12hb5tDIghUslMM"
FIREBASE_PROJECT_ID = "freightpowerai-e90fe"
FIREBASE_AUTH_URL = "https://identitytoolkit.googleapis.com/v1"
FIRESTORE_URL = f"https://firestore.googleapis.com/v1/projects/{FIREBASE_PROJECT_ID}/databases/(default)/documents"


class FirebaseService:
    """Service for Firebase Authentication operations."""

    def __init__(self):
        self.api_key = FIREBASE_API_KEY
        self.auth_url = FIREBASE_AUTH_URL
        self.firestore_url = FIRESTORE_URL

    async def create_user(
        self,
        email: str,
        password: str,
        display_name: Optional[str] = None,
        phone: Optional[str] = None,
        role: str = "carrier",
    ) -> Dict[str, Any]:
        """Create a new user in Firebase Authentication.

        Uses the Firebase Auth REST API to create users.
        https://firebase.google.com/docs/reference/rest/auth
        """
        url = f"{self.auth_url}/accounts:signUp?key={self.api_key}"

        payload = {
            "email": email,
            "password": password,
            "returnSecureToken": True,
        }

        if display_name:
            payload["displayName"] = display_name

        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=payload)
            data = response.json()

            if response.status_code != 200:
                error_message = data.get("error", {}).get("message", "Unknown error")
                raise ValueError(f"Firebase error: {error_message}")

            uid = data.get("localId")
            id_token = data.get("idToken")

            # Create user document in Firestore
            await self.create_user_document(
                uid=uid,
                id_token=id_token,
                email=email,
                display_name=display_name,
                phone=phone,
                role=role,
            )

            return {
                "uid": uid,
                "email": data.get("email"),
                "id_token": id_token,
                "refresh_token": data.get("refreshToken"),
                "expires_in": data.get("expiresIn"),
            }

    async def create_user_document(
        self,
        uid: str,
        id_token: str,
        email: str,
        display_name: Optional[str] = None,
        phone: Optional[str] = None,
        role: str = "carrier",
    ) -> bool:
        """Create user document in Firestore.

        This is required for the frontend login flow which checks Firestore for user data.
        """
        # Firestore REST API to create/update document
        url = f"{self.firestore_url}/users/{uid}?key={self.api_key}"

        # Firestore document format
        document = {
            "fields": {
                "email": {"stringValue": email},
                "role": {"stringValue": role},
                "mfa_enabled": {"booleanValue": False},
                "created_at": {"timestampValue": self._get_timestamp()},
            }
        }

        if display_name:
            document["fields"]["name"] = {"stringValue": display_name}

        if phone:
            document["fields"]["phone"] = {"stringValue": phone}

        async with httpx.AsyncClient() as client:
            response = await client.patch(
                url,
                json=document,
                headers={"Authorization": f"Bearer {id_token}"}
            )
            return response.status_code in [200, 201]

    def _get_timestamp(self) -> str:
        """Get current timestamp in ISO format for Firestore."""
        from datetime import datetime, timezone
        return datetime.now(timezone.utc).isoformat()
    
    async def sign_in_user(
        self,
        email: str,
        password: str,
    ) -> Dict[str, Any]:
        """Sign in an existing user.
        
        Returns tokens if successful.
        """
        url = f"{self.auth_url}/accounts:signInWithPassword?key={self.api_key}"
        
        payload = {
            "email": email,
            "password": password,
            "returnSecureToken": True,
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=payload)
            data = response.json()
            
            if response.status_code != 200:
                error_message = data.get("error", {}).get("message", "Unknown error")
                raise ValueError(f"Firebase error: {error_message}")
            
            return {
                "uid": data.get("localId"),
                "email": data.get("email"),
                "id_token": data.get("idToken"),
                "refresh_token": data.get("refreshToken"),
                "expires_in": data.get("expiresIn"),
            }
    
    async def send_email_verification(self, id_token: str) -> bool:
        """Send email verification to user.
        
        Args:
            id_token: The Firebase ID token of the user
        """
        url = f"{self.auth_url}/accounts:sendOobCode?key={self.api_key}"
        
        payload = {
            "requestType": "VERIFY_EMAIL",
            "idToken": id_token,
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=payload)
            return response.status_code == 200
    
    async def send_password_reset(self, email: str) -> bool:
        """Send password reset email.
        
        Args:
            email: The email address of the user
        """
        url = f"{self.auth_url}/accounts:sendOobCode?key={self.api_key}"
        
        payload = {
            "requestType": "PASSWORD_RESET",
            "email": email,
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=payload)
            return response.status_code == 200


# Singleton instance
firebase_service = FirebaseService()


async def verify_firebase_token(id_token: str) -> Dict[str, Any]:
    """Verify a Firebase ID token and return the decoded user info.

    This validates the token with Firebase and returns user information.

    Args:
        id_token: The Firebase ID token to verify

    Returns:
        Dict with user info including uid, email, email_verified

    Raises:
        ValueError: If token is invalid or expired
    """
    # Use Firebase Auth REST API to get user info from token
    url = f"{FIREBASE_AUTH_URL}/accounts:lookup?key={FIREBASE_API_KEY}"

    payload = {
        "idToken": id_token
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(url, json=payload)
        data = response.json()

        if response.status_code != 200:
            error_message = data.get("error", {}).get("message", "Invalid token")
            raise ValueError(f"Firebase token verification failed: {error_message}")

        users = data.get("users", [])
        if not users:
            raise ValueError("No user found for token")

        user = users[0]

        return {
            "uid": user.get("localId"),
            "email": user.get("email"),
            "email_verified": user.get("emailVerified", False),
            "display_name": user.get("displayName"),
            "phone_number": user.get("phoneNumber"),
            "photo_url": user.get("photoUrl"),
            "created_at": user.get("createdAt"),
            "last_login_at": user.get("lastLoginAt"),
        }

