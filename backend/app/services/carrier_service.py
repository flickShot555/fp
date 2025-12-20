"""Carrier service for carrier management operations."""
from datetime import datetime
from typing import Optional, List, Tuple, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_
import json

from ..models.carrier import Carrier, CarrierProfile, Lane
from ..models.company import Company
from ..schemas.carrier import CarrierCreate, CarrierUpdate, LaneCreate, CarrierSearchRequest


class CarrierService:
    """Service for carrier management operations."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def create_carrier(self, data: CarrierCreate) -> Carrier:
        """Create a new carrier profile."""
        carrier = Carrier(
            company_id=data.company_id,
            equipment_types=json.dumps(data.equipment_types) if data.equipment_types else None,
            power_units=data.power_units or 0,
            trailers=data.trailers or 0,
            service_states=json.dumps(data.service_states) if data.service_states else None,
        )
        
        self.db.add(carrier)
        await self.db.commit()
        await self.db.refresh(carrier)
        return carrier
    
    async def get_carrier(self, carrier_id: str) -> Optional[Carrier]:
        """Get carrier by ID."""
        result = await self.db.execute(select(Carrier).where(Carrier.id == carrier_id))
        return result.scalar_one_or_none()
    
    async def get_carrier_by_company(self, company_id: str) -> Optional[Carrier]:
        """Get carrier by company ID."""
        result = await self.db.execute(select(Carrier).where(Carrier.company_id == company_id))
        return result.scalar_one_or_none()
    
    async def update_carrier(self, carrier_id: str, data: CarrierUpdate) -> Carrier:
        """Update carrier profile."""
        carrier = await self.get_carrier(carrier_id)
        if not carrier:
            raise ValueError("Carrier not found")
        
        update_data = data.model_dump(exclude_unset=True)
        
        for field, value in update_data.items():
            if field in ["equipment_types", "service_states"] and value:
                value = json.dumps(value)
            if hasattr(carrier, field):
                setattr(carrier, field, value)
        
        carrier.updated_at = datetime.utcnow()
        await self.db.commit()
        await self.db.refresh(carrier)
        return carrier
    
    async def list_carriers(
        self,
        is_active: bool = True,
        is_verified: bool = None,
        min_compliance_score: float = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Tuple[List[Carrier], int]:
        """List carriers with filters."""
        query = select(Carrier).where(Carrier.is_active == is_active)
        
        if is_verified is not None:
            query = query.where(Carrier.fmcsa_verified == is_verified)
        if min_compliance_score:
            query = query.where(Carrier.compliance_score >= min_compliance_score)
        
        # Count
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await self.db.execute(count_query)
        total = total_result.scalar()
        
        # Paginate
        query = query.offset((page - 1) * page_size).limit(page_size)
        query = query.order_by(Carrier.compliance_score.desc())
        
        result = await self.db.execute(query)
        carriers = result.scalars().all()
        
        return list(carriers), total
    
    async def search_carriers(self, search: CarrierSearchRequest, page: int = 1, page_size: int = 20) -> Tuple[List[Carrier], int]:
        """Search carriers for load matching."""
        query = select(Carrier).where(Carrier.is_active == True, Carrier.available_for_loads == True)
        
        if search.is_verified:
            query = query.where(Carrier.fmcsa_verified == True)
        if search.min_compliance_score:
            query = query.where(Carrier.compliance_score >= search.min_compliance_score)
        if search.equipment_type:
            query = query.where(Carrier.equipment_types.ilike(f'%"{search.equipment_type}"%'))
        
        # Count
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await self.db.execute(count_query)
        total = total_result.scalar()
        
        # Paginate
        query = query.offset((page - 1) * page_size).limit(page_size)
        
        result = await self.db.execute(query)
        carriers = result.scalars().all()
        
        return list(carriers), total
    
    async def add_lane(self, carrier_id: str, data: LaneCreate) -> Lane:
        """Add a preferred lane for carrier."""
        carrier = await self.get_carrier(carrier_id)
        if not carrier:
            raise ValueError("Carrier not found")
        
        lane = Lane(
            carrier_id=carrier_id,
            origin_city=data.origin_city,
            origin_state=data.origin_state,
            destination_city=data.destination_city,
            destination_state=data.destination_state,
            equipment_type=data.equipment_type,
            preferred_rate=data.preferred_rate,
        )
        
        self.db.add(lane)
        await self.db.commit()
        await self.db.refresh(lane)
        return lane
    
    async def get_carrier_lanes(self, carrier_id: str) -> List[Lane]:
        """Get all lanes for a carrier."""
        result = await self.db.execute(
            select(Lane).where(Lane.carrier_id == carrier_id, Lane.is_active == True)
        )
        return list(result.scalars().all())
    
    async def check_compliance(self, carrier_id: str) -> Dict[str, Any]:
        """Check carrier compliance status."""
        carrier = await self.get_carrier(carrier_id)
        if not carrier:
            raise ValueError("Carrier not found")
        
        checks = {
            "fmcsa_verified": carrier.fmcsa_verified,
            "insurance_valid": carrier.insurance_status == "active" if carrier.insurance_status else False,
            "insurance_not_expired": carrier.insurance_expiry > datetime.utcnow() if carrier.insurance_expiry else False,
        }
        
        issues = []
        if not checks["fmcsa_verified"]:
            issues.append("FMCSA verification required")
        if not checks["insurance_valid"]:
            issues.append("Insurance status not active")
        if not checks["insurance_not_expired"]:
            issues.append("Insurance has expired or expiry not set")
        
        passed = all(checks.values())
        score = (sum(checks.values()) / len(checks)) * 100
        
        return {
            "carrier_id": carrier_id,
            "is_compliant": passed,
            "score": score,
            "checks": checks,
            "issues": issues,
            "warnings": [],
            "last_checked": datetime.utcnow(),
        }

