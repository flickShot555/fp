"""Load/Shipment service for marketplace operations."""
from datetime import datetime
from typing import Optional, List, Tuple, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_
import uuid

from ..models.load import Load, LoadStatus, LoadApplication, LoadAssignment
from ..models.carrier import Carrier
from ..models.driver import Driver
from ..models.document import Document, DocumentType
from ..schemas.load import LoadCreate, LoadUpdate, LoadSearchRequest


class LoadService:
    """Service for load management operations."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def create_load(self, data: LoadCreate, shipper_id: str, company_id: str = None) -> Load:
        """Create a new load."""
        load_number = f"LD-{datetime.utcnow().strftime('%Y%m%d')}-{str(uuid.uuid4())[:8].upper()}"
        
        load = Load(
            load_number=load_number,
            reference_number=data.reference_number,
            origin_address=data.origin_address,
            origin_city=data.origin_city,
            origin_state=data.origin_state,
            origin_zip=data.origin_zip,
            destination_address=data.destination_address,
            destination_city=data.destination_city,
            destination_state=data.destination_state,
            destination_zip=data.destination_zip,
            pickup_date=data.pickup_date,
            pickup_time_start=data.pickup_time_start,
            pickup_time_end=data.pickup_time_end,
            delivery_date=data.delivery_date,
            delivery_time_start=data.delivery_time_start,
            delivery_time_end=data.delivery_time_end,
            equipment_type=data.equipment_type,
            weight=data.weight,
            pieces=data.pieces,
            commodity=data.commodity,
            special_instructions=data.special_instructions,
            temperature_min=data.temperature_min,
            temperature_max=data.temperature_max,
            rate=data.rate,
            shipper_id=shipper_id,
            company_id=company_id,
            status=LoadStatus.DRAFT,
        )
        
        # Calculate miles (simplified - would use actual routing API)
        load.miles = await self._calculate_distance(
            data.origin_city, data.origin_state,
            data.destination_city, data.destination_state
        )
        
        if load.rate and load.miles:
            load.rate_per_mile = load.rate / load.miles
        
        self.db.add(load)
        await self.db.commit()
        await self.db.refresh(load)
        return load
    
    async def _calculate_distance(self, origin_city: str, origin_state: str, dest_city: str, dest_state: str) -> float:
        """Calculate approximate distance (placeholder - use actual routing API)."""
        # Simplified distance calculation
        return 500.0  # Placeholder
    
    async def update_load(self, load_id: str, data: LoadUpdate, user_id: str) -> Load:
        """Update a load."""
        load = await self.get_load(load_id)
        if not load:
            raise ValueError("Load not found")
        
        update_data = data.model_dump(exclude_unset=True)
        
        for field, value in update_data.items():
            if hasattr(load, field):
                setattr(load, field, value)
        
        load.updated_at = datetime.utcnow()
        await self.db.commit()
        await self.db.refresh(load)
        return load
    
    async def get_load(self, load_id: str) -> Optional[Load]:
        """Get load by ID."""
        result = await self.db.execute(select(Load).where(Load.id == load_id))
        return result.scalar_one_or_none()
    
    async def list_loads(
        self,
        company_id: str = None,
        shipper_id: str = None,
        carrier_id: str = None,
        status: LoadStatus = None,
        is_public: bool = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Tuple[List[Load], int]:
        """List loads with filters."""
        query = select(Load)
        
        if company_id:
            query = query.where(Load.company_id == company_id)
        if shipper_id:
            query = query.where(Load.shipper_id == shipper_id)
        if carrier_id:
            query = query.where(Load.assigned_carrier_id == carrier_id)
        if status:
            query = query.where(Load.status == status)
        if is_public is not None:
            query = query.where(Load.is_public == is_public)
        
        # Count
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await self.db.execute(count_query)
        total = total_result.scalar()
        
        # Paginate
        query = query.offset((page - 1) * page_size).limit(page_size)
        query = query.order_by(Load.created_at.desc())
        
        result = await self.db.execute(query)
        loads = result.scalars().all()
        
        return list(loads), total
    
    async def search_loads(self, search: LoadSearchRequest, page: int = 1, page_size: int = 20) -> Tuple[List[Load], int]:
        """Search loads in marketplace."""
        query = select(Load).where(Load.is_public == True, Load.status == LoadStatus.POSTED)
        
        if search.origin_state:
            query = query.where(Load.origin_state == search.origin_state)
        if search.origin_city:
            query = query.where(Load.origin_city.ilike(f"%{search.origin_city}%"))
        if search.destination_state:
            query = query.where(Load.destination_state == search.destination_state)
        if search.destination_city:
            query = query.where(Load.destination_city.ilike(f"%{search.destination_city}%"))
        if search.equipment_type:
            query = query.where(Load.equipment_type == search.equipment_type)
        if search.pickup_date_from:
            query = query.where(Load.pickup_date >= search.pickup_date_from)
        if search.pickup_date_to:
            query = query.where(Load.pickup_date <= search.pickup_date_to)
        if search.min_rate:
            query = query.where(Load.rate >= search.min_rate)
        if search.max_weight:
            query = query.where(Load.weight <= search.max_weight)
        
        # Count
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await self.db.execute(count_query)
        total = total_result.scalar()
        
        # Paginate
        query = query.offset((page - 1) * page_size).limit(page_size)
        query = query.order_by(Load.pickup_date)
        
        result = await self.db.execute(query)
        loads = result.scalars().all()
        
        return list(loads), total
    
    async def post_load(self, load_id: str, is_broadcast: bool = False) -> Load:
        """Post load to marketplace."""
        load = await self.get_load(load_id)
        if not load:
            raise ValueError("Load not found")
        
        load.status = LoadStatus.POSTED
        load.is_public = True
        load.is_broadcast = is_broadcast
        load.posted_at = datetime.utcnow()
        
        await self.db.commit()
        await self.db.refresh(load)
        return load
    
    async def apply_to_load(self, load_id: str, carrier_id: str, bid_amount: float = None, message: str = None) -> LoadApplication:
        """Carrier apply to a load."""
        load = await self.get_load(load_id)
        if not load:
            raise ValueError("Load not found")
        if load.status != LoadStatus.POSTED:
            raise ValueError("Load is not available for applications")
        
        # Check existing application
        existing = await self.db.execute(
            select(LoadApplication).where(
                LoadApplication.load_id == load_id,
                LoadApplication.carrier_id == carrier_id,
            )
        )
        if existing.scalar_one_or_none():
            raise ValueError("Already applied to this load")
        
        application = LoadApplication(
            load_id=load_id,
            carrier_id=carrier_id,
            bid_amount=bid_amount,
            message=message,
            status="pending",
        )
        
        self.db.add(application)
        await self.db.commit()
        await self.db.refresh(application)
        return application
    
    async def _check_carrier_coi_valid(self, carrier_id: str) -> Dict[str, Any]:
        """Check if carrier has valid (non-expired) Certificate of Insurance."""
        # Get carrier
        result = await self.db.execute(select(Carrier).where(Carrier.id == carrier_id))
        carrier = result.scalar_one_or_none()

        if not carrier:
            return {"valid": False, "reason": "Carrier not found"}

        # Check carrier's insurance expiry field first
        if carrier.insurance_expiry:
            if carrier.insurance_expiry < datetime.utcnow():
                return {
                    "valid": False,
                    "reason": f"Insurance expired on {carrier.insurance_expiry.strftime('%Y-%m-%d')}"
                }

        # Also check for COI document
        doc_result = await self.db.execute(
            select(Document).where(
                Document.company_id == carrier.company_id,
                Document.document_type == DocumentType.COI,
                Document.status == "active"
            ).order_by(Document.created_at.desc())
        )
        coi_doc = doc_result.scalar_one_or_none()

        if coi_doc:
            if coi_doc.expiry_date and coi_doc.expiry_date < datetime.utcnow():
                return {
                    "valid": False,
                    "reason": f"COI document expired on {coi_doc.expiry_date.strftime('%Y-%m-%d')}"
                }
            if coi_doc.validation_status == "invalid":
                return {
                    "valid": False,
                    "reason": "COI document failed validation"
                }

        return {"valid": True, "reason": None}

    async def award_load(self, load_id: str, carrier_id: str, agreed_rate: float, user_id: str) -> LoadAssignment:
        """Award load to carrier. Blocks if carrier has expired COI."""
        load = await self.get_load(load_id)
        if not load:
            raise ValueError("Load not found")

        # Check carrier COI compliance
        coi_check = await self._check_carrier_coi_valid(carrier_id)
        if not coi_check["valid"]:
            raise ValueError(f"Cannot award load: {coi_check['reason']}. Carrier must upload valid insurance certificate.")

        assignment = LoadAssignment(
            load_id=load_id,
            carrier_id=carrier_id,
            agreed_rate=agreed_rate,
            assigned_by=user_id,
            status="assigned",
        )

        load.status = LoadStatus.ACCEPTED
        load.assigned_carrier_id = carrier_id
        load.awarded_at = datetime.utcnow()
        load.is_public = False

        self.db.add(assignment)
        await self.db.commit()
        await self.db.refresh(assignment)
        return assignment

    async def get_shipper_loads(
        self, shipper_id: str, page: int = 1, page_size: int = 20
    ) -> Tuple[List[Load], int]:
        """Get loads created by a shipper."""
        return await self.list_loads(shipper_id=shipper_id, page=page, page_size=page_size)

    async def get_carrier_loads(
        self, carrier_id: str, page: int = 1, page_size: int = 20
    ) -> Tuple[List[Load], int]:
        """Get loads assigned to a carrier."""
        return await self.list_loads(carrier_id=carrier_id, page=page, page_size=page_size)

    async def apply_for_load(
        self, load_id: str, carrier_id: str, proposed_rate: float = None, notes: str = None
    ) -> LoadApplication:
        """Carrier apply for a load (alias for apply_to_load with different params)."""
        return await self.apply_to_load(
            load_id=load_id,
            carrier_id=carrier_id,
            bid_amount=proposed_rate,
            message=notes,
        )

    async def get_load_applications(
        self, load_id: str, status: str = None, page: int = 1, page_size: int = 20
    ) -> Tuple[List[LoadApplication], int]:
        """Get applications for a load."""
        query = select(LoadApplication).where(LoadApplication.load_id == load_id)

        if status:
            query = query.where(LoadApplication.status == status)

        # Count
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await self.db.execute(count_query)
        total = total_result.scalar()

        # Paginate
        query = query.offset((page - 1) * page_size).limit(page_size)
        query = query.order_by(LoadApplication.created_at.desc())

        result = await self.db.execute(query)
        applications = result.scalars().all()

        return list(applications), total

    async def get_carrier_applications(
        self, carrier_id: str, status: str = None, page: int = 1, page_size: int = 20
    ) -> Tuple[List[LoadApplication], int]:
        """Get applications by a carrier."""
        query = select(LoadApplication).where(LoadApplication.carrier_id == carrier_id)

        if status:
            query = query.where(LoadApplication.status == status)

        # Count
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await self.db.execute(count_query)
        total = total_result.scalar()

        # Paginate
        query = query.offset((page - 1) * page_size).limit(page_size)
        query = query.order_by(LoadApplication.created_at.desc())

        result = await self.db.execute(query)
        applications = result.scalars().all()

        return list(applications), total

    async def accept_application(self, application_id: str) -> LoadAssignment:
        """Accept a load application and create assignment. Blocks if carrier has expired COI."""
        result = await self.db.execute(
            select(LoadApplication).where(LoadApplication.id == application_id)
        )
        application = result.scalar_one_or_none()

        if not application:
            raise ValueError("Application not found")
        if application.status != "pending":
            raise ValueError("Application is not pending")

        # Get the load
        load = await self.get_load(application.load_id)
        if not load:
            raise ValueError("Load not found")

        # Check carrier COI compliance before accepting
        coi_check = await self._check_carrier_coi_valid(application.carrier_id)
        if not coi_check["valid"]:
            raise ValueError(f"Cannot accept application: {coi_check['reason']}. Carrier must upload valid insurance certificate.")

        # Update application status
        application.status = "accepted"

        # Reject other applications
        await self.db.execute(
            select(LoadApplication).where(
                LoadApplication.load_id == application.load_id,
                LoadApplication.id != application_id,
                LoadApplication.status == "pending"
            )
        )
        # Update rejected applications
        from sqlalchemy import update
        await self.db.execute(
            update(LoadApplication).where(
                LoadApplication.load_id == application.load_id,
                LoadApplication.id != application_id,
                LoadApplication.status == "pending"
            ).values(status="rejected")
        )

        # Create assignment
        assignment = LoadAssignment(
            load_id=application.load_id,
            carrier_id=application.carrier_id,
            agreed_rate=application.bid_amount or load.rate,
            assigned_by=load.shipper_id,
            status="assigned",
        )

        # Update load
        load.status = LoadStatus.ACCEPTED
        load.assigned_carrier_id = application.carrier_id
        load.agreed_rate = application.bid_amount or load.rate
        load.awarded_at = datetime.utcnow()
        load.is_public = False

        self.db.add(assignment)
        await self.db.commit()
        await self.db.refresh(assignment)
        return assignment

    async def reject_application(self, application_id: str, reason: str = None):
        """Reject a load application."""
        result = await self.db.execute(
            select(LoadApplication).where(LoadApplication.id == application_id)
        )
        application = result.scalar_one_or_none()

        if not application:
            raise ValueError("Application not found")
        if application.status != "pending":
            raise ValueError("Application is not pending")

        application.status = "rejected"
        application.rejection_reason = reason

        await self.db.commit()

    async def update_load_status(
        self, load_id: str, new_status: str, user_id: str, notes: str = None
    ) -> Load:
        """Update load status."""
        load = await self.get_load(load_id)
        if not load:
            raise ValueError("Load not found")

        try:
            status_enum = LoadStatus(new_status)
        except ValueError:
            raise ValueError(f"Invalid status: {new_status}")

        # Validate status transition
        valid_transitions = {
            LoadStatus.DRAFT: [LoadStatus.POSTED, LoadStatus.CANCELLED],
            LoadStatus.POSTED: [LoadStatus.TENDERED, LoadStatus.CANCELLED],
            LoadStatus.TENDERED: [LoadStatus.ACCEPTED, LoadStatus.POSTED, LoadStatus.CANCELLED],
            LoadStatus.ACCEPTED: [LoadStatus.DISPATCHED, LoadStatus.CANCELLED],
            LoadStatus.DISPATCHED: [LoadStatus.IN_TRANSIT, LoadStatus.CANCELLED],
            LoadStatus.IN_TRANSIT: [LoadStatus.DELIVERED, LoadStatus.CANCELLED],
            LoadStatus.DELIVERED: [LoadStatus.CLOSED],
            LoadStatus.CLOSED: [],
            LoadStatus.CANCELLED: [],
        }

        if status_enum not in valid_transitions.get(load.status, []):
            raise ValueError(f"Cannot transition from {load.status.value} to {new_status}")

        load.status = status_enum
        load.updated_at = datetime.utcnow()

        # Update timestamps based on status
        if status_enum == LoadStatus.DISPATCHED:
            load.dispatched_at = datetime.utcnow()
        elif status_enum == LoadStatus.DELIVERED:
            load.delivered_at = datetime.utcnow()

        await self.db.commit()
        await self.db.refresh(load)
        return load

