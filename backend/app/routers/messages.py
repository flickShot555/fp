"""Messaging API routes."""
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.database import get_db
from ..core.security import get_current_user, get_current_active_user
from ..models.user import User
from ..schemas.message import (
    ConversationCreate, ConversationResponse, ConversationListResponse,
    MessageCreate, MessageResponse, MessageListResponse
)
from ..services.message_service import MessageService


router = APIRouter(prefix="/messages", tags=["Messaging"])


@router.post("/conversations", response_model=ConversationResponse, status_code=status.HTTP_201_CREATED)
async def create_conversation(
    data: ConversationCreate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Create a new conversation."""
    message_service = MessageService(db)
    
    try:
        conversation = await message_service.create_conversation(data, creator_id=current_user.id)
        return conversation
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/conversations", response_model=ConversationListResponse)
async def list_conversations(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """List user's conversations."""
    message_service = MessageService(db)
    
    conversations, total = await message_service.list_user_conversations(
        user_id=current_user.id,
        page=page,
        page_size=page_size,
    )
    
    return ConversationListResponse(
        conversations=conversations,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/conversations/{conversation_id}", response_model=ConversationResponse)
async def get_conversation(
    conversation_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Get conversation by ID."""
    message_service = MessageService(db)
    
    conversation = await message_service.get_conversation(conversation_id)
    if not conversation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")
    
    return conversation


@router.get("/conversations/{conversation_id}/messages", response_model=MessageListResponse)
async def get_messages(
    conversation_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Get messages in a conversation."""
    message_service = MessageService(db)
    
    try:
        messages, total, has_more = await message_service.get_messages(
            conversation_id=conversation_id,
            user_id=current_user.id,
            page=page,
            page_size=page_size,
        )
        
        return MessageListResponse(
            messages=messages,
            total=total,
            page=page,
            page_size=page_size,
            has_more=has_more,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))


@router.post("/conversations/{conversation_id}/messages", response_model=MessageResponse, status_code=status.HTTP_201_CREATED)
async def send_message(
    conversation_id: str,
    data: MessageCreate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Send a message to a conversation."""
    message_service = MessageService(db)
    
    # Override conversation_id from path
    data.conversation_id = conversation_id
    
    try:
        message = await message_service.send_message(data, sender_id=current_user.id)
        return message
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/conversations/{conversation_id}/read")
async def mark_as_read(
    conversation_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Mark all messages in conversation as read."""
    message_service = MessageService(db)
    
    await message_service.mark_messages_read(conversation_id, current_user.id)
    return {"message": "Messages marked as read"}


@router.post("/direct/{user_id}", response_model=ConversationResponse)
async def get_or_create_direct_conversation(
    user_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Get or create a direct conversation with another user."""
    message_service = MessageService(db)
    
    conversation = await message_service.get_or_create_direct_conversation(
        user1_id=current_user.id,
        user2_id=user_id,
    )
    
    return conversation

