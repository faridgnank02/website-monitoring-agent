from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
import os


MCP_API_KEY = os.getenv("MCP_API_KEY", "")


class APIKeyMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.url.path.startswith("/mcp"):
            api_key = request.headers.get("X-API-Key")
            if not api_key or api_key != MCP_API_KEY:
                raise HTTPException(status_code=403, detail="Invalid API key")
        return await call_next(request)