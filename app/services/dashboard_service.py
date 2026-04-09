from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.application import Application
from app.models.audit_log import AuditLog
from app.models.candidate import Candidate
from app.models.interview import InterviewAssignment, InterviewFeedback
from app.models.job import Job


async def get_hr_dashboard_data(db: AsyncSession) -> dict[str, Any]:
    """Return system-wide metrics for the HR/Admin dashboard."""

    # Total jobs count
    jobs_result = await db.execute(select(func.count(Job.id)))
    total_jobs = jobs_result.scalar() or 0

    # Open (published) jobs count
    open_jobs_result = await db.execute(
        select(func.count(Job.id)).where(Job.status == "Published")
    )
    open_jobs = open_jobs_result.scalar() or 0

    # Total candidates count
    candidates_result = await db.execute(select(func.count(Candidate.id)))
    total_candidates = candidates_result.scalar() or 0

    # Total applications count
    applications_result = await db.execute(select(func.count(Application.id)))
    total_applications = applications_result.scalar() or 0

    # Total interviews count
    interviews_result = await db.execute(select(func.count(InterviewAssignment.id)))
    total_interviews = interviews_result.scalar() or 0

    # Pipeline stage distribution
    pipeline_stages_list = []
    pipeline_total = 0
    stage_names = ["Applied", "Screening", "Interviewing", "Offered", "Hired", "Rejected"]
    for stage_name in stage_names:
        count_result = await db.execute(
            select(func.count(Application.id)).where(Application.status == stage_name)
        )
        count = count_result.scalar() or 0
        pipeline_stages_list.append({"name": stage_name, "count": count})
        pipeline_total += count

    # Recent audit logs (last 20)
    audit_logs_result = await db.execute(
        select(AuditLog)
        .options(selectinload(AuditLog.actor))
        .order_by(AuditLog.created_at.desc())
        .limit(20)
    )
    audit_logs = list(audit_logs_result.scalars().all())

    # Enrich audit logs with user_name for template convenience
    enriched_audit_logs = []
    for log in audit_logs:
        enriched_log = log
        enriched_log.user_name = log.username or (
            log.actor.username if log.actor else "System"
        )
        enriched_audit_logs.append(enriched_log)

    metrics = {
        "open_jobs": total_jobs,
        "published_jobs": open_jobs,
        "candidates": total_candidates,
        "applications": total_applications,
        "interviews": total_interviews,
    }

    return {
        "metrics": metrics,
        "pipeline_stages": pipeline_stages_list,
        "pipeline_total": pipeline_total,
        "audit_logs": enriched_audit_logs,
    }


async def get_hiring_manager_dashboard_data(
    db: AsyncSession, user_id: str
) -> dict[str, Any]:
    """Return dashboard data scoped to a specific hiring manager."""

    # Jobs owned by this hiring manager
    jobs_result = await db.execute(
        select(Job)
        .where(Job.owner_id == user_id)
        .options(selectinload(Job.applications))
        .order_by(Job.created_at.desc())
    )
    jobs = list(jobs_result.scalars().all())

    total_jobs = len(jobs)
    published_jobs = sum(1 for j in jobs if j.status == "Published")

    # Total applications across this manager's jobs
    job_ids = [j.id for j in jobs]
    total_applications = 0
    if job_ids:
        apps_count_result = await db.execute(
            select(func.count(Application.id)).where(Application.job_id.in_(job_ids))
        )
        total_applications = apps_count_result.scalar() or 0

    # Pending interviews for this manager's jobs
    pending_interviews = 0
    if job_ids:
        pending_result = await db.execute(
            select(func.count(InterviewAssignment.id))
            .join(Application, InterviewAssignment.application_id == Application.id)
            .where(Application.job_id.in_(job_ids))
            .where(
                InterviewAssignment.scheduled_time >= datetime.utcnow()
            )
        )
        pending_interviews = pending_result.scalar() or 0

    # Enrich jobs with application_count and pending_interview_count
    enriched_jobs = []
    for job in jobs:
        app_count = len(job.applications) if job.applications else 0
        job.application_count = app_count

        if job.id in job_ids:
            pending_count_result = await db.execute(
                select(func.count(InterviewAssignment.id))
                .join(Application, InterviewAssignment.application_id == Application.id)
                .where(Application.job_id == job.id)
                .where(
                    InterviewAssignment.scheduled_time >= datetime.utcnow()
                )
            )
            job.pending_interview_count = pending_count_result.scalar() or 0
        else:
            job.pending_interview_count = 0

        enriched_jobs.append(job)

    # Recent activity (audit logs related to this user)
    activity_result = await db.execute(
        select(AuditLog)
        .options(selectinload(AuditLog.actor))
        .where(AuditLog.user_id == user_id)
        .order_by(AuditLog.created_at.desc())
        .limit(10)
    )
    recent_activity = list(activity_result.scalars().all())

    metrics = {
        "total_jobs": total_jobs,
        "published_jobs": published_jobs,
        "total_applications": total_applications,
        "pending_interviews": pending_interviews,
    }

    return {
        "metrics": metrics,
        "jobs": enriched_jobs,
        "recent_activity": recent_activity,
    }


async def get_interviewer_dashboard_data(
    db: AsyncSession, user_id: str
) -> dict[str, Any]:
    """Return dashboard data for an interviewer: assignments, feedback status."""

    now = datetime.utcnow()

    # All assignments for this interviewer
    assignments_result = await db.execute(
        select(InterviewAssignment)
        .where(InterviewAssignment.interviewer_id == user_id)
        .options(
            selectinload(InterviewAssignment.application).selectinload(Application.candidate),
            selectinload(InterviewAssignment.application).selectinload(Application.job),
            selectinload(InterviewAssignment.feedback),
        )
        .order_by(InterviewAssignment.scheduled_time.desc())
    )
    all_assignments = list(assignments_result.scalars().all())

    total_assignments = len(all_assignments)

    # Upcoming interviews (scheduled_time >= now)
    upcoming_assignments = [
        a for a in all_assignments if a.scheduled_time and a.scheduled_time >= now
    ]
    upcoming_interviews_count = len(upcoming_assignments)

    # Completed interviews (scheduled_time < now)
    past_assignments = [
        a for a in all_assignments if a.scheduled_time and a.scheduled_time < now
    ]
    completed_interviews_count = len(past_assignments)

    # Assignments with feedback already submitted
    assignments_with_feedback = set()
    for assignment in all_assignments:
        if assignment.feedback and len(assignment.feedback) > 0:
            assignments_with_feedback.add(assignment.id)

    # Pending feedback: past assignments without feedback
    pending_feedback_assignments_list = []
    for assignment in past_assignments:
        if assignment.id not in assignments_with_feedback:
            enriched = _enrich_assignment(assignment)
            pending_feedback_assignments_list.append(enriched)

    pending_feedback_count = len(pending_feedback_assignments_list)

    # Enrich upcoming assignments for display
    enriched_upcoming = []
    for assignment in upcoming_assignments:
        enriched = _enrich_assignment(assignment)
        enriched_upcoming.append(enriched)

    # Recent feedback submitted by this user
    recent_feedback_result = await db.execute(
        select(InterviewFeedback)
        .where(InterviewFeedback.submitted_by == user_id)
        .options(
            selectinload(InterviewFeedback.assignment)
            .selectinload(InterviewAssignment.application)
            .selectinload(Application.candidate),
            selectinload(InterviewFeedback.assignment)
            .selectinload(InterviewAssignment.application)
            .selectinload(Application.job),
        )
        .order_by(InterviewFeedback.submitted_at.desc())
        .limit(10)
    )
    recent_feedback_rows = list(recent_feedback_result.scalars().all())

    recent_feedback = []
    for fb in recent_feedback_rows:
        candidate_name = "Unknown"
        job_title = "Unknown"
        if fb.assignment and fb.assignment.application:
            app = fb.assignment.application
            if app.candidate:
                candidate_name = (
                    f"{app.candidate.first_name} {app.candidate.last_name}"
                )
            if app.job:
                job_title = app.job.title

        recent_feedback.append(
            {
                "candidate_name": candidate_name,
                "job_title": job_title,
                "rating": fb.rating,
                "submitted_at": (
                    fb.submitted_at.strftime("%b %d, %Y") if fb.submitted_at else ""
                ),
            }
        )

    stats = {
        "total_assignments": total_assignments,
        "upcoming_interviews": upcoming_interviews_count,
        "completed_interviews": completed_interviews_count,
        "pending_feedback": pending_feedback_count,
    }

    return {
        "stats": stats,
        "upcoming_assignments": enriched_upcoming,
        "pending_feedback_assignments": pending_feedback_assignments_list,
        "recent_feedback": recent_feedback,
    }


def _enrich_assignment(assignment: InterviewAssignment) -> dict[str, Any]:
    """Convert an InterviewAssignment into a dict suitable for template rendering."""
    candidate_name = "Unknown"
    candidate_email = ""
    job_title = "Unknown"

    if assignment.application:
        app = assignment.application
        if app.candidate:
            candidate_name = f"{app.candidate.first_name} {app.candidate.last_name}"
            candidate_email = app.candidate.email or ""
        if app.job:
            job_title = app.job.title or "Unknown"

    has_feedback = bool(assignment.feedback and len(assignment.feedback) > 0)

    scheduled_date = ""
    scheduled_time = ""
    if assignment.scheduled_time:
        scheduled_date = assignment.scheduled_time.strftime("%b %d, %Y")
        scheduled_time = assignment.scheduled_time.strftime("%I:%M %p")

    return {
        "id": assignment.id,
        "candidate_name": candidate_name,
        "candidate_email": candidate_email,
        "job_title": job_title,
        "scheduled_date": scheduled_date,
        "scheduled_time": scheduled_time,
        "scheduled_at": assignment.scheduled_time,
        "status": "Completed" if (
            assignment.scheduled_time and assignment.scheduled_time < datetime.utcnow()
        ) else "Scheduled",
        "feedback_submitted": has_feedback,
    }