"""Messaging service for chat and conversations."""
from datetime import datetime
from typing import Optional, List, Tuple, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_
import json

from ..models.message import Conversation, Message
from ..schemas.message import ConversationCreate, MessageCreate


class MessageService:
    """Service for messaging operations."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def create_conversation(self, data: ConversationCreate, creator_id: str) -> Conversation:
        """Create a new conversation."""
        # Ensure creator is in participants
        participants = list(set(data.participant_ids + [creator_id]))
        
        conversation = Conversation(
            subject=data.subject,
            conversation_type=data.conversation_type,
            load_id=data.load_id,
            participants=json.dumps(participants),
        )
        
        self.db.add(conversation)
        await self.db.commit()
        await self.db.refresh(conversation)
        return conversation
    
    async def get_conversation(self, conversation_id: str) -> Optional[Conversation]:
        """Get conversation by ID."""
        result = await self.db.execute(select(Conversation).where(Conversation.id == conversation_id))
        return result.scalar_one_or_none()
    
    async def list_user_conversations(
        self,
        user_id: str,
        page: int = 1,
        page_size: int = 20,
    ) -> Tuple[List[Conversation], int]:
        """List user's conversations."""
        # Note: This is a simplified query. In production, use proper JSON querying
        query = select(Conversation).where(
            Conversation.is_active == True,
            Conversation.participants.ilike(f'%"{user_id}"%')
        )
        
        # Count
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await self.db.execute(count_query)
        total = total_result.scalar()
        
        # Paginate and order by last message
        query = query.offset((page - 1) * page_size).limit(page_size)
        query = query.order_by(Conversation.last_message_at.desc().nullslast())
        
        result = await self.db.execute(query)
        conversations = result.scalars().all()
        
        return list(conversations), total
    
    async def send_message(self, data: MessageCreate, sender_id: str) -> Message:
        """Send a message to a conversation."""
        conversation = await self.get_conversation(data.conversation_id)
        if not conversation:
            raise ValueError("Conversation not found")
        
        # Check if sender is participant
        participants = json.loads(conversation.participants)
        if sender_id not in participants:
            raise ValueError("You are not a participant in this conversation")
        
        message = Message(
            conversation_id=data.conversation_id,
            sender_id=sender_id,
            content=data.content,
            message_type=data.message_type,
            attachments=json.dumps(data.attachments) if data.attachments else None,
        )
        
        self.db.add(message)
        
        # Update conversation
        conversation.last_message_at = datetime.utcnow()
        conversation.last_message_preview = data.content[:100] if len(data.content) > 100 else data.content
        
        await self.db.commit()
        await self.db.refresh(message)
        return message
    
    async def get_messages(
        self,
        conversation_id: str,
        user_id: str,
        page: int = 1,
        page_size: int = 50,
    ) -> Tuple[List[Message], int, bool]:
        """Get messages in a conversation."""
        conversation = await self.get_conversation(conversation_id)
        if not conversation:
            raise ValueError("Conversation not found")
        
        participants = json.loads(conversation.participants)
        if user_id not in participants:
            raise ValueError("You are not a participant in this conversation")
        
        query = select(Message).where(
            Message.conversation_id == conversation_id,
            Message.is_deleted == False
        )
        
        # Count
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await self.db.execute(count_query)
        total = total_result.scalar()
        
        # Paginate (newest first for chat)
        query = query.order_by(Message.created_at.desc())
        query = query.offset((page - 1) * page_size).limit(page_size)
        
        result = await self.db.execute(query)
        messages = list(result.scalars().all())
        
        has_more = total > page * page_size
        
        return messages, total, has_more
    
    async def mark_messages_read(self, conversation_id: str, user_id: str):
        """Mark all messages in conversation as read by user."""
        result = await self.db.execute(
            select(Message).where(
                Message.conversation_id == conversation_id,
                Message.sender_id != user_id,
            )
        )
        messages = result.scalars().all()
        
        for message in messages:
            read_by = json.loads(message.read_by) if message.read_by else {}
            if user_id not in read_by:
                read_by[user_id] = datetime.utcnow().isoformat()
                message.read_by = json.dumps(read_by)
        
        await self.db.commit()
    
    async def get_or_create_direct_conversation(self, user1_id: str, user2_id: str) -> Conversation:
        """Get existing direct conversation or create new one."""
        # Look for existing direct conversation between these users
        result = await self.db.execute(
            select(Conversation).where(
                Conversation.conversation_type == "direct",
                Conversation.participants.ilike(f'%"{user1_id}"%'),
                Conversation.participants.ilike(f'%"{user2_id}"%'),
            )
        )
        conversation = result.scalar_one_or_none()
        
        if conversation:
            return conversation
        
        # Create new conversation
        return await self.create_conversation(
            ConversationCreate(
                conversation_type="direct",
                participant_ids=[user1_id, user2_id],
            ),
            creator_id=user1_id
        )

