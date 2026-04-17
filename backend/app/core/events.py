"""Simple async event bus for broadcasting pipeline progress to WebSocket clients."""

import asyncio
import json
import logging
from collections import defaultdict

logger = logging.getLogger(__name__)

# campaign_id -> set of asyncio.Queue (one per connected WebSocket client)
_subscribers: dict[str, set[asyncio.Queue]] = defaultdict(set)


def subscribe(campaign_id: str) -> asyncio.Queue:
    """Subscribe to events for a campaign. Returns a Queue to receive events."""
    queue: asyncio.Queue = asyncio.Queue()
    _subscribers[campaign_id].add(queue)
    return queue


def unsubscribe(campaign_id: str, queue: asyncio.Queue) -> None:
    """Unsubscribe from campaign events."""
    _subscribers[campaign_id].discard(queue)
    if not _subscribers[campaign_id]:
        del _subscribers[campaign_id]


async def publish(campaign_id: str, event_type: str, data: dict) -> None:
    """Publish an event to all subscribers of a campaign."""
    message = json.dumps({"type": event_type, **data})
    dead_queues = []
    for queue in _subscribers.get(campaign_id, set()):
        try:
            queue.put_nowait(message)
        except asyncio.QueueFull:
            dead_queues.append(queue)
    for q in dead_queues:
        _subscribers[campaign_id].discard(q)
