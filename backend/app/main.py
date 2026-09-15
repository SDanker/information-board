from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.bootstrap import ensure_initial_data
from app.config import get_settings
from app.i18n import LanguageMiddleware
from app.logging_config import configure_logging
from app.network_restriction import NetworkRestrictionMiddleware
from app.realtime import manager as realtime_manager
from app.routers import auth, branding, content, emergencies, health, operation, playlists, realtime, screens, sharing, users


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings = get_settings()
    if settings.app_env == "production":
        problems = settings.insecure_production_settings()
        if problems:
            raise RuntimeError(
                "Refusing to start in production with placeholder or weak values for: "
                f"{', '.join(problems)}. Run scripts/setup.py or edit .env (see .env.example)."
            )
    ensure_initial_data()
    if not settings.testing:
        await realtime_manager.start()
    yield
    if not settings.testing:
        await realtime_manager.stop()


settings = get_settings()
if not settings.testing:
    configure_logging()

cors_origins = [settings.public_base_url, "http://localhost", "http://localhost:3000"]
cors_origins += [origin.strip() for origin in settings.cors_extra_origins.split(",") if origin.strip()]

app = FastAPI(title=settings.app_name, version=__version__, lifespan=lifespan)
# Starlette runs the last middleware added first: CORS, then language detection (so
# the network restriction message is already translated), then the network check.
app.add_middleware(NetworkRestrictionMiddleware)
app.add_middleware(LanguageMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(health.router, prefix="/api/v1")
app.include_router(auth.router, prefix="/api/v1/auth")
app.include_router(branding.router, prefix="/api/v1")
app.include_router(screens.router, prefix="/api/v1")
app.include_router(content.router, prefix="/api/v1")
app.include_router(playlists.router, prefix="/api/v1")
app.include_router(sharing.router, prefix="/api/v1")
app.include_router(emergencies.router, prefix="/api/v1")
app.include_router(users.router, prefix="/api/v1")
app.include_router(operation.router, prefix="/api/v1")
app.include_router(realtime.router)
