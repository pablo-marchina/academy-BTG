from __future__ import annotations
import time
from collections import defaultdict
from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, max_requests: int = 60, window_seconds: int = 60):
        super().__init__(app)
        self.max_requests = max_requests
        self.window = window_seconds
        self._requests: dict = defaultdict(list)

    async def dispatch(self, request: Request, call_next):
        if request.url.path in ("/health", "/metrics"):
            return await call_next(request)

        auth = request.headers.get("Authorization", "")
        client_key = auth.replace("Bearer ", "").strip() or request.client.host or "unknown"
        now = time.time()

        self._requests[client_key] = [t for t in self._requests[client_key] if now - t < self.window]

        if len(self._requests[client_key]) >= self.max_requests:
            raise HTTPException(
                status_code=429,
                detail=f"Limite de {self.max_requests} requisicoes por {self.window}s excedido para esta chave",
            )

        self._requests[client_key].append(now)
        return await call_next(request)
