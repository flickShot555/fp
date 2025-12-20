"""FMCSA integration service for carrier verification."""
from datetime import datetime
from typing import Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import httpx
import json

from ..models.carrier import Carrier
from ..models.company import Company
from ..core.config import settings


class FMCSAService:
    """Service for FMCSA API integration."""
    
    def __init__(self, db: AsyncSession = None):
        self.db = db
        self.base_url = settings.FMCSA_BASE_URL
        self.web_key = settings.FMCSA_WEB_KEY
    
    async def lookup_carrier_by_usdot(self, usdot: str) -> Dict[str, Any]:
        """Look up carrier by USDOT number."""
        url = f"{self.base_url}/carriers/{usdot}"
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    url,
                    params={"webKey": self.web_key},
                    timeout=30.0,
                )
                
                if response.status_code == 200:
                    data = response.json()
                    return self._parse_carrier_data(data)
                else:
                    return {"error": f"FMCSA API returned status {response.status_code}"}
            
            except httpx.RequestError as e:
                return {"error": f"Request failed: {str(e)}"}
    
    async def lookup_carrier_by_mc(self, mc_number: str) -> Dict[str, Any]:
        """Look up carrier by MC number."""
        # Strip MC- prefix if present
        mc_clean = mc_number.replace("MC-", "").replace("MC", "").strip()
        
        url = f"{self.base_url}/carriers/docket-number/{mc_clean}"
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    url,
                    params={"webKey": self.web_key},
                    timeout=30.0,
                )
                
                if response.status_code == 200:
                    data = response.json()
                    return self._parse_carrier_data(data)
                else:
                    return {"error": f"FMCSA API returned status {response.status_code}"}
            
            except httpx.RequestError as e:
                return {"error": f"Request failed: {str(e)}"}
    
    def _parse_carrier_data(self, data: Dict) -> Dict[str, Any]:
        """Parse FMCSA response data."""
        content = data.get("content", {})
        carrier = content.get("carrier", {})
        
        return {
            "usdot": carrier.get("dotNumber"),
            "mc_number": carrier.get("mcNumber"),
            "legal_name": carrier.get("legalName"),
            "dba_name": carrier.get("dbaName"),
            "physical_address": {
                "street": carrier.get("phyStreet"),
                "city": carrier.get("phyCity"),
                "state": carrier.get("phyState"),
                "zip": carrier.get("phyZipcode"),
                "country": carrier.get("phyCountry"),
            },
            "mailing_address": {
                "street": carrier.get("mailingStreet"),
                "city": carrier.get("mailingCity"),
                "state": carrier.get("mailingState"),
                "zip": carrier.get("mailingZipcode"),
            },
            "phone": carrier.get("telephone"),
            "fax": carrier.get("fax"),
            "email": carrier.get("emailAddress"),
            "operating_status": carrier.get("allowedToOperate"),
            "entity_type": carrier.get("carrierOperation", {}).get("carrierOperationDesc"),
            "safety_rating": carrier.get("safetyRating"),
            "safety_rating_date": carrier.get("safetyRatingDate"),
            "power_units": carrier.get("totalPowerUnits"),
            "drivers": carrier.get("totalDrivers"),
            "mcs150_date": carrier.get("mcs150FormDate"),
            "insurance": self._parse_insurance(carrier),
            "is_authorized": carrier.get("allowedToOperate") == "Y",
            "raw_data": carrier,
        }
    
    def _parse_insurance(self, carrier: Dict) -> Dict[str, Any]:
        """Parse insurance information from carrier data."""
        return {
            "bipd_insurance_required": carrier.get("bipdInsuranceRequired"),
            "bipd_insurance_on_file": carrier.get("bipdInsuranceOnFile"),
            "cargo_insurance_required": carrier.get("cargoInsuranceRequired"),
            "cargo_insurance_on_file": carrier.get("cargoInsuranceOnFile"),
            "bond_insurance_required": carrier.get("bondInsuranceRequired"),
            "bond_insurance_on_file": carrier.get("bondInsuranceOnFile"),
        }
    
    async def verify_carrier(self, carrier_id: str, usdot: str = None, mc_number: str = None) -> Dict[str, Any]:
        """Verify carrier against FMCSA database."""
        if not self.db:
            raise ValueError("Database session required for verification")
        
        # Look up from FMCSA
        if usdot:
            fmcsa_data = await self.lookup_carrier_by_usdot(usdot)
        elif mc_number:
            fmcsa_data = await self.lookup_carrier_by_mc(mc_number)
        else:
            return {"error": "USDOT or MC number required"}
        
        if "error" in fmcsa_data:
            return fmcsa_data
        
        # Get carrier and company
        result = await self.db.execute(select(Carrier).where(Carrier.id == carrier_id))
        carrier = result.scalar_one_or_none()
        
        if not carrier:
            return {"error": "Carrier not found"}
        
        # Update carrier
        carrier.fmcsa_verified = fmcsa_data.get("is_authorized", False)
        carrier.fmcsa_verification_date = datetime.utcnow()
        carrier.fmcsa_verification_data = json.dumps(fmcsa_data)
        carrier.power_units = fmcsa_data.get("power_units") or carrier.power_units
        
        # Update company
        if carrier.company_id:
            company_result = await self.db.execute(select(Company).where(Company.id == carrier.company_id))
            company = company_result.scalar_one_or_none()
            
            if company:
                company.legal_name = fmcsa_data.get("legal_name") or company.legal_name
                company.dba_name = fmcsa_data.get("dba_name")
                company.usdot = fmcsa_data.get("usdot") or company.usdot
                company.mc_number = fmcsa_data.get("mc_number") or company.mc_number
                company.fmcsa_status = "AUTHORIZED" if fmcsa_data.get("is_authorized") else "NOT_AUTHORIZED"
                company.operating_status = fmcsa_data.get("operating_status")
                company.safety_rating = fmcsa_data.get("safety_rating")
                company.power_units = fmcsa_data.get("power_units") or company.power_units
                company.drivers_count = fmcsa_data.get("drivers") or company.drivers_count
        
        await self.db.commit()
        
        return {
            "carrier_id": carrier_id,
            "usdot": fmcsa_data.get("usdot"),
            "mc_number": fmcsa_data.get("mc_number"),
            "legal_name": fmcsa_data.get("legal_name"),
            "dba_name": fmcsa_data.get("dba_name"),
            "operating_status": fmcsa_data.get("operating_status"),
            "authority_status": "AUTHORIZED" if fmcsa_data.get("is_authorized") else "NOT_AUTHORIZED",
            "safety_rating": fmcsa_data.get("safety_rating"),
            "insurance_status": "ON_FILE" if fmcsa_data.get("insurance", {}).get("bipd_insurance_on_file") == "Y" else "MISSING",
            "is_authorized": fmcsa_data.get("is_authorized", False),
            "issues": self._identify_issues(fmcsa_data),
            "raw_data": fmcsa_data,
        }
    
    def _identify_issues(self, data: Dict) -> list:
        """Identify compliance issues from FMCSA data."""
        issues = []
        
        if not data.get("is_authorized"):
            issues.append("Carrier is not authorized to operate")
        
        insurance = data.get("insurance", {})
        if insurance.get("bipd_insurance_required") == "Y" and insurance.get("bipd_insurance_on_file") != "Y":
            issues.append("BIPD insurance required but not on file")
        if insurance.get("cargo_insurance_required") == "Y" and insurance.get("cargo_insurance_on_file") != "Y":
            issues.append("Cargo insurance required but not on file")
        
        if data.get("safety_rating") == "UNSATISFACTORY":
            issues.append("Unsatisfactory safety rating")
        
        return issues

