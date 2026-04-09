from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.application import Application
from app.models.candidate import Candidate
from app.models.job import Job
from app.models.user import User
from app.services.audit_service import log_audit_action

ALLOWED_TRANSITIONS: dict[str, list[str]] = {
    "Applied": ["Screening", "Rejected"],
    "Screening": ["Interviewing", "Rejected"],
    "Interviewing": ["Offered", "Rejected"],
    "Offered": ["Hired", "Rejected"],
    "Hired": [],
    "Rejected": [],
}

ALL_STAGES = ["Applied", "Screening", "Interviewing", "Offered", "Hired", "Rejected"]


async def create_application(
    db: AsyncSession,
    candidate_id: str,
    job_id: str,
) -> Application:
    candidate_result = await db.execute(
        select(Candidate).where(Candidate.id == candidate_id)
    )
    candidate = candidate_result.scalar_one_or_none()
    if candidate is None:
        raise ValueError("Candidate not found.")

    job_result = await db.execute(
        select(Job).where(Job.id == job_id)
    )
    job = job_result.scalar_one_or_none()
    if job is None:
        raise ValueError("Job not found.")

    existing_result = await db.execute(
        select(Application).where(
            Application.candidate_id == candidate_id,
            Application.job_id == job_id,
        )
    )
    existing = existing_result.scalar_one_or_none()
    if existing is not None:
        raise ValueError("An application already exists for this candidate and job.")

    application = Application(
        candidate_id=candidate_id,
        job_id=job_id,
        status="Applied",
        applied_at=datetime.utcnow(),
    )
    db.add(application)
    await db.flush()
    await db.refresh(application)

    await log_audit_action(
        db=db,
        user_id=None,
        username=None,
        action="Application Created",
        details=f"Application created for candidate {candidate_id} on job {job_id}",
    )

    return application


async def change_status(
    db: AsyncSession,
    application_id: str,
    new_status: str,
    user: User,
) -> Application:
    result = await db.execute(
        select(Application)
        .where(Application.id == application_id)
        .options(
            selectinload(Application.candidate),
            selectinload(Application.job),
        )
    )
    application = result.scalar_one_or_none()
    if application is None:
        raise ValueError("Application not found.")

    current_status = application.status
    allowed = ALLOWED_TRANSITIONS.get(current_status, [])
    if new_status not in allowed:
        raise ValueError(
            f"Invalid status transition from '{current_status}' to '{new_status}'. "
            f"Allowed transitions: {', '.join(allowed) if allowed else 'none'}."
        )

    old_status = application.status
    application.status = new_status
    application.updated_at = datetime.utcnow()
    await db.flush()
    await db.refresh(application)

    await log_audit_action(
        db=db,
        user_id=user.id,
        username=user.username,
        action="Application Status Changed",
        details=f"Application {application_id} status changed from '{old_status}' to '{new_status}'",
    )

    return application


async def get_applications(
    db: AsyncSession,
    filters: dict[str, Any] | None = None,
) -> list[Application]:
    query = (
        select(Application)
        .options(
            selectinload(Application.candidate),
            selectinload(Application.job),
        )
        .order_by(Application.created_at.desc())
    )

    if filters:
        if filters.get("status"):
            query = query.where(Application.status == filters["status"])
        if filters.get("job_id"):
            query = query.where(Application.job_id == filters["job_id"])
        if filters.get("candidate_id"):
            query = query.where(Application.candidate_id == filters["candidate_id"])

    result = await db.execute(query)
    return list(result.scalars().all())


async def get_applications_by_job(
    db: AsyncSession,
    job_id: str,
) -> list[Application]:
    result = await db.execute(
        select(Application)
        .where(Application.job_id == job_id)
        .options(
            selectinload(Application.candidate),
            selectinload(Application.job),
        )
        .order_by(Application.created_at.desc())
    )
    return list(result.scalars().all())


async def get_pipeline_data(
    db: AsyncSession,
    job_id: str | None = None,
) -> dict[str, list[dict[str, Any]]]:
    pipeline: dict[str, list[dict[str, Any]]] = {stage: [] for stage in ALL_STAGES}

    query = (
        select(Application)
        .options(
            selectinload(Application.candidate),
            selectinload(Application.job),
        )
        .order_by(Application.created_at.asc())
    )

    if job_id:
        query = query.where(Application.job_id == job_id)

    result = await db.execute(query)
    applications = result.scalars().all()

    for app in applications:
        candidate_name = ""
        candidate_email = ""
        if app.candidate:
            candidate_name = f"{app.candidate.first_name} {app.candidate.last_name}"
            candidate_email = app.candidate.email or ""

        job_title = ""
        if app.job:
            job_title = app.job.title or ""

        entry = {
            "id": app.id,
            "candidate_id": app.candidate_id,
            "candidate_name": candidate_name,
            "candidate_email": candidate_email,
            "job_id": app.job_id,
            "job_title": job_title,
            "status": app.status,
            "applied_at": app.applied_at,
            "created_at": app.created_at,
        }

        stage = app.status if app.status in ALL_STAGES else "Applied"
        pipeline[stage].append(entry)

    return pipeline


async def get_pipeline_stats(
    db: AsyncSession,
    job_id: str | None = None,
) -> dict[str, int]:
    stats: dict[str, int] = {}

    for stage in ALL_STAGES:
        query = select(func.count(Application.id)).where(Application.status == stage)
        if job_id:
            query = query.where(Application.job_id == job_id)
        result = await db.execute(query)
        stats[stage] = result.scalar() or 0

    return stats


async def get_application_by_id(
    db: AsyncSession,
    application_id: str,
) -> Application | None:
    result = await db.execute(
        select(Application)
        .where(Application.id == application_id)
        .options(
            selectinload(Application.candidate),
            selectinload(Application.job),
            selectinload(Application.interview_assignments),
        )
    )
    return result.scalar_one_or_none()


async def get_application_count_by_job(
    db: AsyncSession,
    job_id: str,
) -> int:
    result = await db.execute(
        select(func.count(Application.id)).where(Application.job_id == job_id)
    )
    return result.scalar() or 0