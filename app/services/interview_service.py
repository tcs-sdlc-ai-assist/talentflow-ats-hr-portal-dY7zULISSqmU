from datetime import datetime

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.application import Application
from app.models.candidate import Candidate
from app.models.interview import InterviewAssignment, InterviewFeedback
from app.models.job import Job
from app.models.user import User
from app.services.audit_service import log_audit_action


async def schedule_interview(
    db: AsyncSession,
    application_id: str,
    interviewer_id: str,
    scheduled_time: datetime,
    scheduled_by_user_id: str | None = None,
    scheduled_by_username: str | None = None,
) -> InterviewAssignment:
    result = await db.execute(
        select(Application)
        .where(Application.id == application_id)
        .options(
            selectinload(Application.candidate),
            selectinload(Application.job),
        )
    )
    application = result.scalars().first()
    if application is None:
        raise ValueError("Application not found")

    result = await db.execute(
        select(User).where(User.id == interviewer_id)
    )
    interviewer = result.scalars().first()
    if interviewer is None:
        raise ValueError("Interviewer not found")

    assignment = InterviewAssignment(
        application_id=application_id,
        interviewer_id=interviewer_id,
        scheduled_time=scheduled_time,
    )
    db.add(assignment)
    await db.flush()

    candidate_name = ""
    if application.candidate:
        candidate_name = f"{application.candidate.first_name} {application.candidate.last_name}"

    job_title = ""
    if application.job:
        job_title = application.job.title

    await log_audit_action(
        db=db,
        user_id=scheduled_by_user_id,
        username=scheduled_by_username,
        action="Interview Scheduled",
        details=(
            f"Interview scheduled for candidate '{candidate_name}' "
            f"for job '{job_title}' with interviewer '{interviewer.username}' "
            f"at {scheduled_time.strftime('%Y-%m-%d %H:%M')}"
        ),
    )

    return assignment


async def get_my_interviews(
    db: AsyncSession,
    interviewer_id: str,
) -> list[InterviewAssignment]:
    result = await db.execute(
        select(InterviewAssignment)
        .where(InterviewAssignment.interviewer_id == interviewer_id)
        .options(
            selectinload(InterviewAssignment.application).selectinload(Application.candidate),
            selectinload(InterviewAssignment.application).selectinload(Application.job),
            selectinload(InterviewAssignment.interviewer),
            selectinload(InterviewAssignment.feedback),
        )
        .order_by(InterviewAssignment.scheduled_time.desc())
    )
    return list(result.scalars().all())


async def get_interviews_by_application(
    db: AsyncSession,
    application_id: str,
) -> list[InterviewAssignment]:
    result = await db.execute(
        select(InterviewAssignment)
        .where(InterviewAssignment.application_id == application_id)
        .options(
            selectinload(InterviewAssignment.interviewer),
            selectinload(InterviewAssignment.feedback),
            selectinload(InterviewAssignment.application).selectinload(Application.candidate),
            selectinload(InterviewAssignment.application).selectinload(Application.job),
        )
        .order_by(InterviewAssignment.scheduled_time.desc())
    )
    return list(result.scalars().all())


async def get_all_interviews(
    db: AsyncSession,
    status: str | None = None,
    feedback_filter: str | None = None,
    search: str | None = None,
) -> list[InterviewAssignment]:
    stmt = (
        select(InterviewAssignment)
        .options(
            selectinload(InterviewAssignment.application).selectinload(Application.candidate),
            selectinload(InterviewAssignment.application).selectinload(Application.job),
            selectinload(InterviewAssignment.interviewer),
            selectinload(InterviewAssignment.feedback),
        )
        .order_by(InterviewAssignment.scheduled_time.desc())
    )

    result = await db.execute(stmt)
    assignments = list(result.scalars().all())

    if feedback_filter == "submitted":
        assignments = [a for a in assignments if len(a.feedback) > 0]
    elif feedback_filter == "pending":
        assignments = [a for a in assignments if len(a.feedback) == 0]

    if search:
        search_lower = search.lower()
        filtered = []
        for a in assignments:
            candidate_name = ""
            if a.application and a.application.candidate:
                candidate_name = (
                    f"{a.application.candidate.first_name} {a.application.candidate.last_name}"
                ).lower()
            interviewer_name = ""
            if a.interviewer:
                interviewer_name = a.interviewer.username.lower()
            if search_lower in candidate_name or search_lower in interviewer_name:
                filtered.append(a)
        assignments = filtered

    return assignments


async def get_interview_by_id(
    db: AsyncSession,
    assignment_id: str,
) -> InterviewAssignment | None:
    result = await db.execute(
        select(InterviewAssignment)
        .where(InterviewAssignment.id == assignment_id)
        .options(
            selectinload(InterviewAssignment.application).selectinload(Application.candidate),
            selectinload(InterviewAssignment.application).selectinload(Application.job),
            selectinload(InterviewAssignment.interviewer),
            selectinload(InterviewAssignment.feedback),
        )
    )
    return result.scalars().first()


async def get_pending_feedback(
    db: AsyncSession,
    interviewer_id: str,
) -> list[InterviewAssignment]:
    result = await db.execute(
        select(InterviewAssignment)
        .where(InterviewAssignment.interviewer_id == interviewer_id)
        .options(
            selectinload(InterviewAssignment.application).selectinload(Application.candidate),
            selectinload(InterviewAssignment.application).selectinload(Application.job),
            selectinload(InterviewAssignment.interviewer),
            selectinload(InterviewAssignment.feedback),
        )
        .order_by(InterviewAssignment.scheduled_time.desc())
    )
    assignments = list(result.scalars().all())
    return [a for a in assignments if len(a.feedback) == 0]


def validate_feedback(rating: int, notes: str) -> list[str]:
    errors: list[str] = []
    if not isinstance(rating, int) or rating < 1 or rating > 5:
        errors.append("Rating must be an integer between 1 and 5.")
    if not notes or len(notes.strip()) < 10:
        errors.append("Notes must be at least 10 characters long.")
    return errors


async def submit_feedback(
    db: AsyncSession,
    assignment_id: str,
    rating: int,
    notes: str,
    submitted_by: str,
    submitted_by_username: str | None = None,
) -> InterviewFeedback:
    errors = validate_feedback(rating, notes)
    if errors:
        raise ValueError("; ".join(errors))

    result = await db.execute(
        select(InterviewAssignment)
        .where(InterviewAssignment.id == assignment_id)
        .options(
            selectinload(InterviewAssignment.application).selectinload(Application.candidate),
            selectinload(InterviewAssignment.application).selectinload(Application.job),
            selectinload(InterviewAssignment.feedback),
        )
    )
    assignment = result.scalars().first()
    if assignment is None:
        raise ValueError("Interview assignment not found")

    if len(assignment.feedback) > 0:
        raise ValueError("Feedback has already been submitted for this interview")

    feedback = InterviewFeedback(
        assignment_id=assignment_id,
        rating=rating,
        notes=notes.strip(),
        submitted_by=submitted_by,
    )
    db.add(feedback)
    await db.flush()

    candidate_name = ""
    if assignment.application and assignment.application.candidate:
        candidate_name = (
            f"{assignment.application.candidate.first_name} "
            f"{assignment.application.candidate.last_name}"
        )

    job_title = ""
    if assignment.application and assignment.application.job:
        job_title = assignment.application.job.title

    await log_audit_action(
        db=db,
        user_id=submitted_by,
        username=submitted_by_username,
        action="Feedback Submitted",
        details=(
            f"Feedback submitted for candidate '{candidate_name}' "
            f"for job '{job_title}' — Rating: {rating}/5"
        ),
    )

    return feedback


async def get_interview_stats(db: AsyncSession) -> dict:
    total_result = await db.execute(
        select(func.count(InterviewAssignment.id))
    )
    total = total_result.scalar() or 0

    now = datetime.utcnow()
    scheduled_result = await db.execute(
        select(func.count(InterviewAssignment.id))
        .where(InterviewAssignment.scheduled_time >= now)
    )
    scheduled = scheduled_result.scalar() or 0

    all_result = await db.execute(
        select(InterviewAssignment)
        .options(selectinload(InterviewAssignment.feedback))
    )
    all_assignments = list(all_result.scalars().all())
    pending_feedback = sum(1 for a in all_assignments if len(a.feedback) == 0)

    return {
        "total": total,
        "scheduled": scheduled,
        "pending_feedback": pending_feedback,
    }


async def get_interviewer_stats(db: AsyncSession, interviewer_id: str) -> dict:
    assignments = await get_my_interviews(db, interviewer_id)

    now = datetime.utcnow()
    total_assignments = len(assignments)
    upcoming = sum(1 for a in assignments if a.scheduled_time >= now)
    completed = sum(1 for a in assignments if a.scheduled_time < now)
    pending = sum(1 for a in assignments if len(a.feedback) == 0)

    return {
        "total_assignments": total_assignments,
        "upcoming_interviews": upcoming,
        "completed_interviews": completed,
        "pending_feedback": pending,
    }


async def get_recent_feedback_by_user(
    db: AsyncSession,
    user_id: str,
    limit: int = 10,
) -> list[InterviewFeedback]:
    result = await db.execute(
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
        .limit(limit)
    )
    return list(result.scalars().all())