from __future__ import annotations
import json
from typing import AsyncIterator

from fastapi.responses import StreamingResponse

# Shared SSE wire format for every streaming agent endpoint (landing chat/
# Aria, Command Center, Finance Agent) — each yields plain dicts (e.g.
# {"type": "chunk", "text": "..."}), this formats them as a standard
# `data: <json>\n\n` event stream. A POST body is what carries the question
# (Bearer-authed endpoints can't use a GET-only browser EventSource), so the
# frontend consumes this via fetch()'s ReadableStream, not new EventSource().
async def _to_sse_bytes(events: AsyncIterator[dict]) -> AsyncIterator[bytes]:
    try:
        async for event in events:
            yield f"data: {json.dumps(event)}\n\n".encode("utf-8")
    except Exception as exc:  # never let a mid-stream crash hang the connection open
        yield f"data: {json.dumps({'type': 'error', 'message': str(exc)})}\n\n".encode("utf-8")


def sse_response(events: AsyncIterator[dict]) -> StreamingResponse:
    return StreamingResponse(
        _to_sse_bytes(events),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            # Disables buffering on nginx-style reverse proxies so chunks
            # reach the browser as they're produced, not batched.
            "X-Accel-Buffering": "no",
        },
    )
