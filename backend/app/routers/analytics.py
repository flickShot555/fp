"""Analytics and Reports API routes."""
from typing import Optional
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from ..core.database import get_db
from ..core.security import get_current_user, get_current_active_user, require_roles
from ..models.user import User, UserRole
from ..models.load import Load, LoadStatus
from ..models.document import Document
from ..models.carrier import Carrier
from ..services.compliance_service import ComplianceService


router = APIRouter(prefix="/analytics", tags=["Analytics"])


@router.get("/dashboard")
async def get_dashboard_stats(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Get dashboard statistics based on user role."""
    stats = {}
    
    if current_user.role == UserRole.SHIPPER:
        # Shipper stats
        loads_result = await db.execute(
            select(func.count()).where(Load.shipper_id == current_user.id)
        )
        stats["total_loads"] = loads_result.scalar()
        
        active_result = await db.execute(
            select(func.count()).where(
                Load.shipper_id == current_user.id,
                Load.status.in_([LoadStatus.POSTED, LoadStatus.TENDERED, LoadStatus.DISPATCHED])
            )
        )
        stats["active_loads"] = active_result.scalar()
        
        delivered_result = await db.execute(
            select(func.count()).where(
                Load.shipper_id == current_user.id,
                Load.status == LoadStatus.DELIVERED
            )
        )
        stats["delivered_loads"] = delivered_result.scalar()
    
    elif current_user.role == UserRole.CARRIER:
        # Carrier stats
        carrier_result = await db.execute(
            select(Carrier).where(Carrier.company_id == current_user.company_id)
        )
        carrier = carrier_result.scalar_one_or_none()
        
        if carrier:
            stats["compliance_score"] = carrier.compliance_score or 0
            stats["fmcsa_verified"] = carrier.fmcsa_verified
        
        # Document stats
        docs_result = await db.execute(
            select(func.count()).where(Document.owner_id == current_user.id)
        )
        stats["total_documents"] = docs_result.scalar()
    
    elif current_user.role in [UserRole.ADMIN, UserRole.SUPER_ADMIN]:
        # Admin stats
        users_result = await db.execute(select(func.count()).select_from(User))
        stats["total_users"] = users_result.scalar()
        
        loads_result = await db.execute(select(func.count()).select_from(Load))
        stats["total_loads"] = loads_result.scalar()
        
        carriers_result = await db.execute(select(func.count()).select_from(Carrier))
        stats["total_carriers"] = carriers_result.scalar()
        
        docs_result = await db.execute(select(func.count()).select_from(Document))
        stats["total_documents"] = docs_result.scalar()
    
    return stats


@router.get("/compliance/expiring-documents")
async def get_expiring_documents(
    days: int = Query(30, ge=1, le=90),
    current_user: User = Depends(require_roles([UserRole.ADMIN, UserRole.SUPER_ADMIN, UserRole.CARRIER])),
    db: AsyncSession = Depends(get_db)
):
    """Get documents expiring within specified days."""
    compliance_service = ComplianceService(db)
    
    report = await compliance_service.get_expiring_documents_report(days=days)
    
    # Filter by user if not admin
    if current_user.role not in [UserRole.ADMIN, UserRole.SUPER_ADMIN]:
        report = [r for r in report if r["owner_id"] == current_user.id]
    
    return {"documents": report, "days": days}


@router.get("/loads/summary")
async def get_loads_summary(
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Get loads summary statistics."""
    if not start_date:
        start_date = datetime.utcnow() - timedelta(days=30)
    if not end_date:
        end_date = datetime.utcnow()
    
    query = select(Load).where(Load.created_at >= start_date, Load.created_at <= end_date)
    
    if current_user.role == UserRole.SHIPPER:
        query = query.where(Load.shipper_id == current_user.id)
    elif current_user.role not in [UserRole.ADMIN, UserRole.SUPER_ADMIN]:
        query = query.where(Load.carrier_id == current_user.id)
    
    result = await db.execute(query)
    loads = result.scalars().all()
    
    # Calculate summary
    status_counts = {}
    total_revenue = 0
    
    for load in loads:
        status_counts[load.status.value] = status_counts.get(load.status.value, 0) + 1
        if load.agreed_rate:
            total_revenue += float(load.agreed_rate)
    
    return {
        "total_loads": len(loads),
        "status_breakdown": status_counts,
        "total_revenue": total_revenue,
        "period": {"start": start_date, "end": end_date},
    }


@router.get("/compliance/summary")
async def get_compliance_summary(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Get compliance summary for current user."""
    compliance_service = ComplianceService(db)
    
    result = await compliance_service.check_user_compliance(current_user.id)
    actions = await compliance_service.get_next_best_actions(current_user.id)
    
    return {
        "compliance": result,
        "next_actions": actions,
    }


@router.get("/admin/overview")
async def get_admin_overview(
    current_user: User = Depends(require_roles([UserRole.ADMIN, UserRole.SUPER_ADMIN])),
    db: AsyncSession = Depends(get_db)
):
    """Get admin overview statistics."""
    # Users by role
    role_counts = {}
    for role in UserRole:
        result = await db.execute(
            select(func.count()).where(User.role == role)
        )
        role_counts[role.value] = result.scalar()
    
    # Recent signups (last 7 days)
    week_ago = datetime.utcnow() - timedelta(days=7)
    recent_result = await db.execute(
        select(func.count()).where(User.created_at >= week_ago)
    )
    recent_signups = recent_result.scalar()
    
    # Active loads
    active_result = await db.execute(
        select(func.count()).where(
            Load.status.in_([LoadStatus.POSTED, LoadStatus.TENDERED, LoadStatus.DISPATCHED])
        )
    )
    active_loads = active_result.scalar()
    
    return {
        "users_by_role": role_counts,
        "recent_signups": recent_signups,
        "active_loads": active_loads,
    }

