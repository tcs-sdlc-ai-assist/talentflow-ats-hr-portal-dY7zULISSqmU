from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, Form, Query, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import UserRole
from app.core.database import get_db
from app.dependencies.auth import get_current_user
from app.models.user import User
from app.services.audit_service import log_action
from app.services.job_service import (
    change_job_status,
    create_job,
    edit_job,
    get_job,
    get_job_application_count,
    get_jobs,
    validate_job_data,
)

router = APIRouter(prefix="/jobs", tags=["jobs"])

templates = Jinja2Templates(
    directory=str(Path(__file__).resolve().parent.parent / "templates")
)


@router.get("")
async def job_list(
    request: Request,
    search: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    filters = {}
    if search and search.strip():
        filters["search"] = search.strip()
    if status and status.strip():
        filters["status"] = status.strip()

    if user.role == UserRole.HIRING_MANAGER:
        filters["owner_id"] = user.id

    jobs = await get_jobs(db, filters=filters if filters else None)

    return templates.TemplateResponse(
        request,
        "jobs/job_list.html",
        context={
            "user": user,
            "jobs": jobs,
            "search": search or "",
            "status_filter": status or "",
        },
    )


@router.get("/create")
async def job_create_form(
    request: Request,
    user: User = Depends(get_current_user),
):
    if user.role not in [UserRole.SYSTEM_ADMIN, UserRole.HR_RECRUITER, UserRole.HIRING_MANAGER]:
        return RedirectResponse(url="/jobs", status_code=302)

    return templates.TemplateResponse(
        request,
        "jobs/job_form.html",
        context={
            "user": user,
            "job": None,
            "form_data": None,
            "errors": None,
        },
    )


@router.post("/create")
async def job_create_submit(
    request: Request,
    title: str = Form(""),
    department: str = Form(""),
    location: str = Form(""),
    job_type: str = Form(""),
    salary_min: Optional[str] = Form(None),
    salary_max: Optional[str] = Form(None),
    description: str = Form(""),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if user.role not in [UserRole.SYSTEM_ADMIN, UserRole.HR_RECRUITER, UserRole.HIRING_MANAGER]:
        return RedirectResponse(url="/jobs", status_code=302)

    parsed_salary_min = None
    parsed_salary_max = None
    if salary_min and salary_min.strip():
        try:
            parsed_salary_min = int(salary_min.strip())
        except (ValueError, TypeError):
            pass
    if salary_max and salary_max.strip():
        try:
            parsed_salary_max = int(salary_max.strip())
        except (ValueError, TypeError):
            pass

    data = {
        "title": title,
        "department": department,
        "location": location,
        "job_type": job_type,
        "salary_min": parsed_salary_min,
        "salary_max": parsed_salary_max,
        "description": description,
    }

    errors = await validate_job_data(data)
    if errors:
        return templates.TemplateResponse(
            request,
            "jobs/job_form.html",
            context={
                "user": user,
                "job": None,
                "form_data": data,
                "errors": errors,
            },
            status_code=400,
        )

    job = await create_job(db=db, data=data, owner_id=user.id)

    await log_action(
        db=db,
        user_id=user.id,
        username=user.username,
        action="Job Created",
        details=f"Job '{job.title}' (ID: {job.id}) created with status '{job.status}'",
    )

    return RedirectResponse(url=f"/jobs/{job.id}", status_code=302)


@router.get("/{job_id}")
async def job_detail(
    request: Request,
    job_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    job = await get_job(db, job_id)
    if job is None:
        return RedirectResponse(url="/jobs", status_code=302)

    if user.role == UserRole.HIRING_MANAGER and job.owner_id != user.id:
        if user.role not in [UserRole.SYSTEM_ADMIN, UserRole.HR_RECRUITER]:
            pass

    application_count = await get_job_application_count(db, job_id)

    creator = job.owner if job.owner else None
    hiring_manager = job.owner if job.owner else None

    return templates.TemplateResponse(
        request,
        "jobs/job_detail.html",
        context={
            "user": user,
            "job": job,
            "application_count": application_count,
            "creator": creator,
            "hiring_manager": hiring_manager,
        },
    )


@router.get("/{job_id}/edit")
async def job_edit_form(
    request: Request,
    job_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if user.role not in [UserRole.SYSTEM_ADMIN, UserRole.HR_RECRUITER, UserRole.HIRING_MANAGER]:
        return RedirectResponse(url=f"/jobs/{job_id}", status_code=302)

    job = await get_job(db, job_id)
    if job is None:
        return RedirectResponse(url="/jobs", status_code=302)

    if user.role == UserRole.HIRING_MANAGER and job.owner_id != user.id:
        return RedirectResponse(url=f"/jobs/{job_id}", status_code=302)

    return templates.TemplateResponse(
        request,
        "jobs/job_form.html",
        context={
            "user": user,
            "job": job,
            "form_data": None,
            "errors": None,
        },
    )


@router.post("/{job_id}/edit")
async def job_edit_submit(
    request: Request,
    job_id: str,
    title: str = Form(""),
    department: str = Form(""),
    location: str = Form(""),
    job_type: str = Form(""),
    salary_min: Optional[str] = Form(None),
    salary_max: Optional[str] = Form(None),
    description: str = Form(""),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if user.role not in [UserRole.SYSTEM_ADMIN, UserRole.HR_RECRUITER, UserRole.HIRING_MANAGER]:
        return RedirectResponse(url=f"/jobs/{job_id}", status_code=302)

    job = await get_job(db, job_id)
    if job is None:
        return RedirectResponse(url="/jobs", status_code=302)

    if user.role == UserRole.HIRING_MANAGER and job.owner_id != user.id:
        return RedirectResponse(url=f"/jobs/{job_id}", status_code=302)

    parsed_salary_min = None
    parsed_salary_max = None
    if salary_min and salary_min.strip():
        try:
            parsed_salary_min = int(salary_min.strip())
        except (ValueError, TypeError):
            pass
    if salary_max and salary_max.strip():
        try:
            parsed_salary_max = int(salary_max.strip())
        except (ValueError, TypeError):
            pass

    data = {
        "title": title,
        "department": department,
        "location": location,
        "job_type": job_type,
        "salary_min": parsed_salary_min,
        "salary_max": parsed_salary_max,
        "description": description,
    }

    errors = await validate_job_data(data)
    if errors:
        return templates.TemplateResponse(
            request,
            "jobs/job_form.html",
            context={
                "user": user,
                "job": job,
                "form_data": data,
                "errors": errors,
            },
            status_code=400,
        )

    updated_job = await edit_job(db=db, job_id=job_id, data=data, user=user)
    if updated_job is None:
        return templates.TemplateResponse(
            request,
            "jobs/job_form.html",
            context={
                "user": user,
                "job": job,
                "form_data": data,
                "errors": ["You do not have permission to edit this job."],
            },
            status_code=403,
        )

    await log_action(
        db=db,
        user_id=user.id,
        username=user.username,
        action="Job Updated",
        details=f"Job '{updated_job.title}' (ID: {updated_job.id}) updated",
    )

    return RedirectResponse(url=f"/jobs/{job_id}", status_code=302)


@router.post("/{job_id}/status")
async def job_change_status(
    request: Request,
    job_id: str,
    status: str = Form(""),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if user.role not in [UserRole.SYSTEM_ADMIN, UserRole.HR_RECRUITER, UserRole.HIRING_MANAGER]:
        return RedirectResponse(url=f"/jobs/{job_id}", status_code=302)

    job = await get_job(db, job_id)
    if job is None:
        return RedirectResponse(url="/jobs", status_code=302)

    old_status = job.status

    updated_job = await change_job_status(
        db=db,
        job_id=job_id,
        new_status=status,
        user=user,
    )

    if updated_job is None:
        return RedirectResponse(url=f"/jobs/{job_id}", status_code=302)

    await log_action(
        db=db,
        user_id=user.id,
        username=user.username,
        action="Job Status Changed",
        details=f"Job '{updated_job.title}' (ID: {updated_job.id}) status changed from '{old_status}' to '{updated_job.status}'",
    )

    return RedirectResponse(url=f"/jobs/{job_id}", status_code=302)