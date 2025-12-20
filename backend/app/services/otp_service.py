"""OTP (One-Time Password) service for email and SMS verification."""
from datetime import datetime, timedelta
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete

from ..models.user import User, OTPVerification
from ..core.security import generate_otp
from ..core.config import settings


class OTPService:
    """Service for OTP generation and verification."""
    
    OTP_EXPIRY_MINUTES = 10
    MAX_ATTEMPTS = 3
    
    def __init__(self, db: AsyncSession):
        self.db = db

    async def send_otp(self, user_id: str, channel: str = "email", purpose: str = "verification") -> str:
        """Send OTP to user via specified channel."""
        result = await self.db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()

        if not user:
            raise ValueError("User not found")

        if channel == "email":
            if not user.email:
                raise ValueError("User has no email address")
            return await self.send_email_otp(user.email, user_id)
        elif channel == "sms":
            if not user.phone:
                raise ValueError("User has no phone number")
            return await self.send_sms_otp(user.phone, user_id)
        else:
            raise ValueError(f"Invalid channel: {channel}")

    async def send_email_otp(self, email: str, user_id: str = None) -> str:
        """Generate and send OTP via email."""
        otp_code = generate_otp()
        
        # Delete any existing OTPs for this email
        await self.db.execute(
            delete(OTPVerification).where(
                OTPVerification.email == email,
                OTPVerification.otp_type == "email"
            )
        )
        
        # Create new OTP record
        otp = OTPVerification(
            user_id=user_id,
            email=email,
            otp_code=otp_code,
            otp_type="email",
            expires_at=datetime.utcnow() + timedelta(minutes=self.OTP_EXPIRY_MINUTES),
        )
        self.db.add(otp)
        await self.db.commit()
        
        # Send email via SendGrid
        await self._send_email(email, otp_code)
        
        return otp_code  # For testing; remove in production
    
    async def send_sms_otp(self, phone: str, user_id: str = None) -> str:
        """Generate and send OTP via SMS."""
        otp_code = generate_otp()
        
        # Delete any existing OTPs for this phone
        await self.db.execute(
            delete(OTPVerification).where(
                OTPVerification.phone == phone,
                OTPVerification.otp_type == "sms"
            )
        )
        
        # Create new OTP record
        otp = OTPVerification(
            user_id=user_id,
            phone=phone,
            otp_code=otp_code,
            otp_type="sms",
            expires_at=datetime.utcnow() + timedelta(minutes=self.OTP_EXPIRY_MINUTES),
        )
        self.db.add(otp)
        await self.db.commit()
        
        # Send SMS via Twilio
        await self._send_sms(phone, otp_code)
        
        return otp_code  # For testing; remove in production
    
    async def verify_otp(
        self,
        otp_code: str = None,
        email: str = None,
        phone: str = None,
        otp_type: str = "email",
        user_id: str = None,
        code: str = None,
        purpose: str = "verification",
    ) -> bool:
        """Verify OTP code."""
        # Support both old and new parameter names
        actual_code = code or otp_code
        if not actual_code:
            raise ValueError("OTP code is required")

        query = select(OTPVerification).where(
            OTPVerification.verified == False
        )

        if user_id:
            query = query.where(OTPVerification.user_id == user_id)
        elif email:
            query = query.where(OTPVerification.email == email)
        elif phone:
            query = query.where(OTPVerification.phone == phone)
        else:
            raise ValueError("User ID, email, or phone required")
        
        result = await self.db.execute(query)
        otp_record = result.scalar_one_or_none()
        
        if not otp_record:
            raise ValueError("No OTP found. Please request a new one.")
        
        if otp_record.expires_at < datetime.utcnow():
            raise ValueError("OTP has expired. Please request a new one.")
        
        if otp_record.attempts >= self.MAX_ATTEMPTS:
            raise ValueError("Too many failed attempts. Please request a new OTP.")
        
        if otp_record.otp_code != actual_code:
            otp_record.attempts += 1
            await self.db.commit()
            raise ValueError("Invalid OTP code")
        
        # Mark as verified
        otp_record.verified = True
        
        # Update user verification status
        if otp_record.user_id:
            result = await self.db.execute(select(User).where(User.id == otp_record.user_id))
            user = result.scalar_one_or_none()
            if user:
                if otp_type == "email":
                    user.email_verified = True
                elif otp_type == "sms":
                    user.phone_verified = True
                
                if user.email_verified or user.phone_verified:
                    user.is_verified = True
                    user.verified_at = datetime.utcnow()
        
        await self.db.commit()
        return True
    
    async def _send_email(self, email: str, otp_code: str):
        """Send OTP via SendGrid."""
        if not settings.SENDGRID_API_KEY:
            print(f"[DEV] Email OTP to {email}: {otp_code}")
            return
        
        from sendgrid import SendGridAPIClient
        from sendgrid.helpers.mail import Mail
        
        message = Mail(
            from_email=settings.SENDGRID_FROM_EMAIL,
            to_emails=email,
            subject="FreightPower AI - Verification Code",
            html_content=f"""
            <h2>Your Verification Code</h2>
            <p>Your verification code is: <strong>{otp_code}</strong></p>
            <p>This code will expire in {self.OTP_EXPIRY_MINUTES} minutes.</p>
            <p>If you didn't request this code, please ignore this email.</p>
            """
        )
        
        sg = SendGridAPIClient(settings.SENDGRID_API_KEY)
        await sg.send(message)
    
    async def _send_sms(self, phone: str, otp_code: str):
        """Send OTP via Twilio."""
        if not settings.TWILIO_ACCOUNT_SID:
            print(f"[DEV] SMS OTP to {phone}: {otp_code}")
            return
        
        from twilio.rest import Client
        
        client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
        message = client.messages.create(
            body=f"Your FreightPower AI verification code is: {otp_code}",
            from_=settings.TWILIO_PHONE_NUMBER,
            to=phone
        )
        return message.sid

