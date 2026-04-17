import asyncio
import logging
import time
from typing import Set

logger = logging.getLogger(__name__)


class EventBus:
    def __init__(self):
        self._clients: Set[asyncio.Queue] = set()

    def connect(self) -> asyncio.Queue:
        q = asyncio.Queue()
        self._clients.add(q)
        logger.info(f"SSE client connected. Total: {len(self._clients)}")
        return q

    def disconnect(self, q: asyncio.Queue):
        self._clients.discard(q)
        logger.info(f"SSE client disconnected. Total: {len(self._clients)}")

    async def broadcast(self, event_type: str, data: str = ""):
        if not self._clients:
            return
        message = f"event: {event_type}\ndata: {data}\n\n"
        dead = []
        for q in self._clients:
            try:
                q.put_nowait(message)
            except asyncio.QueueFull:
                dead.append(q)
        for q in dead:
            self._clients.discard(q)

    @property
    def client_count(self) -> int:
        return len(self._clients)


event_bus = EventBus()
