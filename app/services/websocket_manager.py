"""WebSocket connection manager for real-time queue updates"""

from typing import Dict, List, Set
from fastapi import WebSocket
import json
from datetime import datetime

class ConnectionManager:
    def __init__(self):
        # Active WebSocket connections by assignment_id
        self.active_connections: Dict[int, List[WebSocket]] = {}
        # Track which user is connected to which assignment
        self.user_assignments: Dict[int, Set[int]] = {}  # user_id -> set of assignment_ids

    async def connect(self, websocket: WebSocket, session_id: int, user_id: int):
        """Accept a new WebSocket connection"""
        await websocket.accept()

        # Add to session connections
        if session_id not in self.active_connections:
            self.active_connections[session_id] = []
        self.active_connections[session_id].append(websocket)

        # Track user's assignments
        if user_id not in self.user_assignments:
            self.user_assignments[user_id] = set()
        self.user_assignments[user_id].add(session_id)

    def disconnect(self, websocket: WebSocket, session_id: int, user_id: int):
        """Remove a WebSocket connection"""
        if session_id in self.active_connections:
            self.active_connections[session_id].remove(websocket)
            if not self.active_connections[session_id]:
                del self.active_connections[session_id]

        if user_id in self.user_assignments:
            self.user_assignments[user_id].discard(session_id)
            if not self.user_assignments[user_id]:
                del self.user_assignments[user_id]

    async def send_personal_message(self, message: str, websocket: WebSocket):
        """Send a message to a specific WebSocket"""
        await websocket.send_text(message)

    async def broadcast_to_session(self, message: dict, session_id: int):
        """Broadcast a message to all connections in a session"""
        if session_id in self.active_connections:
            message_text = json.dumps(message)
            disconnected = []

            for connection in self.active_connections[session_id]:
                try:
                    await connection.send_text(message_text)
                except:
                    # SAFE REMOVAL: Check if it's still there before removing
                    if connection in self.active_connections[session_id]:
                        self.active_connections[session_id].remove(connection)

            # Clean up disconnected connections
            for conn in disconnected:
                self.active_connections[session_id].remove(conn)

    async def notify_queue_update(self, session_id: int, queue_data: dict):
        """Notify all users in a session about queue updates"""
        message = {
            "type": "queue_update",
            "timestamp": datetime.utcnow().isoformat(),
            "data": queue_data
        }
        await self.broadcast_to_session(message, session_id)

    async def notify_position_change(self, session_id: int, student_id: int, new_position: int):
        """Notify about a student's position change in the queue"""
        message = {
            "type": "position_change",
            "timestamp": datetime.utcnow().isoformat(),
            "student_id": student_id,
            "new_position": new_position
        }
        await self.broadcast_to_session(message, session_id)

    async def notify_student_called(self, session_id: int, student_id: int, ta_name: str):
        """Notify when a student is called by a TA"""
        message = {
            "type": "student_called",
            "timestamp": datetime.utcnow().isoformat(),
            "student_id": student_id,
            "ta_name": ta_name
        }
        await self.broadcast_to_session(message, session_id)

    async def notify_progress_update(self, session_id: int, student_id: int, progress_data: dict):
        """Notify about a student's progress update"""
        message = {
            "type": "progress_update",
            "timestamp": datetime.utcnow().isoformat(),
            "student_id": student_id,
            "progress": progress_data
        }
        await self.broadcast_to_session(message, session_id)

# Global instance
manager = ConnectionManager()
