"""Driver service for driver management operations."""
from datetime import datetime, date
from typing import Optional, List, Tuple, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from ..models.driver import Driver, DriverStatus
from ..models.user import User, UserRole
from ..schemas.driver import DriverCreate, DriverUpdate, DriverSearchRequest


class DriverService:
    """Service for driver management operations."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def create_driver(self, user_id: str, data: DriverCreate) -> Driver:
        """Create a new driver profile."""
        # Check if driver already exists
        existing = await self.db.execute(select(Driver).where(Driver.user_id == user_id))
        if existing.scalar_one_or_none():
            raise ValueError("Driver profile already exists for this user")
        
        driver = Driver(
            user_id=user_id,
            carrier_id=data.carrier_id,
            first_name=data.first_name,
            last_name=data.last_name,
            date_of_birth=data.date_of_birth,
            cdl_number=data.cdl_number,
            cdl_state=data.cdl_state,
            cdl_class=data.cdl_class,
            cdl_expiry=data.cdl_expiry,
            status=DriverStatus.UNAVAILABLE,
        )
        
        self.db.add(driver)
        await self.db.commit()
        await self.db.refresh(driver)
        return driver
    
    async def get_driver(self, driver_id: str) -> Optional[Driver]:
        """Get driver by ID."""
        result = await self.db.execute(select(Driver).where(Driver.id == driver_id))
        return result.scalar_one_or_none()
    
    async def get_driver_by_user(self, user_id: str) -> Optional[Driver]:
        """Get driver by user ID."""
        result = await self.db.execute(select(Driver).where(Driver.user_id == user_id))
        return result.scalar_one_or_none()
    
    async def update_driver(self, driver_id: str, data: DriverUpdate) -> Driver:
        """Update driver profile."""
        driver = await self.get_driver(driver_id)
        if not driver:
            raise ValueError("Driver not found")
        
        update_data = data.model_dump(exclude_unset=True)
        
        for field, value in update_data.items():
            if hasattr(driver, field):
                setattr(driver, field, value)
        
        driver.updated_at = datetime.utcnow()
        await self.db.commit()
        await self.db.refresh(driver)
        return driver
    
    async def list_drivers(
        self,
        carrier_id: str = None,
        status: DriverStatus = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Tuple[List[Driver], int]:
        """List drivers with filters."""
        query = select(Driver)
        
        if carrier_id:
            query = query.where(Driver.carrier_id == carrier_id)
        if status:
            query = query.where(Driver.status == status)
        
        # Count
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await self.db.execute(count_query)
        total = total_result.scalar()
        
        # Paginate
        query = query.offset((page - 1) * page_size).limit(page_size)
        query = query.order_by(Driver.created_at.desc())
        
        result = await self.db.execute(query)
        drivers = result.scalars().all()
        
        return list(drivers), total
    
    async def search_drivers(self, search: DriverSearchRequest, page: int = 1, page_size: int = 20) -> Tuple[List[Driver], int]:
        """Search available drivers."""
        query = select(Driver)
        
        if search.carrier_id:
            query = query.where(Driver.carrier_id == search.carrier_id)
        if search.status:
            query = query.where(Driver.status == search.status)
        if search.state:
            query = query.where(Driver.current_state == search.state)
        if search.cdl_class:
            query = query.where(Driver.cdl_class == search.cdl_class)
        if search.hazmat:
            query = query.where(Driver.hazmat_endorsement == True)
        if search.min_hours_available:
            query = query.where(Driver.hours_available >= search.min_hours_available)
        
        # Count
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await self.db.execute(count_query)
        total = total_result.scalar()
        
        # Paginate
        query = query.offset((page - 1) * page_size).limit(page_size)
        
        result = await self.db.execute(query)
        drivers = result.scalars().all()
        
        return list(drivers), total
    
    async def update_location(self, driver_id: str, lat: float, lng: float, city: str = None, state: str = None) -> Driver:
        """Update driver location."""
        driver = await self.get_driver(driver_id)
        if not driver:
            raise ValueError("Driver not found")
        
        driver.current_lat = lat
        driver.current_lng = lng
        driver.current_city = city
        driver.current_state = state
        driver.last_location_update = datetime.utcnow()
        
        await self.db.commit()
        await self.db.refresh(driver)
        return driver
    
    async def check_compliance(self, driver_id: str) -> Dict[str, Any]:
        """Check driver compliance status."""
        driver = await self.get_driver(driver_id)
        if not driver:
            raise ValueError("Driver not found")
        
        today = date.today()
        
        cdl_valid = driver.cdl_expiry and driver.cdl_expiry >= today if driver.cdl_expiry else False
        medical_valid = driver.medical_card_expiry and driver.medical_card_expiry >= today if driver.medical_card_expiry else False
        
        checks = {
            "cdl_verified": driver.cdl_verified,
            "cdl_not_expired": cdl_valid,
            "medical_card_verified": driver.medical_card_verified,
            "medical_card_not_expired": medical_valid,
            "drug_test_passed": driver.drug_test_status == "passed" if driver.drug_test_status else False,
        }
        
        issues = []
        if not checks["cdl_verified"]:
            issues.append("CDL verification required")
        if not checks["cdl_not_expired"]:
            issues.append("CDL has expired or expiry not set")
        if not checks["medical_card_verified"]:
            issues.append("Medical card verification required")
        if not checks["medical_card_not_expired"]:
            issues.append("Medical card has expired")
        if not checks["drug_test_passed"]:
            issues.append("Drug test not passed or not recorded")
        
        score = (sum(checks.values()) / len(checks)) * 100
        
        return {
            "driver_id": driver_id,
            "is_compliant": all(checks.values()),
            "score": score,
            "cdl_valid": cdl_valid,
            "medical_valid": medical_valid,
            "drug_test_status": driver.drug_test_status,
            "clearinghouse_status": driver.clearinghouse_status,
            "missing_documents": [],
            "expiring_documents": [],
        }

