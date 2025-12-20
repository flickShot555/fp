"""WebSocket handler for real-time messaging."""
from typing import Dict, Set
from fastapi import WebSocket, WebSocketDisconnect, Depends
from sqlalchemy.ext.asyncio import AsyncSession
import json
import logging

from .core.database import get_db
from .core.security import decode_access_token
from .services.message_service import MessageService
from .services.notification_service import NotificationService

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Manages WebSocket connections."""
    
    def __init__(self):
        # user_id -> set of websocket connections
        self.active_connections: Dict[str, Set[WebSocket]] = {}
    
    async def connect(self, websocket: WebSocket, user_id: str):
        """Accept and register a new connection."""
        await websocket.accept()
        
        if user_id not in self.active_connections:
            self.active_connections[user_id] = set()
        
        self.active_connections[user_id].add(websocket)
        logger.info(f"User {user_id} connected. Total connections: {len(self.active_connections)}")
    
    def disconnect(self, websocket: WebSocket, user_id: str):
        """Remove a connection."""
        if user_id in self.active_connections:
            self.active_connections[user_id].discard(websocket)
            
            if not self.active_connections[user_id]:
                del self.active_connections[user_id]
        
        logger.info(f"User {user_id} disconnected. Total connections: {len(self.active_connections)}")
    
    async def send_personal_message(self, message: dict, user_id: str):
        """Send message to a specific user."""
        if user_id in self.active_connections:
            for connection in self.active_connections[user_id]:
                try:
                    await connection.send_json(message)
                except Exception as e:
                    logger.error(f"Error sending message to {user_id}: {e}")
    
    async def send_to_users(self, message: dict, user_ids: list):
        """Send message to multiple users."""
        for user_id in user_ids:
            await self.send_personal_message(message, user_id)
    
    async def broadcast(self, message: dict):
        """Broadcast message to all connected users."""
        for user_id in self.active_connections:
            await self.send_personal_message(message, user_id)


# Global connection manager
manager = ConnectionManager()


async def get_user_from_token(token: str) -> str:
    """Extract user ID from JWT token."""
    try:
        payload = decode_access_token(token)
        return payload.get("sub")
    except Exception:
        return None


async def websocket_endpoint(websocket: WebSocket, token: str):
    """WebSocket endpoint for real-time communication."""
    # Authenticate user
    user_id = await get_user_from_token(token)
    
    if not user_id:
        await websocket.close(code=4001, reason="Invalid token")
        return
    
    await manager.connect(websocket, user_id)
    
    try:
        while True:
            # Receive message
            data = await websocket.receive_text()
            message = json.loads(data)
            
            message_type = message.get("type")
            
            if message_type == "ping":
                # Heartbeat
                await websocket.send_json({"type": "pong"})
            
            elif message_type == "message":
                # Handle chat message
                conversation_id = message.get("conversation_id")
                content = message.get("content")
                
                if conversation_id and content:
                    # Save message to database
                    # This would need a database session
                    
                    # Broadcast to conversation participants
                    await manager.send_personal_message({
                        "type": "new_message",
                        "conversation_id": conversation_id,
                        "sender_id": user_id,
                        "content": content,
                    }, user_id)
            
            elif message_type == "typing":
                # Typing indicator
                conversation_id = message.get("conversation_id")
                
                # Broadcast typing status to other participants
                # This would need to look up conversation participants
            
            elif message_type == "read":
                # Mark messages as read
                conversation_id = message.get("conversation_id")
                
                # Update read status in database
    
    except WebSocketDisconnect:
        manager.disconnect(websocket, user_id)
    except Exception as e:
        logger.error(f"WebSocket error for user {user_id}: {e}")
        manager.disconnect(websocket, user_id)


async def send_notification_to_user(user_id: str, notification: dict):
    """Send a notification to a user via WebSocket."""
    await manager.send_personal_message({
        "type": "notification",
        "data": notification,
    }, user_id)


async def send_message_to_conversation(conversation_id: str, message: dict, participant_ids: list):
    """Send a message to all participants in a conversation."""
    await manager.send_to_users({
        "type": "new_message",
        "conversation_id": conversation_id,
        "data": message,
    }, participant_ids)

