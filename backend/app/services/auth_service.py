"""Authentication service."""
from datetime import datetime, timedelta
from typing import Optional, Tuple, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from sqlalchemy.orm import selectinload
import hashlib

from ..models.user import User, UserRole, OTPVerification, RefreshToken, AuditLog
from ..models.company import Company, CompanyType
from ..core.security import (
    get_password_hash, verify_password, create_access_token,
    create_refresh_token, decode_token, generate_otp
)
from ..core.config import settings


class AuthService:
    """Authentication service for user management."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def signup(
        self,
        email: str,
        password: str,
        phone: str = None,
        first_name: str = None,
        last_name: str = None,
        role: UserRole = UserRole.CARRIER,
        company_name: str = None,
        usdot: str = None,
        mc_number: str = None,
        ip_address: str = None,
        user_agent: str = None,
    ) -> User:
        """Register a new user."""
        # Check if email exists
        existing = await self.db.execute(select(User).where(User.email == email))
        if existing.scalar_one_or_none():
            raise ValueError("Email already registered")

        # Check phone if provided
        if phone:
            existing_phone = await self.db.execute(select(User).where(User.phone == phone))
            if existing_phone.scalar_one_or_none():
                raise ValueError("Phone number already registered")

        # Create company if carrier/shipper with company name
        company_id = None
        if company_name and role in [UserRole.CARRIER, UserRole.SHIPPER, UserRole.BROKER]:
            company_type = CompanyType.CARRIER if role == UserRole.CARRIER else CompanyType.SHIPPER
            if role == UserRole.BROKER:
                company_type = CompanyType.BROKER

            company = Company(
                name=company_name,
                company_type=company_type,
                usdot=usdot,
                mc_number=mc_number,
            )
            self.db.add(company)
            await self.db.flush()
            company_id = company.id

        # Create user
        user = User(
            email=email,
            phone=phone,
            password_hash=get_password_hash(password),
            first_name=first_name,
            last_name=last_name,
            role=role,
            company_id=company_id,
        )
        self.db.add(user)
        await self.db.flush()

        # Log action
        await self._log_action(user.id, "signup", "user", user.id, ip_address=ip_address)

        await self.db.commit()
        return user

    async def login(
        self,
        email: str,
        password: str,
        ip_address: str = None,
        user_agent: str = None,
    ) -> Dict[str, Any]:
        """Authenticate user and return tokens."""
        result = await self.db.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()
        
        if not user:
            raise ValueError("Invalid email or password")

        # Check if locked
        if user.is_locked and user.locked_until and user.locked_until > datetime.utcnow():
            raise ValueError("Account is locked. Try again later.")

        # Verify password
        if not verify_password(password, user.password_hash):
            user.failed_login_attempts += 1
            if user.failed_login_attempts >= 5:
                user.is_locked = True
                user.locked_until = datetime.utcnow() + timedelta(minutes=30)
            await self.db.commit()
            raise ValueError("Invalid email or password")

        # Reset failed attempts
        user.failed_login_attempts = 0
        user.is_locked = False
        user.locked_until = None
        user.last_login_at = datetime.utcnow()

        # Generate tokens
        access_token = create_access_token({"sub": user.id, "role": user.role.value})
        refresh_token = create_refresh_token({"sub": user.id})

        # Store refresh token
        await self._store_refresh_token(user.id, refresh_token)

        # Log action
        await self._log_action(user.id, "login", "user", user.id, ip_address=ip_address, user_agent=user_agent)

        await self.db.commit()

        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            "user": user,
        }
    
    async def refresh_tokens(self, refresh_token: str) -> Tuple[str, str]:
        """Refresh access and refresh tokens."""
        payload = decode_token(refresh_token)
        if payload.get("type") != "refresh":
            raise ValueError("Invalid token type")
        
        user_id = payload.get("sub")
        token_hash = hashlib.sha256(refresh_token.encode()).hexdigest()
        
        # Find and validate stored token
        result = await self.db.execute(
            select(RefreshToken).where(
                RefreshToken.user_id == user_id,
                RefreshToken.token_hash == token_hash,
                RefreshToken.revoked == False
            )
        )
        stored_token = result.scalar_one_or_none()
        if not stored_token or stored_token.expires_at < datetime.utcnow():
            raise ValueError("Invalid or expired refresh token")
        
        # Get user
        result = await self.db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if not user or not user.is_active:
            raise ValueError("User not found or inactive")
        
        # Revoke old token
        stored_token.revoked = True
        stored_token.revoked_at = datetime.utcnow()
        
        # Generate new tokens
        new_access = create_access_token({"sub": user.id, "role": user.role.value})
        new_refresh = create_refresh_token({"sub": user.id})
        
        # Store new refresh token
        new_token_id = await self._store_refresh_token(user.id, new_refresh)
        stored_token.replaced_by = new_token_id
        
        await self.db.commit()
        return new_access, new_refresh
    
    async def _store_refresh_token(self, user_id: str, token: str) -> str:
        """Store refresh token hash."""
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        expires_at = datetime.utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
        
        refresh_token = RefreshToken(
            user_id=user_id,
            token_hash=token_hash,
            expires_at=expires_at,
        )
        self.db.add(refresh_token)
        await self.db.flush()
        return refresh_token.id
    
    async def _log_action(self, user_id: str, action: str, resource_type: str = None,
                          resource_id: str = None, ip_address: str = None, user_agent: str = None):
        """Log user action for audit."""
        log = AuditLog(
            user_id=user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        self.db.add(log)

    async def logout(self, user_id: str):
        """Logout user and revoke all refresh tokens."""
        await self.db.execute(
            update(RefreshToken)
            .where(RefreshToken.user_id == user_id, RefreshToken.revoked == False)
            .values(revoked=True, revoked_at=datetime.utcnow())
        )
        await self.db.commit()

    async def refresh_token(
        self,
        refresh_token: str,
        ip_address: str = None,
        user_agent: str = None,
    ) -> Dict[str, Any]:
        """Refresh access token using refresh token."""
        new_access, new_refresh = await self.refresh_tokens(refresh_token)

        # Get user
        payload = decode_token(new_access)
        user_id = payload.get("sub")
        result = await self.db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()

        return {
            "access_token": new_access,
            "refresh_token": new_refresh,
            "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            "user": user,
        }

    async def request_password_reset(self, email: str):
        """Request password reset."""
        result = await self.db.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()

        if user:
            # Generate reset token
            reset_token = create_access_token(
                {"sub": user.id, "purpose": "password_reset"},
                expires_delta=timedelta(hours=1)
            )
            # In production, send email with reset link
            # For now, just log it
            print(f"Password reset token for {email}: {reset_token}")

    async def reset_password(self, token: str, new_password: str):
        """Reset password with token."""
        payload = decode_token(token)
        if payload.get("purpose") != "password_reset":
            raise ValueError("Invalid reset token")

        user_id = payload.get("sub")
        result = await self.db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()

        if not user:
            raise ValueError("User not found")

        user.password_hash = get_password_hash(new_password)
        await self.db.commit()

    async def change_password(self, user_id: str, current_password: str, new_password: str):
        """Change user password."""
        result = await self.db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()

        if not user:
            raise ValueError("User not found")

        if not verify_password(current_password, user.password_hash):
            raise ValueError("Current password is incorrect")

        user.password_hash = get_password_hash(new_password)
        await self.db.commit()

    async def enable_mfa(self, user_id: str, method: str = "totp") -> Dict[str, Any]:
        """Enable MFA for user."""
        result = await self.db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()

        if not user:
            raise ValueError("User not found")

        user.mfa_enabled = True
        await self.db.commit()

        return {"enabled": True, "method": method}

    async def disable_mfa(self, user_id: str):
        """Disable MFA for user."""
        result = await self.db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()

        if not user:
            raise ValueError("User not found")

        user.mfa_enabled = False
        await self.db.commit()

    async def log_login_event(
        self, token: str, ip_address: str = None, user_agent: str = None
    ):
        """Log a login event from Firebase token."""
        try:
            # Decode the Firebase token to get user info
            # In production, this would verify the Firebase token
            # For now, we just log the event
            from ..models.user import AuditLog

            log = AuditLog(
                user_id=None,  # Would be extracted from token
                action="login",
                resource_type="session",
                ip_address=ip_address,
                user_agent=user_agent,
                details="Login via Firebase",
            )
            self.db.add(log)
            await self.db.commit()
        except Exception as e:
            # Don't fail if logging fails
            pass

