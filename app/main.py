from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.core.config import settings
from app.core.database import async_session_factory, create_tables
from app.routers.application_routes import router as application_router
from app.routers.audit_routes import router as audit_router
from app.routers.auth_routes import router as auth_router
from app.routers.candidate_routes import router as candidate_router
from app.routers.dashboard_routes import router as dashboard_router
from app.routers.interview_routes import router as interview_router
from app.routers.job_routes import router as job_router
from app.routers.landing import router as landing_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    await create_tables()

    async with async_session_factory() as session:
        try:
            from app.services.user_service import create_default_admin

            admin = await create_default_admin(session)
            if admin is not None:
                await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

    yield


app = FastAPI(
    title=settings.APP_NAME,
    debug=settings.DEBUG,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.ENVIRONMENT == "dev" else [],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

static_dir = Path(__file__).resolve().parent / "static"
if static_dir.is_dir():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

app.include_router(landing_router)
app.include_router(auth_router)
app.include_router(dashboard_router)
app.include_router(job_router)
app.include_router(candidate_router)
app.include_router(application_router)
app.include_router(interview_router)
app.include_router(audit_router)


@app.get("/health")
async def health_check():
    return {"status": "healthy"}