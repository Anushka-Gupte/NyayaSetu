import json
import logging
import asyncio
from typing import Dict, List, Set, Any
from fastapi import WebSocket

logger = logging.getLogger("nyayasetu.websocket")

class ConnectionManager:
    """
    Manages real-time WebSocket client connections and topic broadcasting
    (SRS Section 3.4 Communication Protocols - WebSocket).
    """
    def __init__(self):
        # Maps topic string to set of active WebSockets
        # Topics: "court:all", "courtroom:{id}", "case:{id}"
        self.active_subscriptions: Dict[str, Set[WebSocket]] = {}
        self.all_connections: Set[WebSocket] = set()

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.all_connections.add(websocket)
        # Default subscribe to court-wide live feed
        self.subscribe(websocket, "court:all")

    def disconnect(self, websocket: WebSocket):
        self.all_connections.discard(websocket)
        for topic, subs in list(self.active_subscriptions.items()):
            subs.discard(websocket)
            if not subs:
                del self.active_subscriptions[topic]

    def subscribe(self, websocket: WebSocket, topic: str):
        if topic not in self.active_subscriptions:
            self.active_subscriptions[topic] = set()
        self.active_subscriptions[topic].add(websocket)

    def unsubscribe(self, websocket: WebSocket, topic: str):
        if topic in self.active_subscriptions:
            self.active_subscriptions[topic].discard(websocket)
            if not self.active_subscriptions[topic]:
                del self.active_subscriptions[topic]

    async def _async_send(self, websocket: WebSocket, payload: str):
        try:
            await websocket.send_text(payload)
        except Exception:
            self.disconnect(websocket)

    async def broadcast_to_topic(self, topic: str, message: Dict[str, Any]):
        """
        Broadcasts message to all clients subscribed to a specific topic.
        """
        payload = json.dumps(message)
        subscribers = self.active_subscriptions.get(topic, set()).copy()
        for connection in subscribers:
            await self._async_send(connection, payload)

    def broadcast_court_event(self, event_type: str, data: Dict[str, Any]):
        """
        Thread-safe broadcast that dispatches to running asyncio event loops if active,
        or safely completes without blocking.
        """
        message = {
            "event": event_type,
            "timestamp": data.get("timestamp"),
            "data": data
        }
        try:
            loop = asyncio.get_running_loop()
            # If event loop is running (e.g. inside Uvicorn), schedule tasks
            asyncio.create_task(self.broadcast_to_topic("court:all", message))
            if "courtroom_id" in data:
                asyncio.create_task(self.broadcast_to_topic(f"courtroom:{data['courtroom_id']}", message))
            if "case_id" in data:
                asyncio.create_task(self.broadcast_to_topic(f"case:{data['case_id']}", message))
        except RuntimeError:
            # No running event loop (e.g. running in synchronous test or CLI)
            pass

ws_manager = ConnectionManager()
