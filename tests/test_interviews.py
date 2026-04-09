from datetime import datetime, timedelta

import httpx
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.application import Application
from app.models.candidate import Candidate
from app.models.interview import InterviewAssignment, InterviewFeedback
from app.models.job import Job
from app.models.user import User


async def _create_job(db_session: AsyncSession, owner_id: str) -> Job:
    job = Job(
        title="Backend Engineer",
        department="Engineering",
        location="Remote",
        job_type="Full-Time",
        salary_min=100000,
        salary_max=150000,
        description="Build backend services.",
        status="Published",
        owner_id=owner_id,
    )
    db_session.add(job)
    await db_session.flush()
    await db_session.refresh(job)
    return job


async def _create_candidate(db_session: AsyncSession) -> Candidate:
    candidate = Candidate(
        first_name="Alice",
        last_name="Smith",
        email="alice.smith@example.com",
        phone="+1234567890",
    )
    db_session.add(candidate)
    await db_session.flush()
    await db_session.refresh(candidate)
    return candidate


async def _create_application(
    db_session: AsyncSession, candidate_id: str, job_id: str
) -> Application:
    application = Application(
        candidate_id=candidate_id,
        job_id=job_id,
        status="Interviewing",
        applied_at=datetime.utcnow(),
    )
    db_session.add(application)
    await db_session.flush()
    await db_session.refresh(application)
    return application


async def _create_interview_assignment(
    db_session: AsyncSession,
    application_id: str,
    interviewer_id: str,
    scheduled_time: datetime | None = None,
) -> InterviewAssignment:
    if scheduled_time is None:
        scheduled_time = datetime.utcnow() - timedelta(hours=1)
    assignment = InterviewAssignment(
        application_id=application_id,
        interviewer_id=interviewer_id,
        scheduled_time=scheduled_time,
    )
    db_session.add(assignment)
    await db_session.flush()
    await db_session.refresh(assignment)
    return assignment


@pytest.mark.asyncio
class TestScheduleInterview:
    async def test_admin_can_schedule_interview(
        self,
        admin_client: httpx.AsyncClient,
        admin_user: User,
        db_session: AsyncSession,
    ):
        job = await _create_job(db_session, admin_user.id)
        candidate = await _create_candidate(db_session)
        application = await _create_application(db_session, candidate.id, job.id)

        scheduled_time = (datetime.utcnow() + timedelta(days=3)).strftime(
            "%Y-%m-%dT%H:%M"
        )

        response = await admin_client.post(
            "/interviews/schedule",
            data={
                "application_id": application.id,
                "interviewer_id": admin_user.id,
                "scheduled_time": scheduled_time,
                "notes": "",
            },
            follow_redirects=False,
        )

        assert response.status_code == 302
        assert "/interviews" in response.headers.get("location", "")

    async def test_recruiter_can_schedule_interview(
        self,
        recruiter_client: httpx.AsyncClient,
        recruiter_user: User,
        interviewer_user: User,
        db_session: AsyncSession,
    ):
        job = await _create_job(db_session, recruiter_user.id)
        candidate = await _create_candidate(db_session)
        application = await _create_application(db_session, candidate.id, job.id)

        scheduled_time = (datetime.utcnow() + timedelta(days=2)).strftime(
            "%Y-%m-%dT%H:%M"
        )

        response = await recruiter_client.post(
            "/interviews/schedule",
            data={
                "application_id": application.id,
                "interviewer_id": interviewer_user.id,
                "scheduled_time": scheduled_time,
                "notes": "",
            },
            follow_redirects=False,
        )

        assert response.status_code == 302
        assert "/interviews" in response.headers.get("location", "")

    async def test_interviewer_cannot_schedule_interview(
        self,
        interviewer_client: httpx.AsyncClient,
        interviewer_user: User,
        admin_user: User,
        db_session: AsyncSession,
    ):
        job = await _create_job(db_session, admin_user.id)
        candidate = await _create_candidate(db_session)
        application = await _create_application(db_session, candidate.id, job.id)

        scheduled_time = (datetime.utcnow() + timedelta(days=2)).strftime(
            "%Y-%m-%dT%H:%M"
        )

        response = await interviewer_client.post(
            "/interviews/schedule",
            data={
                "application_id": application.id,
                "interviewer_id": interviewer_user.id,
                "scheduled_time": scheduled_time,
                "notes": "",
            },
            follow_redirects=False,
        )

        assert response.status_code == 302
        assert response.headers.get("location") == "/interviews"

    async def test_schedule_form_requires_auth(
        self,
        client: httpx.AsyncClient,
    ):
        response = await client.get("/interviews/schedule", follow_redirects=False)
        assert response.status_code == 401

    async def test_schedule_with_missing_fields_returns_400(
        self,
        admin_client: httpx.AsyncClient,
        admin_user: User,
        db_session: AsyncSession,
    ):
        response = await admin_client.post(
            "/interviews/schedule",
            data={
                "application_id": "",
                "interviewer_id": "",
                "scheduled_time": "",
                "notes": "",
            },
            follow_redirects=False,
        )

        assert response.status_code == 400

    async def test_schedule_with_invalid_datetime_returns_400(
        self,
        admin_client: httpx.AsyncClient,
        admin_user: User,
        db_session: AsyncSession,
    ):
        job = await _create_job(db_session, admin_user.id)
        candidate = await _create_candidate(db_session)
        application = await _create_application(db_session, candidate.id, job.id)

        response = await admin_client.post(
            "/interviews/schedule",
            data={
                "application_id": application.id,
                "interviewer_id": admin_user.id,
                "scheduled_time": "not-a-date",
                "notes": "",
            },
            follow_redirects=False,
        )

        assert response.status_code == 400


@pytest.mark.asyncio
class TestMyInterviews:
    async def test_my_interviews_returns_only_assigned(
        self,
        interviewer_client: httpx.AsyncClient,
        interviewer_user: User,
        admin_user: User,
        db_session: AsyncSession,
    ):
        job = await _create_job(db_session, admin_user.id)
        candidate = await _create_candidate(db_session)
        application = await _create_application(db_session, candidate.id, job.id)

        await _create_interview_assignment(
            db_session,
            application.id,
            interviewer_user.id,
            scheduled_time=datetime.utcnow() + timedelta(days=1),
        )

        other_user = User(
            username="otherinterviewer",
            password_hash="fakehash",
            role="Interviewer",
        )
        db_session.add(other_user)
        await db_session.flush()
        await db_session.refresh(other_user)

        candidate2 = Candidate(
            first_name="Bob",
            last_name="Jones",
            email="bob.jones@example.com",
        )
        db_session.add(candidate2)
        await db_session.flush()
        await db_session.refresh(candidate2)

        app2 = Application(
            candidate_id=candidate2.id,
            job_id=job.id,
            status="Interviewing",
            applied_at=datetime.utcnow(),
        )
        db_session.add(app2)
        await db_session.flush()
        await db_session.refresh(app2)

        await _create_interview_assignment(
            db_session,
            app2.id,
            other_user.id,
            scheduled_time=datetime.utcnow() + timedelta(days=2),
        )

        response = await interviewer_client.get("/interviews/my")
        assert response.status_code == 200

        content = response.text
        assert "Alice Smith" in content
        assert "Bob Jones" not in content

    async def test_my_interviews_requires_auth(
        self,
        client: httpx.AsyncClient,
    ):
        response = await client.get("/interviews/my", follow_redirects=False)
        assert response.status_code == 401


@pytest.mark.asyncio
class TestInterviewList:
    async def test_interview_list_accessible_by_admin(
        self,
        admin_client: httpx.AsyncClient,
        admin_user: User,
        db_session: AsyncSession,
    ):
        response = await admin_client.get("/interviews")
        assert response.status_code == 200

    async def test_interview_list_accessible_by_interviewer(
        self,
        interviewer_client: httpx.AsyncClient,
    ):
        response = await interviewer_client.get("/interviews")
        assert response.status_code == 200

    async def test_interview_list_requires_auth(
        self,
        client: httpx.AsyncClient,
    ):
        response = await client.get("/interviews", follow_redirects=False)
        assert response.status_code == 401


@pytest.mark.asyncio
class TestInterviewDetail:
    async def test_interview_detail_accessible(
        self,
        admin_client: httpx.AsyncClient,
        admin_user: User,
        db_session: AsyncSession,
    ):
        job = await _create_job(db_session, admin_user.id)
        candidate = await _create_candidate(db_session)
        application = await _create_application(db_session, candidate.id, job.id)
        assignment = await _create_interview_assignment(
            db_session, application.id, admin_user.id
        )

        response = await admin_client.get(f"/interviews/{assignment.id}")
        assert response.status_code == 200
        assert "Alice Smith" in response.text

    async def test_interview_detail_not_found(
        self,
        admin_client: httpx.AsyncClient,
    ):
        response = await admin_client.get(
            "/interviews/nonexistent-id-12345"
        )
        assert response.status_code == 404


@pytest.mark.asyncio
class TestSubmitFeedback:
    async def test_submit_feedback_valid_rating(
        self,
        interviewer_client: httpx.AsyncClient,
        interviewer_user: User,
        admin_user: User,
        db_session: AsyncSession,
    ):
        job = await _create_job(db_session, admin_user.id)
        candidate = await _create_candidate(db_session)
        application = await _create_application(db_session, candidate.id, job.id)
        assignment = await _create_interview_assignment(
            db_session,
            application.id,
            interviewer_user.id,
            scheduled_time=datetime.utcnow() - timedelta(hours=2),
        )

        response = await interviewer_client.post(
            f"/interviews/{assignment.id}/feedback",
            data={
                "rating": 4,
                "notes": "Great candidate with strong technical skills and good communication.",
            },
            follow_redirects=False,
        )

        assert response.status_code == 302
        assert f"/interviews/{assignment.id}" in response.headers.get("location", "")

    async def test_submit_feedback_rating_1(
        self,
        interviewer_client: httpx.AsyncClient,
        interviewer_user: User,
        admin_user: User,
        db_session: AsyncSession,
    ):
        job = await _create_job(db_session, admin_user.id)
        candidate = await _create_candidate(db_session)
        application = await _create_application(db_session, candidate.id, job.id)
        assignment = await _create_interview_assignment(
            db_session,
            application.id,
            interviewer_user.id,
            scheduled_time=datetime.utcnow() - timedelta(hours=2),
        )

        response = await interviewer_client.post(
            f"/interviews/{assignment.id}/feedback",
            data={
                "rating": 1,
                "notes": "Candidate did not meet the minimum requirements for this role.",
            },
            follow_redirects=False,
        )

        assert response.status_code == 302

    async def test_submit_feedback_rating_5(
        self,
        interviewer_client: httpx.AsyncClient,
        interviewer_user: User,
        admin_user: User,
        db_session: AsyncSession,
    ):
        job = await _create_job(db_session, admin_user.id)
        candidate = await _create_candidate(db_session)
        application = await _create_application(db_session, candidate.id, job.id)
        assignment = await _create_interview_assignment(
            db_session,
            application.id,
            interviewer_user.id,
            scheduled_time=datetime.utcnow() - timedelta(hours=2),
        )

        response = await interviewer_client.post(
            f"/interviews/{assignment.id}/feedback",
            data={
                "rating": 5,
                "notes": "Exceptional candidate, strongly recommend hiring immediately.",
            },
            follow_redirects=False,
        )

        assert response.status_code == 302

    async def test_submit_feedback_invalid_rating_zero(
        self,
        interviewer_client: httpx.AsyncClient,
        interviewer_user: User,
        admin_user: User,
        db_session: AsyncSession,
    ):
        job = await _create_job(db_session, admin_user.id)
        candidate = await _create_candidate(db_session)
        application = await _create_application(db_session, candidate.id, job.id)
        assignment = await _create_interview_assignment(
            db_session,
            application.id,
            interviewer_user.id,
            scheduled_time=datetime.utcnow() - timedelta(hours=2),
        )

        response = await interviewer_client.post(
            f"/interviews/{assignment.id}/feedback",
            data={
                "rating": 0,
                "notes": "This is a test with an invalid rating value of zero.",
            },
            follow_redirects=False,
        )

        assert response.status_code == 400

    async def test_submit_feedback_invalid_rating_six(
        self,
        interviewer_client: httpx.AsyncClient,
        interviewer_user: User,
        admin_user: User,
        db_session: AsyncSession,
    ):
        job = await _create_job(db_session, admin_user.id)
        candidate = await _create_candidate(db_session)
        application = await _create_application(db_session, candidate.id, job.id)
        assignment = await _create_interview_assignment(
            db_session,
            application.id,
            interviewer_user.id,
            scheduled_time=datetime.utcnow() - timedelta(hours=2),
        )

        response = await interviewer_client.post(
            f"/interviews/{assignment.id}/feedback",
            data={
                "rating": 6,
                "notes": "This is a test with an invalid rating value of six.",
            },
            follow_redirects=False,
        )

        assert response.status_code == 400

    async def test_submit_feedback_notes_too_short(
        self,
        interviewer_client: httpx.AsyncClient,
        interviewer_user: User,
        admin_user: User,
        db_session: AsyncSession,
    ):
        job = await _create_job(db_session, admin_user.id)
        candidate = await _create_candidate(db_session)
        application = await _create_application(db_session, candidate.id, job.id)
        assignment = await _create_interview_assignment(
            db_session,
            application.id,
            interviewer_user.id,
            scheduled_time=datetime.utcnow() - timedelta(hours=2),
        )

        response = await interviewer_client.post(
            f"/interviews/{assignment.id}/feedback",
            data={
                "rating": 3,
                "notes": "Short",
            },
            follow_redirects=False,
        )

        assert response.status_code == 400

    async def test_submit_feedback_duplicate_rejected(
        self,
        interviewer_client: httpx.AsyncClient,
        interviewer_user: User,
        admin_user: User,
        db_session: AsyncSession,
    ):
        job = await _create_job(db_session, admin_user.id)
        candidate = await _create_candidate(db_session)
        application = await _create_application(db_session, candidate.id, job.id)
        assignment = await _create_interview_assignment(
            db_session,
            application.id,
            interviewer_user.id,
            scheduled_time=datetime.utcnow() - timedelta(hours=2),
        )

        feedback = InterviewFeedback(
            assignment_id=assignment.id,
            rating=4,
            notes="Already submitted feedback for this interview assignment.",
            submitted_by=interviewer_user.id,
        )
        db_session.add(feedback)
        await db_session.flush()

        response = await interviewer_client.post(
            f"/interviews/{assignment.id}/feedback",
            data={
                "rating": 5,
                "notes": "Trying to submit duplicate feedback for the same interview.",
            },
            follow_redirects=False,
        )

        assert response.status_code == 302
        assert f"/interviews/{assignment.id}" in response.headers.get("location", "")

    async def test_feedback_form_requires_auth(
        self,
        client: httpx.AsyncClient,
        admin_user: User,
        db_session: AsyncSession,
    ):
        job = await _create_job(db_session, admin_user.id)
        candidate = await _create_candidate(db_session)
        application = await _create_application(db_session, candidate.id, job.id)
        assignment = await _create_interview_assignment(
            db_session, application.id, admin_user.id
        )

        response = await client.get(
            f"/interviews/{assignment.id}/feedback",
            follow_redirects=False,
        )
        assert response.status_code == 401


@pytest.mark.asyncio
class TestFeedbackViewable:
    async def test_feedback_viewable_on_detail_page(
        self,
        admin_client: httpx.AsyncClient,
        admin_user: User,
        interviewer_user: User,
        db_session: AsyncSession,
    ):
        job = await _create_job(db_session, admin_user.id)
        candidate = await _create_candidate(db_session)
        application = await _create_application(db_session, candidate.id, job.id)
        assignment = await _create_interview_assignment(
            db_session,
            application.id,
            interviewer_user.id,
            scheduled_time=datetime.utcnow() - timedelta(hours=2),
        )

        feedback = InterviewFeedback(
            assignment_id=assignment.id,
            rating=4,
            notes="Strong technical skills demonstrated during the coding exercise.",
            submitted_by=interviewer_user.id,
        )
        db_session.add(feedback)
        await db_session.flush()

        response = await admin_client.get(f"/interviews/{assignment.id}")
        assert response.status_code == 200
        assert "4" in response.text
        assert "Strong technical skills" in response.text

    async def test_feedback_viewable_by_recruiter(
        self,
        recruiter_client: httpx.AsyncClient,
        recruiter_user: User,
        interviewer_user: User,
        db_session: AsyncSession,
    ):
        job = await _create_job(db_session, recruiter_user.id)
        candidate = await _create_candidate(db_session)
        application = await _create_application(db_session, candidate.id, job.id)
        assignment = await _create_interview_assignment(
            db_session,
            application.id,
            interviewer_user.id,
            scheduled_time=datetime.utcnow() - timedelta(hours=2),
        )

        feedback = InterviewFeedback(
            assignment_id=assignment.id,
            rating=3,
            notes="Average performance, needs improvement in system design area.",
            submitted_by=interviewer_user.id,
        )
        db_session.add(feedback)
        await db_session.flush()

        response = await recruiter_client.get(f"/interviews/{assignment.id}")
        assert response.status_code == 200
        assert "Average performance" in response.text

    async def test_feedback_viewable_by_interviewer(
        self,
        interviewer_client: httpx.AsyncClient,
        interviewer_user: User,
        admin_user: User,
        db_session: AsyncSession,
    ):
        job = await _create_job(db_session, admin_user.id)
        candidate = await _create_candidate(db_session)
        application = await _create_application(db_session, candidate.id, job.id)
        assignment = await _create_interview_assignment(
            db_session,
            application.id,
            interviewer_user.id,
            scheduled_time=datetime.utcnow() - timedelta(hours=2),
        )

        feedback = InterviewFeedback(
            assignment_id=assignment.id,
            rating=5,
            notes="Outstanding candidate, exceeded all expectations in every area.",
            submitted_by=interviewer_user.id,
        )
        db_session.add(feedback)
        await db_session.flush()

        response = await interviewer_client.get(f"/interviews/{assignment.id}")
        assert response.status_code == 200
        assert "Outstanding candidate" in response.text


@pytest.mark.asyncio
class TestRBACEnforcement:
    async def test_schedule_form_get_blocked_for_interviewer(
        self,
        interviewer_client: httpx.AsyncClient,
    ):
        response = await interviewer_client.get(
            "/interviews/schedule", follow_redirects=False
        )
        assert response.status_code == 302
        assert response.headers.get("location") == "/interviews"

    async def test_hiring_manager_can_schedule(
        self,
        hiring_manager_client: httpx.AsyncClient,
        hiring_manager_user: User,
        interviewer_user: User,
        db_session: AsyncSession,
    ):
        job = await _create_job(db_session, hiring_manager_user.id)
        candidate = await _create_candidate(db_session)
        application = await _create_application(db_session, candidate.id, job.id)

        scheduled_time = (datetime.utcnow() + timedelta(days=5)).strftime(
            "%Y-%m-%dT%H:%M"
        )

        response = await hiring_manager_client.post(
            "/interviews/schedule",
            data={
                "application_id": application.id,
                "interviewer_id": interviewer_user.id,
                "scheduled_time": scheduled_time,
                "notes": "",
            },
            follow_redirects=False,
        )

        assert response.status_code == 302
        assert "/interviews" in response.headers.get("location", "")

    async def test_unauthenticated_cannot_access_interviews(
        self,
        client: httpx.AsyncClient,
    ):
        response = await client.get("/interviews", follow_redirects=False)
        assert response.status_code == 401

    async def test_unauthenticated_cannot_submit_feedback(
        self,
        client: httpx.AsyncClient,
    ):
        response = await client.post(
            "/interviews/some-id/feedback",
            data={"rating": 3, "notes": "Some feedback notes for testing purposes."},
            follow_redirects=False,
        )
        assert response.status_code == 401

    async def test_feedback_form_get_accessible_by_all_authenticated_roles(
        self,
        admin_client: httpx.AsyncClient,
        admin_user: User,
        db_session: AsyncSession,
    ):
        job = await _create_job(db_session, admin_user.id)
        candidate = await _create_candidate(db_session)
        application = await _create_application(db_session, candidate.id, job.id)
        assignment = await _create_interview_assignment(
            db_session,
            application.id,
            admin_user.id,
            scheduled_time=datetime.utcnow() - timedelta(hours=1),
        )

        response = await admin_client.get(f"/interviews/{assignment.id}/feedback")
        assert response.status_code == 200