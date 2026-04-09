from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, Form, Query, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.dependencies.auth import get_current_user
from app.models.user import User
from app.services.audit_service import log_action
from app.services.interview_service import (
    get_all_interviews,
    get_interview_by_id,
    get_interview_stats,
    get_interviewer_stats,
    get_my_interviews,
    get_pending_feedback,
    get_recent_feedback_by_user,
    schedule_interview,
    submit_feedback,
    validate_feedback,
)
from app.services.application_service import get_applications
from app.services.user_service import get_all_users

router = APIRouter(prefix="/interviews", tags=["interviews"])

templates = Jinja2Templates(
    directory=str(Path(__file__).resolve().parent.parent / "templates")
)


@router.get("")
async def interview_list(
    request: Request,
    status: Optional[str] = Query(None),
    feedback: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    stats = await get_interview_stats(db)

    assignments = await get_all_interviews(
        db,
        status=status,
        feedback_filter=feedback,
        search=search,
    )

    enriched_interviews = []
    for assignment in assignments:
        candidate_name = ""
        candidate_email = ""
        job_title = ""
        department = ""
        interviewer_name = ""

        if assignment.application:
            app = assignment.application
            if app.candidate:
                candidate_name = f"{app.candidate.first_name} {app.candidate.last_name}"
                candidate_email = app.candidate.email or ""
            if app.job:
                job_title = app.job.title or ""
                department = app.job.department or ""

        if assignment.interviewer:
            interviewer_name = assignment.interviewer.username

        has_feedback = bool(assignment.feedback and len(assignment.feedback) > 0)

        now = datetime.utcnow()
        if assignment.scheduled_time and assignment.scheduled_time < now:
            interview_status = "Completed"
        else:
            interview_status = "Scheduled"

        enriched_interviews.append(
            type(
                "InterviewView",
                (),
                {
                    "id": assignment.id,
                    "candidate_name": candidate_name,
                    "candidate_email": candidate_email,
                    "job_title": job_title,
                    "department": department,
                    "interviewer_name": interviewer_name,
                    "scheduled_at": assignment.scheduled_time,
                    "status": interview_status,
                    "feedback_submitted": has_feedback,
                    "created_at": assignment.created_at,
                },
            )()
        )

    filters_dict = {
        "status": status or "",
        "feedback": feedback or "",
        "search": search or "",
    }

    return templates.TemplateResponse(
        request,
        "interviews/interview_list.html",
        context={
            "user": user,
            "interviews": enriched_interviews,
            "stats": stats,
            "filters": filters_dict,
        },
    )


@router.get("/my")
async def my_interviews(
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    assignments = await get_my_interviews(db, user.id)

    enriched_interviews = []
    now = datetime.utcnow()
    for assignment in assignments:
        candidate_name = ""
        candidate_email = ""
        job_title = ""

        if assignment.application:
            app = assignment.application
            if app.candidate:
                candidate_name = f"{app.candidate.first_name} {app.candidate.last_name}"
                candidate_email = app.candidate.email or ""
            if app.job:
                job_title = app.job.title or ""

        has_feedback = bool(assignment.feedback and len(assignment.feedback) > 0)

        if assignment.scheduled_time and assignment.scheduled_time < now:
            interview_status = "Completed"
        else:
            interview_status = "Scheduled"

        enriched_interviews.append(
            type(
                "InterviewView",
                (),
                {
                    "id": assignment.id,
                    "candidate_name": candidate_name,
                    "candidate_email": candidate_email,
                    "job_title": job_title,
                    "scheduled_at": assignment.scheduled_time,
                    "status": interview_status,
                    "feedback_submitted": has_feedback,
                },
            )()
        )

    return templates.TemplateResponse(
        request,
        "interviews/my_interviews.html",
        context={
            "user": user,
            "interviews": enriched_interviews,
        },
    )


@router.get("/schedule")
async def schedule_form(
    request: Request,
    application_id: Optional[str] = Query(None),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if user.role not in ["System Admin", "HR Recruiter", "Hiring Manager"]:
        return RedirectResponse(url="/interviews", status_code=302)

    applications = await get_applications(db)
    all_users = await get_all_users(db)
    interviewers = [u for u in all_users if u.role in ["Interviewer", "Hiring Manager", "HR Recruiter", "System Admin"]]

    form_data = None
    if application_id:
        form_data = type(
            "FormData",
            (),
            {
                "application_id": application_id,
                "interviewer_id": "",
                "scheduled_time": "",
                "notes": "",
            },
        )()

    return templates.TemplateResponse(
        request,
        "interviews/schedule_form.html",
        context={
            "user": user,
            "applications": applications,
            "interviewers": interviewers,
            "form_data": form_data,
            "errors": None,
        },
    )


@router.post("/schedule")
async def schedule_submit(
    request: Request,
    application_id: str = Form(...),
    interviewer_id: str = Form(...),
    scheduled_time: str = Form(...),
    notes: str = Form(""),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if user.role not in ["System Admin", "HR Recruiter", "Hiring Manager"]:
        return RedirectResponse(url="/interviews", status_code=302)

    errors: list[str] = []

    if not application_id:
        errors.append("Application is required.")
    if not interviewer_id:
        errors.append("Interviewer is required.")
    if not scheduled_time:
        errors.append("Scheduled date and time is required.")

    parsed_time: Optional[datetime] = None
    if scheduled_time:
        try:
            parsed_time = datetime.fromisoformat(scheduled_time)
        except (ValueError, TypeError):
            errors.append("Invalid date/time format.")

    if errors:
        applications = await get_applications(db)
        all_users = await get_all_users(db)
        interviewers = [u for u in all_users if u.role in ["Interviewer", "Hiring Manager", "HR Recruiter", "System Admin"]]

        form_data = type(
            "FormData",
            (),
            {
                "application_id": application_id,
                "interviewer_id": interviewer_id,
                "scheduled_time": scheduled_time,
                "notes": notes,
            },
        )()

        return templates.TemplateResponse(
            request,
            "interviews/schedule_form.html",
            context={
                "user": user,
                "applications": applications,
                "interviewers": interviewers,
                "form_data": form_data,
                "errors": errors,
            },
            status_code=400,
        )

    try:
        await schedule_interview(
            db=db,
            application_id=application_id,
            interviewer_id=interviewer_id,
            scheduled_time=parsed_time,
            scheduled_by_user_id=user.id,
            scheduled_by_username=user.username,
        )
    except ValueError as e:
        applications = await get_applications(db)
        all_users = await get_all_users(db)
        interviewers = [u for u in all_users if u.role in ["Interviewer", "Hiring Manager", "HR Recruiter", "System Admin"]]

        form_data = type(
            "FormData",
            (),
            {
                "application_id": application_id,
                "interviewer_id": interviewer_id,
                "scheduled_time": scheduled_time,
                "notes": notes,
            },
        )()

        return templates.TemplateResponse(
            request,
            "interviews/schedule_form.html",
            context={
                "user": user,
                "applications": applications,
                "interviewers": interviewers,
                "form_data": form_data,
                "errors": [str(e)],
            },
            status_code=400,
        )

    return RedirectResponse(url="/interviews", status_code=302)


@router.get("/{assignment_id}")
async def interview_detail(
    request: Request,
    assignment_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    assignment = await get_interview_by_id(db, assignment_id)

    if assignment is None:
        return templates.TemplateResponse(
            request,
            "interviews/interview_detail.html",
            context={
                "user": user,
                "interview": None,
                "candidate": None,
                "job": None,
                "interviewer": None,
                "application": None,
                "feedback": None,
                "feedback_submitted_by": None,
            },
            status_code=404,
        )

    candidate = None
    job = None
    application_obj = None
    if assignment.application:
        application_obj = assignment.application
        candidate = assignment.application.candidate
        job = assignment.application.job

    interviewer = assignment.interviewer

    feedback_obj = None
    feedback_submitted_by = None
    if assignment.feedback and len(assignment.feedback) > 0:
        feedback_obj = assignment.feedback[0]

    has_feedback = feedback_obj is not None
    now = datetime.utcnow()

    if assignment.scheduled_time and assignment.scheduled_time < now:
        interview_status = "Completed"
    else:
        interview_status = "Scheduled"

    interview_view = type(
        "InterviewDetailView",
        (),
        {
            "id": assignment.id,
            "scheduled_at": assignment.scheduled_time,
            "created_at": assignment.created_at,
            "status": interview_status,
            "feedback_submitted": has_feedback,
        },
    )()

    candidate_view = None
    if candidate:
        candidate_view = type(
            "CandidateView",
            (),
            {
                "id": candidate.id,
                "name": f"{candidate.first_name} {candidate.last_name}",
                "email": candidate.email or "",
                "phone": candidate.phone or "",
                "linkedin_url": candidate.linkedin_url or "",
            },
        )()

    job_view = None
    if job:
        job_view = type(
            "JobView",
            (),
            {
                "id": job.id,
                "title": job.title,
                "department": job.department,
                "location": job.location,
                "status": job.status,
            },
        )()

    interviewer_view = None
    if interviewer:
        interviewer_view = type(
            "InterviewerView",
            (),
            {
                "id": interviewer.id,
                "username": interviewer.username,
                "full_name": interviewer.username,
                "email": "",
                "role": interviewer.role,
            },
        )()

    return templates.TemplateResponse(
        request,
        "interviews/interview_detail.html",
        context={
            "user": user,
            "interview": interview_view,
            "candidate": candidate_view,
            "job": job_view,
            "interviewer": interviewer_view,
            "application": application_obj,
            "feedback": feedback_obj,
            "feedback_submitted_by": interviewer_view if feedback_obj else None,
        },
    )


@router.get("/{assignment_id}/feedback")
async def feedback_form(
    request: Request,
    assignment_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    assignment = await get_interview_by_id(db, assignment_id)

    if assignment is None:
        return RedirectResponse(url="/interviews", status_code=302)

    if assignment.feedback and len(assignment.feedback) > 0:
        return RedirectResponse(url=f"/interviews/{assignment_id}", status_code=302)

    candidate_name = ""
    job_title = ""
    scheduled_at_str = ""

    if assignment.application:
        app = assignment.application
        if app.candidate:
            candidate_name = f"{app.candidate.first_name} {app.candidate.last_name}"
        if app.job:
            job_title = app.job.title or ""

    if assignment.scheduled_time:
        scheduled_at_str = assignment.scheduled_time.strftime("%B %d, %Y at %I:%M %p")

    now = datetime.utcnow()
    if assignment.scheduled_time and assignment.scheduled_time < now:
        interview_status = "Completed"
    else:
        interview_status = "Scheduled"

    interview_view = type(
        "InterviewFeedbackView",
        (),
        {
            "id": assignment.id,
            "candidate_name": candidate_name,
            "job_title": job_title,
            "scheduled_at": scheduled_at_str,
            "status": interview_status,
        },
    )()

    return templates.TemplateResponse(
        request,
        "interviews/feedback_form.html",
        context={
            "user": user,
            "interview": interview_view,
            "errors": None,
            "form_data": None,
        },
    )


@router.post("/{assignment_id}/feedback")
async def feedback_submit(
    request: Request,
    assignment_id: str,
    rating: int = Form(...),
    notes: str = Form(...),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    assignment = await get_interview_by_id(db, assignment_id)

    if assignment is None:
        return RedirectResponse(url="/interviews", status_code=302)

    if assignment.feedback and len(assignment.feedback) > 0:
        return RedirectResponse(url=f"/interviews/{assignment_id}", status_code=302)

    candidate_name = ""
    job_title = ""
    scheduled_at_str = ""

    if assignment.application:
        app = assignment.application
        if app.candidate:
            candidate_name = f"{app.candidate.first_name} {app.candidate.last_name}"
        if app.job:
            job_title = app.job.title or ""

    if assignment.scheduled_time:
        scheduled_at_str = assignment.scheduled_time.strftime("%B %d, %Y at %I:%M %p")

    now = datetime.utcnow()
    if assignment.scheduled_time and assignment.scheduled_time < now:
        interview_status = "Completed"
    else:
        interview_status = "Scheduled"

    interview_view = type(
        "InterviewFeedbackView",
        (),
        {
            "id": assignment.id,
            "candidate_name": candidate_name,
            "job_title": job_title,
            "scheduled_at": scheduled_at_str,
            "status": interview_status,
        },
    )()

    validation_errors = validate_feedback(rating, notes)
    if validation_errors:
        form_data = type(
            "FormData",
            (),
            {
                "rating": rating,
                "notes": notes,
            },
        )()

        return templates.TemplateResponse(
            request,
            "interviews/feedback_form.html",
            context={
                "user": user,
                "interview": interview_view,
                "errors": validation_errors,
                "form_data": form_data,
            },
            status_code=400,
        )

    try:
        await submit_feedback(
            db=db,
            assignment_id=assignment_id,
            rating=rating,
            notes=notes,
            submitted_by=user.id,
            submitted_by_username=user.username,
        )
    except ValueError as e:
        form_data = type(
            "FormData",
            (),
            {
                "rating": rating,
                "notes": notes,
            },
        )()

        return templates.TemplateResponse(
            request,
            "interviews/feedback_form.html",
            context={
                "user": user,
                "interview": interview_view,
                "errors": [str(e)],
                "form_data": form_data,
            },
            status_code=400,
        )

    await log_action(
        db=db,
        user_id=user.id,
        username=user.username,
        action="Feedback Submitted",
        details=f"User '{user.username}' submitted feedback for interview {assignment_id} — Rating: {rating}/5",
    )

    return RedirectResponse(url=f"/interviews/{assignment_id}", status_code=302)