from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, Form, Query, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.dependencies.auth import get_current_user
from app.models.user import User
from app.services.application_service import (
    change_status,
    create_application,
    get_application_by_id,
    get_applications,
    get_pipeline_data,
    get_pipeline_stats,
)
from app.services.audit_service import log_action
from app.services.candidate_service import get_candidates
from app.services.job_service import get_job, get_jobs

router = APIRouter(tags=["applications"])

templates = Jinja2Templates(
    directory=str(Path(__file__).resolve().parent.parent / "templates")
)


@router.get("/applications")
async def application_list(
    request: Request,
    status: Optional[str] = Query(None),
    job_id: Optional[str] = Query(None),
    candidate_id: Optional[str] = Query(None),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    filters = {}
    if status:
        filters["status"] = status
    if job_id:
        filters["job_id"] = job_id
    if candidate_id:
        filters["candidate_id"] = candidate_id

    applications = await get_applications(db, filters=filters if filters else None)

    return templates.TemplateResponse(
        request,
        "applications/application_list.html",
        context={
            "user": user,
            "applications": applications,
            "status_filter": status,
        },
    )


@router.get("/applications/create")
async def application_create_form(
    request: Request,
    job_id: Optional[str] = Query(None),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if user.role not in ["System Admin", "HR Recruiter", "Hiring Manager"]:
        return RedirectResponse(url="/applications", status_code=302)

    candidates_list = await get_candidates(db)
    jobs_list = await get_jobs(db)

    form_data = None
    if job_id:
        form_data = {"job_id": job_id, "candidate_id": None}

    return templates.TemplateResponse(
        request,
        "applications/application_form.html",
        context={
            "user": user,
            "candidates": candidates_list,
            "jobs": jobs_list,
            "errors": None,
            "form_data": form_data,
        },
    )


@router.post("/applications/create")
async def application_create_submit(
    request: Request,
    candidate_id: str = Form(...),
    job_id: str = Form(...),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if user.role not in ["System Admin", "HR Recruiter", "Hiring Manager"]:
        return RedirectResponse(url="/applications", status_code=302)

    errors = []
    if not candidate_id:
        errors.append("Candidate is required.")
    if not job_id:
        errors.append("Job is required.")

    if errors:
        candidates_list = await get_candidates(db)
        jobs_list = await get_jobs(db)
        return templates.TemplateResponse(
            request,
            "applications/application_form.html",
            context={
                "user": user,
                "candidates": candidates_list,
                "jobs": jobs_list,
                "errors": errors,
                "form_data": {"candidate_id": candidate_id, "job_id": job_id},
            },
            status_code=400,
        )

    try:
        application = await create_application(
            db=db,
            candidate_id=candidate_id,
            job_id=job_id,
        )

        await log_action(
            db=db,
            user_id=user.id,
            username=user.username,
            action="Application Created",
            details=f"Application created by '{user.username}' for candidate {candidate_id} on job {job_id}",
        )

        return RedirectResponse(
            url=f"/applications/{application.id}", status_code=302
        )
    except ValueError as e:
        candidates_list = await get_candidates(db)
        jobs_list = await get_jobs(db)
        return templates.TemplateResponse(
            request,
            "applications/application_form.html",
            context={
                "user": user,
                "candidates": candidates_list,
                "jobs": jobs_list,
                "errors": [str(e)],
                "form_data": {"candidate_id": candidate_id, "job_id": job_id},
            },
            status_code=400,
        )


@router.get("/applications/{application_id}")
async def application_detail(
    request: Request,
    application_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    application = await get_application_by_id(db, application_id)
    if application is None:
        return RedirectResponse(url="/applications", status_code=302)

    interviews = []
    if application.interview_assignments:
        from datetime import datetime

        for assignment in application.interview_assignments:
            has_feedback = bool(assignment.feedback and len(assignment.feedback) > 0)
            now = datetime.utcnow()
            is_completed = (
                assignment.scheduled_time is not None
                and assignment.scheduled_time < now
            )
            interview_status = "Completed" if is_completed else "Scheduled"

            interviews.append(
                {
                    "id": assignment.id,
                    "interviewer": assignment.interviewer,
                    "scheduled_at": assignment.scheduled_time,
                    "status": interview_status,
                    "feedback_submitted": has_feedback,
                }
            )

    return templates.TemplateResponse(
        request,
        "applications/application_detail.html",
        context={
            "user": user,
            "application": application,
            "interviews": interviews,
        },
    )


@router.post("/applications/{application_id}/status")
async def application_change_status(
    request: Request,
    application_id: str,
    status: str = Form(...),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if user.role not in ["System Admin", "HR Recruiter", "Hiring Manager"]:
        return RedirectResponse(
            url=f"/applications/{application_id}", status_code=302
        )

    try:
        await change_status(
            db=db,
            application_id=application_id,
            new_status=status,
            user=user,
        )
        return RedirectResponse(
            url=f"/applications/{application_id}", status_code=302
        )
    except ValueError:
        return RedirectResponse(
            url=f"/applications/{application_id}", status_code=302
        )


@router.get("/jobs/{job_id}/pipeline")
async def job_pipeline_view(
    request: Request,
    job_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    job = await get_job(db, job_id)
    if job is None:
        return RedirectResponse(url="/jobs", status_code=302)

    pipeline = await get_pipeline_data(db, job_id=job_id)
    stats = await get_pipeline_stats(db, job_id=job_id)

    return templates.TemplateResponse(
        request,
        "applications/pipeline.html",
        context={
            "user": user,
            "job": job,
            "pipeline": pipeline,
            "stats": stats,
        },
    )