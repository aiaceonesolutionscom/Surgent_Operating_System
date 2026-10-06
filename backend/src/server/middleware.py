import time
import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from src.server.runtime_metrics import record_request

logger = logging.getLogger("aesthetixai")


# Shared with main.py's exception handlers — see the comment there for why:
# CORSMiddleware never adds its header to a response built by a registered
# `@app.exception_handler`, in any FastAPI/Starlette setup (confirmed with a
# minimal repro with zero custom middleware) — so those handlers add this
# header themselves instead of relying on CORSMiddleware to do it.
ALLOWED_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:5183",
    "http://localhost:3000",
]


class AuditLogMiddleware:
    # Plain ASGI middleware, not `BaseHTTPMiddleware` — kept this way since
    # it's the more robust pattern in general (BaseHTTPMiddleware's
    # `call_next()` has its own documented history of mishandling responses
    # from deep exceptions), even though it turned out not to be the actual
    # cause of the CORS-on-error issue described above.
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        start = time.time()
        status_holder = {}

        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                status_holder["status"] = message["status"]
            await send(message)

        await self.app(scope, receive, send_wrapper)

        duration = time.time() - start
        # Feed the Super Admin SYSTEM panel (admin/platform_metrics) — the
        # same timing the log line below already computes, at no extra cost.
        record_request(duration * 1000, status_holder.get("status"))
        logger.info(
            "%s %s %s %.2fms",
            scope.get("method"),
            scope.get("path"),
            status_holder.get("status"),
            duration * 1000,
        )


def setup_middleware(app: FastAPI):
    app.add_middleware(
        CORSMiddleware,
        allow_origins=ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.add_middleware(AuditLogMiddleware)
