from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.core.config import settings
from app.core.auth import require_api_key
from app.core.database import init_db
from app.api.simulations import router as simulations_router
from app.api.ab_tests import router as ab_tests_router
from app.api.export import router as export_router
from app.api.campaigns import router as campaigns_router
from app.api.ws import router as ws_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


app = FastAPI(
    title="PhantomCrowd",
    description="AI Audience Simulator - Preview how your content will be received before publishing",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API routes — auth applied when PC_API_KEY is set
api_deps = [require_api_key] if settings.api_key else []
app.include_router(simulations_router, prefix="/api", dependencies=[*api_deps])
app.include_router(ab_tests_router, prefix="/api", dependencies=[*api_deps])
app.include_router(export_router, prefix="/api", dependencies=[*api_deps])
app.include_router(campaigns_router, prefix="/api", dependencies=[*api_deps])
# WebSocket — no auth (uses campaign_id as implicit scope)
app.include_router(ws_router)


@app.get("/api/health")
async def health():
    return {"status": "ok", "app": settings.app_name, "auth_enabled": bool(settings.api_key)}


# Serve frontend static files in production (Docker)
static_dir = Path(__file__).parent.parent / "static"
if static_dir.exists():
    app.mount("/", StaticFiles(directory=str(static_dir), html=True), name="static")
