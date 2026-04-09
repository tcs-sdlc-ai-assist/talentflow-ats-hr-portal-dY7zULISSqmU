from pathlib import Path

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.dependencies.auth import get_current_user
from app.dependencies.rbac import require_roles
from app.models.user import User
from app.services.dashboard_service import (
    get_hiring_manager_dashboard_data,
    get_hr_dashboard_data,
    get_interviewer_dashboard_data,
)

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

templates = Jinja2Templates(
    directory=str(Path(__file__).resolve().parent.parent / "templates")
)


@router.get("")
async def dashboard_redirect(
    request: Request,
    user: User = Depends(get_current_user),
):
    if user.role in ["System Admin", "HR Recruiter"]:
        return RedirectResponse(url="/dashboard/hr", status_code=302)
    elif user.role == "Hiring Manager":
        return RedirectResponse(url="/dashboard/hiring-manager", status_code=302)
    elif user.role == "Interviewer":
        return RedirectResponse(url="/dashboard/interviewer", status_code=302)
    else:
        return RedirectResponse(url="/dashboard/interviewer", status_code=302)


@router.get("/hr")
async def hr_dashboard(
    request: Request,
    user: User = Depends(require_roles(["System Admin", "HR Recruiter"])),
    db: AsyncSession = Depends(get_db),
):
    data = await get_hr_dashboard_data(db)

    return templates.TemplateResponse(
        request,
        "dashboard/hr_dashboard.html",
        context={
            "user": user,
            "metrics": data["metrics"],
            "pipeline_stages": data["pipeline_stages"],
            "pipeline_total": data["pipeline_total"],
            "audit_logs": data["audit_logs"],
        },
    )


@router.get("/hiring-manager")
async def hiring_manager_dashboard(
    request: Request,
    user: User = Depends(require_roles(["System Admin", "HR Recruiter", "Hiring Manager"])),
    db: AsyncSession = Depends(get_db),
):
    data = await get_hiring_manager_dashboard_data(db, user.id)

    return templates.TemplateResponse(
        request,
        "dashboard/hm_dashboard.html",
        context={
            "user": user,
            "metrics": data["metrics"],
            "jobs": data["jobs"],
            "recent_activity": data["recent_activity"],
        },
    )


@router.get("/interviewer")
async def interviewer_dashboard(
    request: Request,
    user: User = Depends(require_roles(["System Admin", "HR Recruiter", "Hiring Manager", "Interviewer"])),
    db: AsyncSession = Depends(get_db),
):
    data = await get_interviewer_dashboard_data(db, user.id)

    return templates.TemplateResponse(
        request,
        "dashboard/interviewer_dashboard.html",
        context={
            "user": user,
            "stats": data["stats"],
            "upcoming_assignments": data["upcoming_assignments"],
            "pending_feedback_assignments": data["pending_feedback_assignments"],
            "recent_feedback": data["recent_feedback"],
        },
    )