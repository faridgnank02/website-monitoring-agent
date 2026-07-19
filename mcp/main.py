from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from mcp.transport import sse_router
from mcp.auth import api_key_middleware


app = FastAPI(
    title="Monitor Agent MCP Server",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.middleware("http")(api_key_middleware)

app.include_router(sse_router, prefix="/mcp")


@app.get("/health")
async def health():
    return {"status": "ok"}