"""User service for profile and user management."""
from datetime import datetime
from typing import Optional, List, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_

from ..models.user import User, UserRole, AuditLog
from ..models.company import Company
from ..schemas.user import UserUpdate, AdminUserCreate, AdminUserUpdate
from ..core.security import get_password_hash


class UserService:
    """Service for user management operations."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def get_user_by_id(self, user_id: str) -> Optional[User]:
        """Get user by ID."""
        result = await self.db.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()
    
    async def get_user_by_email(self, email: str) -> Optional[User]:
        """Get user by email."""
        result = await self.db.execute(select(User).where(User.email == email))
        return result.scalar_one_or_none()
    
    async def update_user(self, user_id: str, data: UserUpdate) -> User:
        """Update user profile."""
        user = await self.get_user_by_id(user_id)
        if not user:
            raise ValueError("User not found")
        
        update_data = data.model_dump(exclude_unset=True)
        
        for field, value in update_data.items():
            if hasattr(user, field):
                setattr(user, field, value)
        
        user.updated_at = datetime.utcnow()
        await self.db.commit()
        await self.db.refresh(user)
        return user
    
    async def list_users(
        self,
        page: int = 1,
        page_size: int = 20,
        role: Optional[UserRole] = None,
        company_id: Optional[str] = None,
        search: Optional[str] = None,
        is_active: Optional[bool] = None,
    ) -> Tuple[List[User], int]:
        """List users with filters and pagination."""
        query = select(User)
        
        if role:
            query = query.where(User.role == role)
        if company_id:
            query = query.where(User.company_id == company_id)
        if is_active is not None:
            query = query.where(User.is_active == is_active)
        if search:
            query = query.where(
                or_(
                    User.name.ilike(f"%{search}%"),
                    User.email.ilike(f"%{search}%"),
                    User.phone.ilike(f"%{search}%"),
                )
            )
        
        # Get total count
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await self.db.execute(count_query)
        total = total_result.scalar()
        
        # Apply pagination
        query = query.offset((page - 1) * page_size).limit(page_size)
        query = query.order_by(User.created_at.desc())
        
        result = await self.db.execute(query)
        users = result.scalars().all()
        
        return list(users), total
    
    async def admin_create_user(self, data: AdminUserCreate, created_by: str) -> User:
        """Admin create a new user."""
        # Check email exists
        existing = await self.get_user_by_email(data.email)
        if existing:
            raise ValueError("Email already registered")
        
        user = User(
            email=data.email,
            phone=data.phone,
            password_hash=get_password_hash(data.password),
            name=data.name,
            role=data.role,
            company_id=data.company_id,
            is_verified=data.is_verified,
        )
        self.db.add(user)
        
        # Log action
        log = AuditLog(
            user_id=created_by,
            action="admin_create_user",
            resource_type="user",
            resource_id=user.id,
            details=f"Created user {user.email} with role {user.role.value}",
        )
        self.db.add(log)
        
        await self.db.commit()
        await self.db.refresh(user)
        return user
    
    async def admin_update_user(self, user_id: str, data: AdminUserUpdate, updated_by: str) -> User:
        """Admin update a user."""
        user = await self.get_user_by_id(user_id)
        if not user:
            raise ValueError("User not found")
        
        update_data = data.model_dump(exclude_unset=True)
        
        for field, value in update_data.items():
            if hasattr(user, field):
                setattr(user, field, value)
        
        user.updated_at = datetime.utcnow()
        
        # Log action
        log = AuditLog(
            user_id=updated_by,
            action="admin_update_user",
            resource_type="user",
            resource_id=user.id,
            details=f"Updated fields: {list(update_data.keys())}",
        )
        self.db.add(log)
        
        await self.db.commit()
        await self.db.refresh(user)
        return user
    
    async def delete_user(self, user_id: str, deleted_by: str) -> bool:
        """Soft delete a user (set is_active=False)."""
        user = await self.get_user_by_id(user_id)
        if not user:
            raise ValueError("User not found")
        
        user.is_active = False
        user.updated_at = datetime.utcnow()
        
        # Log action
        log = AuditLog(
            user_id=deleted_by,
            action="delete_user",
            resource_type="user",
            resource_id=user_id,
        )
        self.db.add(log)
        
        await self.db.commit()
        return True
    
    async def get_audit_logs(
        self, 
        user_id: Optional[str] = None, 
        action: Optional[str] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> Tuple[List[AuditLog], int]:
        """Get audit logs with filters."""
        query = select(AuditLog)
        
        if user_id:
            query = query.where(AuditLog.user_id == user_id)
        if action:
            query = query.where(AuditLog.action == action)
        
        # Count
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await self.db.execute(count_query)
        total = total_result.scalar()
        
        # Paginate
        query = query.offset((page - 1) * page_size).limit(page_size)
        query = query.order_by(AuditLog.created_at.desc())
        
        result = await self.db.execute(query)
        logs = result.scalars().all()

        return list(logs), total

    async def update_preferences(self, user_id: str, preferences) -> User:
        """Update user notification preferences."""
        user = await self.get_user_by_id(user_id)
        if not user:
            raise ValueError("User not found")

        import json
        prefs = preferences.model_dump(exclude_unset=True)
        user.notification_preferences = json.dumps(prefs)
        user.updated_at = datetime.utcnow()

        await self.db.commit()
        await self.db.refresh(user)
        return user

    async def deactivate_user(self, user_id: str, admin_id: str = None) -> bool:
        """Deactivate a user account."""
        user = await self.get_user_by_id(user_id)
        if not user:
            raise ValueError("User not found")

        user.is_active = False
        user.updated_at = datetime.utcnow()

        if admin_id:
            log = AuditLog(
                user_id=admin_id,
                action="deactivate_user",
                resource_type="user",
                resource_id=user_id,
            )
            self.db.add(log)

        await self.db.commit()
        return True

    async def reactivate_user(self, user_id: str, admin_id: str = None) -> bool:
        """Reactivate a user account."""
        user = await self.get_user_by_id(user_id)
        if not user:
            raise ValueError("User not found")

        user.is_active = True
        user.updated_at = datetime.utcnow()

        if admin_id:
            log = AuditLog(
                user_id=admin_id,
                action="reactivate_user",
                resource_type="user",
                resource_id=user_id,
            )
            self.db.add(log)

        await self.db.commit()
        return True

    async def get_user_profile(self, user_id: str) -> Optional[dict]:
        """Get user profile with additional details."""
        user = await self.get_user_by_id(user_id)
        if not user:
            return None

        return {
            "id": user.id,
            "email": user.email,
            "phone": user.phone,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "name": user.name,
            "role": user.role.value,
            "company_id": user.company_id,
            "is_active": user.is_active,
            "is_verified": user.is_verified,
            "email_verified": user.email_verified,
            "phone_verified": user.phone_verified,
            "mfa_enabled": user.mfa_enabled,
            "onboarding_status": user.onboarding_status,
            "onboarding_step": user.onboarding_step,
            "timezone": user.timezone,
            "language": user.language,
            "created_at": user.created_at,
            "updated_at": user.updated_at,
        }

