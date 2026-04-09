from datetime import datetime
from typing import Optional

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.job import Job
from app.models.user import User
from app.models.application import Application
from app.core.constants import UserRole, JobStatus


ALLOWED_STATUSES = JobStatus.ALL


async def create_job(
    db: AsyncSession,
    data: dict,
    owner_id: str,
) -> Job:
    job = Job(
        title=data["title"],
        department=data["department"],
        location=data["location"],
        job_type=data["job_type"],
        salary_min=data.get("salary_min"),
        salary_max=data.get("salary_max"),
        description=data["description"],
        status=data.get("status", JobStatus.DRAFT),
        owner_id=owner_id,
    )
    db.add(job)
    await db.flush()

    from app.services.audit_service import log_audit

    await log_audit(
        db=db,
        user_id=owner_id,
        action="Job Created",
        details=f"Job '{job.title}' created with status '{job.status}'",
    )

    return job


async def edit_job(
    db: AsyncSession,
    job_id: str,
    data: dict,
    user: User,
) -> Optional[Job]:
    result = await db.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one_or_none()
    if job is None:
        return None

    if user.role not in [UserRole.SYSTEM_ADMIN, UserRole.HR_RECRUITER]:
        if user.role == UserRole.HIRING_MANAGER and job.owner_id != user.id:
            return None
        elif user.role not in [UserRole.HIRING_MANAGER]:
            return None

    if "title" in data and data["title"]:
        job.title = data["title"]
    if "department" in data and data["department"]:
        job.department = data["department"]
    if "location" in data and data["location"]:
        job.location = data["location"]
    if "job_type" in data and data["job_type"]:
        job.job_type = data["job_type"]
    if "salary_min" in data:
        job.salary_min = data["salary_min"]
    if "salary_max" in data:
        job.salary_max = data["salary_max"]
    if "description" in data and data["description"]:
        job.description = data["description"]
    if "status" in data and data["status"] in ALLOWED_STATUSES:
        job.status = data["status"]

    job.updated_at = datetime.utcnow()
    await db.flush()

    from app.services.audit_service import log_audit

    await log_audit(
        db=db,
        user_id=user.id,
        action="Job Updated",
        details=f"Job '{job.title}' (ID: {job.id}) updated",
    )

    return job


async def change_job_status(
    db: AsyncSession,
    job_id: str,
    new_status: str,
    user: User,
) -> Optional[Job]:
    if new_status not in ALLOWED_STATUSES:
        return None

    result = await db.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one_or_none()
    if job is None:
        return None

    if user.role not in [UserRole.SYSTEM_ADMIN, UserRole.HR_RECRUITER]:
        if user.role == UserRole.HIRING_MANAGER and job.owner_id != user.id:
            return None
        elif user.role not in [UserRole.HIRING_MANAGER]:
            return None

    old_status = job.status
    job.status = new_status
    job.updated_at = datetime.utcnow()
    await db.flush()

    from app.services.audit_service import log_audit

    await log_audit(
        db=db,
        user_id=user.id,
        action="Job Status Changed",
        details=f"Job '{job.title}' status changed from '{old_status}' to '{new_status}'",
    )

    return job


async def get_jobs(
    db: AsyncSession,
    filters: Optional[dict] = None,
) -> list[Job]:
    stmt = select(Job).order_by(Job.created_at.desc())

    if filters:
        if filters.get("status"):
            stmt = stmt.where(Job.status == filters["status"])
        if filters.get("search"):
            search_term = f"%{filters['search']}%"
            stmt = stmt.where(
                (Job.title.ilike(search_term))
                | (Job.department.ilike(search_term))
                | (Job.location.ilike(search_term))
            )
        if filters.get("department"):
            stmt = stmt.where(Job.department == filters["department"])
        if filters.get("owner_id"):
            stmt = stmt.where(Job.owner_id == filters["owner_id"])

    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_job(
    db: AsyncSession,
    job_id: str,
) -> Optional[Job]:
    result = await db.execute(select(Job).where(Job.id == job_id))
    return result.scalar_one_or_none()


async def get_published_jobs(
    db: AsyncSession,
) -> list[Job]:
    stmt = (
        select(Job)
        .where(Job.status == JobStatus.PUBLISHED)
        .order_by(Job.created_at.desc())
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_jobs_by_owner(
    db: AsyncSession,
    owner_id: str,
) -> list[Job]:
    stmt = (
        select(Job)
        .where(Job.owner_id == owner_id)
        .order_by(Job.created_at.desc())
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_job_application_count(
    db: AsyncSession,
    job_id: str,
) -> int:
    stmt = select(func.count(Application.id)).where(Application.job_id == job_id)
    result = await db.execute(stmt)
    return result.scalar_one() or 0


async def get_job_metrics_for_owner(
    db: AsyncSession,
    owner_id: str,
) -> dict:
    jobs = await get_jobs_by_owner(db, owner_id)

    total_jobs = len(jobs)
    published_jobs = sum(1 for j in jobs if j.status == JobStatus.PUBLISHED)

    job_ids = [j.id for j in jobs]

    total_applications = 0
    if job_ids:
        stmt = select(func.count(Application.id)).where(
            Application.job_id.in_(job_ids)
        )
        result = await db.execute(stmt)
        total_applications = result.scalar_one() or 0

    from app.models.interview import InterviewAssignment

    pending_interviews = 0
    if job_ids:
        stmt = (
            select(func.count(InterviewAssignment.id))
            .join(Application, InterviewAssignment.application_id == Application.id)
            .where(Application.job_id.in_(job_ids))
        )
        result = await db.execute(stmt)
        pending_interviews = result.scalar_one() or 0

    return {
        "total_jobs": total_jobs,
        "published_jobs": published_jobs,
        "total_applications": total_applications,
        "pending_interviews": pending_interviews,
    }


async def validate_job_data(data: dict) -> list[str]:
    errors = []
    if not data.get("title", "").strip():
        errors.append("Job title is required.")
    if not data.get("department", "").strip():
        errors.append("Department is required.")
    if not data.get("location", "").strip():
        errors.append("Location is required.")
    if not data.get("job_type", "").strip():
        errors.append("Employment type is required.")
    if not data.get("description", "").strip():
        errors.append("Job description is required.")

    salary_min = data.get("salary_min")
    salary_max = data.get("salary_max")

    if salary_min is not None and salary_max is not None:
        try:
            s_min = int(salary_min)
            s_max = int(salary_max)
            if s_min < 0:
                errors.append("Minimum salary cannot be negative.")
            if s_max < 0:
                errors.append("Maximum salary cannot be negative.")
            if s_min > s_max:
                errors.append("Minimum salary cannot exceed maximum salary.")
        except (ValueError, TypeError):
            errors.append("Salary values must be valid numbers.")

    return errors