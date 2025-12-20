"""Database models for FreightPower AI."""
from .user import User, UserRole, AuditLog, OTPVerification, RefreshToken
from .document import Document, DocumentVersion, DocumentType
from .company import Company, CompanyType
from .load import Load, LoadStatus, LoadApplication, LoadAssignment
from .carrier import Carrier, CarrierProfile, Lane
from .driver import Driver, DriverStatus
from .consent import Consent, ConsentType, ESignature
from .message import Message, Conversation, Notification, NotificationType
from .calendar import CalendarEvent, Task, TaskStatus
from .training import TrainingModule, TrainingProgress, NewsPost

__all__ = [
    "User", "UserRole", "AuditLog", "OTPVerification", "RefreshToken",
    "Document", "DocumentVersion", "DocumentType",
    "Company", "CompanyType",
    "Load", "LoadStatus", "LoadApplication", "LoadAssignment",
    "Carrier", "CarrierProfile", "Lane",
    "Driver", "DriverStatus",
    "Consent", "ConsentType", "ESignature",
    "Message", "Conversation", "Notification", "NotificationType",
    "CalendarEvent", "Task", "TaskStatus",
    "TrainingModule", "TrainingProgress", "NewsPost",
]

