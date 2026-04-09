from pathlib import Path

from fastapi import APIRouter, Depends, Request
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.dependencies.auth import get_optional_user
from app.models.user import User
from app.services.job_service import get_published_jobs

router = APIRouter()

templates = Jinja2Templates(
    directory=str(Path(__file__).resolve().parent.parent / "templates")
)


@router.get("/")
async def landing_page(
    request: Request,
    user: User | None = Depends(get_optional_user),
    db: AsyncSession = Depends(get_db),
):
    jobs = await get_published_jobs(db)

    return templates.TemplateResponse(
        request,
        "landing.html",
        context={
            "user": user,
            "jobs": jobs,
        },
    )