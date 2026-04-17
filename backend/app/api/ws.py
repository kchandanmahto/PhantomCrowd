"""WebSocket endpoint for real-time campaign progress streaming."""

import asyncio
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.core.events import subscribe, unsubscribe

logger = logging.getLogger(__name__)
router = APIRouter()


@router.websocket("/ws/campaigns/{campaign_id}")
async def campaign_ws(websocket: WebSocket, campaign_id: str):
    """Stream real-time events for a campaign pipeline."""
    await websocket.accept()
    queue = subscribe(campaign_id)
    try:
        while True:
            message = await queue.get()
            await websocket.send_text(message)
    except WebSocketDisconnect:
        pass
    except Exception:
        logger.debug("WebSocket closed for campaign %s", campaign_id)
    finally:
        unsubscribe(campaign_id, queue)
