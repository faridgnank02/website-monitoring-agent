"""FastAPI application entry point for Monitor Agent."""

import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI

# Configure root logger so all modules (monitor_service, etc.) output to stdout
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
from fastapi.middleware.cors import CORSMiddleware

from db.base import init_db
from api.auth.router import router as auth_router
from api.routers.monitor import router as monitor_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: create tables if they don't exist
    init_db()
    yield
    # Shutdown: nothing to clean up for now


app = FastAPI(
    title="Monitor Agent API",
    description="Enterprise website change monitoring with AI-powered alerts",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(monitor_router)


@app.get("/health")
def health():
    return {"status": "ok", "service": "monitor-agent"}
