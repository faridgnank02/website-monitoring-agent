from fastapi import APIRouter, Request, Response
from fastapi.responses import StreamingResponse
import json


sse_router = APIRouter()


@sse_router.post("/initialize")
async def initialize(request: Request):
    return {"protocolVersion": "2024-11-05", "capabilities": {"tools": {}}}


@sse_router.post("/message")
async def message(request: Request):
    body = await request.json()
    method = body.get("method")
    if method == "tools/list":
        return {"tools": []}
    elif method == "tools/call":
        return {"content": [{"type": "text", "text": "not implemented"}]}
    return {"error": {"code": -32601, "message": "Method not found"}}


@sse_router.get("/sse")
async def sse_endpoint(request: Request):
    async def event_stream():
        yield "data: {}\n\n"
    return StreamingResponse(event_stream(), media_type="text/event-stream")