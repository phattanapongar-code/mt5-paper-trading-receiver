from __future__ import annotations

import asyncio
import json
from typing import Any, Awaitable, Callable

from app.multibot.runtime import hub

ASGIApp = Callable[[dict[str, Any], Callable[[], Awaitable[dict[str, Any]]], Callable[[dict[str, Any]], Awaitable[None]]], Awaitable[None]]


class MultiBotTickMiddleware:
    """Fan out accepted /price payloads without slowing or draining the legacy receiver body.

    The middleware buffers the incoming body, replays the same bytes to the existing
    FastAPI route, lets the route reply first, and then submits the payload to the
    latest-tick-wins background queue. The sender path therefore stays responsive.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: dict[str, Any], receive, send) -> None:
        if scope.get("type") != "http" or scope.get("method") != "POST" or scope.get("path") != "/price":
            await self.app(scope, receive, send)
            return

        body_parts: list[bytes] = []
        while True:
            message = await receive()
            if message.get("type") == "http.disconnect":
                await self.app(scope, receive, send)
                return
            if message.get("type") != "http.request":
                continue
            body_parts.append(message.get("body", b""))
            if not message.get("more_body", False):
                break

        body = b"".join(body_parts)
        replayed = False
        response_status = 500
        submitted = False

        async def replay_receive() -> dict[str, Any]:
            nonlocal replayed
            if not replayed:
                replayed = True
                return {"type": "http.request", "body": body, "more_body": False}
            return {"type": "http.disconnect"}

        async def send_wrapper(message: dict[str, Any]) -> None:
            nonlocal response_status, submitted
            if message.get("type") == "http.response.start":
                response_status = int(message.get("status", 500))
            await send(message)
            if (
                not submitted
                and message.get("type") == "http.response.body"
                and not message.get("more_body", False)
                and response_status < 400
            ):
                submitted = True
                try:
                    payload = json.loads(body.decode("utf-8"))
                    if payload.get("type") in {"tick", "heartbeat"} and payload.get("bid") is not None and payload.get("ask") is not None:
                        asyncio.create_task(hub.submit(payload))
                except Exception:
                    pass

        await self.app(scope, replay_receive, send_wrapper)
