"""AI service for document processing and chat."""
from datetime import datetime
from typing import Optional, Dict, Any, List
import base64
import json
import io
import logging

from ..core.config import settings

logger = logging.getLogger(__name__)


class AIService:
    """Service for AI-powered document processing and chat."""
    
    def __init__(self):
        self.groq_api_key = settings.GROQ_API_KEY
        self.text_model = settings.GROQ_TEXT_MODEL
        self.vision_model = settings.GROQ_VISION_MODEL
    
    async def classify_document(self, content: bytes, mime_type: str) -> Dict[str, Any]:
        """Classify document type using AI."""
        if not self.groq_api_key:
            return {"type": "other", "confidence": 0.0}
        
        from groq import Groq
        
        client = Groq(api_key=self.groq_api_key)
        
        # Handle PDF documents - extract text for classification
        pdf_text = None
        if mime_type == "application/pdf":
            try:
                import PyPDF2
                pdf_reader = PyPDF2.PdfReader(io.BytesIO(content))
                pdf_text = ""
                # Extract first 5 pages for classification
                for i, page in enumerate(pdf_reader.pages[:5]):
                    pdf_text += page.extract_text()
                logger.info(f"Extracted {len(pdf_text)} characters from PDF for classification")
            except Exception as e:
                logger.warning(f"Failed to extract PDF text: {e}")
                pdf_text = None
        
        # Handle images
        if mime_type.startswith("image/"):
            base64_content = base64.b64encode(content).decode("utf-8")
            
            response = client.chat.completions.create(
                model=self.vision_model,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": """Classify this document. Return JSON only:
                                {"type": "cdl|mc_certificate|coi|w9|bol|pod|rate_confirmation|invoice|mvr|medical_card|drug_test|authority|other", "confidence": 0.0-1.0}
                                
                                Types:
                                - cdl: Commercial Driver's License
                                - mc_certificate: Motor Carrier Authority Certificate / MC Authority
                                - coi: Certificate of Insurance
                                - w9: Tax form W-9
                                - bol: Bill of Lading
                                - pod: Proof of Delivery
                                - rate_confirmation: Rate Confirmation
                                - invoice: Invoice
                                - mvr: Motor Vehicle Record
                                - medical_card: DOT Medical Card
                                - drug_test: Drug Test Results
                                - authority: Operating Authority / Broker Agreement
                                - other: Unknown/Other"""
                            },
                            {
                                "type": "image_url",
                                "image_url": {"url": f"data:{mime_type};base64,{base64_content}"}
                            }
                        ]
                    }
                ],
                temperature=0.1,
                max_tokens=100,
            )
            
            try:
                result = json.loads(response.choices[0].message.content)
                return result
            except json.JSONDecodeError:
                return {"type": "other", "confidence": 0.0}
        
        # Handle PDFs via text extraction
        elif mime_type == "application/pdf" and pdf_text:
            response = client.chat.completions.create(
                model=self.text_model,
                messages=[
                    {
                        "role": "user",
                        "content": f"""Classify this document based on the text. Return ONLY valid JSON:
                        {{"type": "cdl|mc_certificate|coi|w9|bol|pod|rate_confirmation|invoice|mvr|medical_card|drug_test|authority|other", "confidence": 0.0-1.0}}
                        
                        Document text:
                        {pdf_text[:2000]}
                        
                        Types:
                        - cdl: Commercial Driver's License
                        - mc_certificate: Motor Carrier Authority Certificate / MC Authority / MC Number
                        - coi: Certificate of Insurance / COI / General Liability
                        - w9: Tax form W-9 / Form W9
                        - bol: Bill of Lading
                        - pod: Proof of Delivery
                        - rate_confirmation: Rate Confirmation
                        - invoice: Invoice
                        - mvr: Motor Vehicle Record
                        - medical_card: DOT Medical Card / Medical Exam
                        - drug_test: Drug Test Results
                        - authority: Operating Authority / Broker Agreement / Carrier Agreement
                        - other: Unknown/Other"""
                    }
                ],
                temperature=0.1,
                max_tokens=100,
            )
            
            try:
                result = json.loads(response.choices[0].message.content)
                logger.info(f"PDF classified as: {result}")
                return result
            except json.JSONDecodeError as e:
                logger.warning(f"Failed to parse classification JSON: {response.choices[0].message.content}")
                return {"type": "other", "confidence": 0.0}
        
        return {"type": "other", "confidence": 0.0}
    
    async def extract_document_data(
        self, content: bytes, mime_type: str, document_type: str
    ) -> Dict[str, Any]:
        """Extract data from document using AI."""
        if not self.groq_api_key:
            return {"text": "", "data": {}, "ocr": {}}
        
        from groq import Groq
        
        client = Groq(api_key=self.groq_api_key)
        
        extraction_prompts = {
            "cdl": "Extract: cdl_number, cdl_class, state, expiry_date (YYYY-MM-DD), name, address, endorsements, restrictions",
            "mc_certificate": "Extract: mc_number, usdot, legal_name, effective_date, authority_type",
            "coi": "Extract: policy_number, carrier, coverage_amount, effective_date, expiry_date (YYYY-MM-DD), insured_name",
            "medical_card": "Extract: expiry_date (YYYY-MM-DD), driver_name, examiner_name, restrictions",
            "bol": "Extract: bol_number, shipper, consignee, origin, destination, commodity, weight, pieces",
            "pod": "Extract: delivery_date, receiver_name, signature_present (true/false), notes",
        }
        
        prompt = extraction_prompts.get(document_type, "Extract all relevant information")
        
        if mime_type.startswith("image/"):
            base64_content = base64.b64encode(content).decode("utf-8")
            
            response = client.chat.completions.create(
                model=self.vision_model,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": f"Extract document data as JSON. {prompt}"},
                            {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{base64_content}"}}
                        ]
                    }
                ],
                temperature=0.1,
                max_tokens=500,
            )
            
            try:
                data = json.loads(response.choices[0].message.content)
                return {"text": "", "data": data, "ocr": {}}
            except json.JSONDecodeError:
                return {"text": response.choices[0].message.content, "data": {}, "ocr": {}}
        
        return {"text": "", "data": {}, "ocr": {}}
    
    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        system_prompt: str = None,
        temperature: float = 0.7,
    ) -> str:
        """Generate chat completion."""
        if not self.groq_api_key:
            return "AI service not configured."
        
        from groq import Groq
        
        client = Groq(api_key=self.groq_api_key)
        
        all_messages = []
        if system_prompt:
            all_messages.append({"role": "system", "content": system_prompt})
        all_messages.extend(messages)
        
        response = client.chat.completions.create(
            model=self.text_model,
            messages=all_messages,
            temperature=temperature,
            max_tokens=1000,
        )
        
        return response.choices[0].message.content
    
    async def generate_compliance_recommendations(
        self,
        carrier_data: Dict,
        documents: List[Dict],
    ) -> List[Dict[str, Any]]:
        """Generate AI-powered compliance recommendations."""
        prompt = f"""
        Based on this carrier data and documents, provide compliance recommendations:
        
        Carrier: {json.dumps(carrier_data, default=str)}
        Documents: {json.dumps(documents, default=str)}
        
        Return JSON array of recommendations:
        [
            {{"priority": "high|medium|low", "category": "documents|insurance|authority|safety", 
              "title": "...", "description": "...", "action": "..."}}
        ]
        """
        
        response = await self.chat_completion(
            messages=[{"role": "user", "content": prompt}],
            system_prompt="You are a freight compliance expert. Provide actionable recommendations.",
            temperature=0.3,
        )

        try:
            return json.loads(response)
        except json.JSONDecodeError:
            return []

    async def chat(self, message: str, context: str = "general") -> str:
        """
        General chat endpoint for AI assistant.

        Args:
            message: User message
            context: Context for the chat (onboarding, compliance, etc.)

        Returns:
            AI response string
        """
        system_prompts = {
            "onboarding": """You are a helpful onboarding assistant for FreightPower AI,
            a freight management platform. Help users understand the onboarding process,
            required documents, and compliance requirements. Be friendly and professional.""",
            "compliance": """You are a freight compliance expert. Help users understand
            FMCSA regulations, document requirements, and compliance best practices.""",
            "general": """You are a helpful assistant for FreightPower AI, a freight
            management platform. Help users with their questions about the platform.""",
        }

        system_prompt = system_prompts.get(context, system_prompts["general"])

        response = await self.chat_completion(
            messages=[{"role": "user", "content": message}],
            system_prompt=system_prompt,
            temperature=0.7,
        )

        return response
