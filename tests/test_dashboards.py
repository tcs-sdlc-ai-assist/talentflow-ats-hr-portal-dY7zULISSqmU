import pytest
import pytest_asyncio
from datetime import datetime, timedelta

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.models.job import Job
from app.models.candidate import Candidate
from app.models.application import Application
from app.models.interview import InterviewAssignment, InterviewFeedback


async def _create_job(
    db: AsyncSession,
    owner_id: str,
    title: str = "Test Engineer",
    status: str = "Published",
) -> Job:
    job = Job(
        title=title,
        department="Engineering",
        location="Remote",
        job_type="Full-Time",
        description="A test job description for testing purposes.",
        status=status,
        owner_id=owner_id,
    )
    db.add(job)
    await db.flush()
    await db.refresh(job)
    return job


async def _create_candidate(
    db: AsyncSession,
    first_name: str = "Jane",
    last_name: str = "Doe",
    email: str = "jane.doe@example.com",
) -> Candidate:
    candidate = Candidate(
        first_name=first_name,
        last_name=last_name,
        email=email,
    )
    db.add(candidate)
    await db.flush()
    await db.refresh(candidate)
    return candidate


async def _create_application(
    db: AsyncSession,
    candidate_id: str,
    job_id: str,
    status: str = "Applied",
) -> Application:
    application = Application(
        candidate_id=candidate_id,
        job_id=job_id,
        status=status,
        applied_at=datetime.utcnow(),
    )
    db.add(application)
    await db.flush()
    await db.refresh(application)
    return application


async def _create_interview_assignment(
    db: AsyncSession,
    application_id: str,
    interviewer_id: str,
    scheduled_time: datetime | None = None,
) -> InterviewAssignment:
    if scheduled_time is None:
        scheduled_time = datetime.utcnow() + timedelta(days=1)
    assignment = InterviewAssignment(
        application_id=application_id,
        interviewer_id=interviewer_id,
        scheduled_time=scheduled_time,
    )
    db.add(assignment)
    await db.flush()
    await db.refresh(assignment)
    return assignment


async def _create_feedback(
    db: AsyncSession,
    assignment_id: str,
    submitted_by: str,
    rating: int = 4,
    notes: str = "Good candidate with strong skills.",
) -> InterviewFeedback:
    feedback = InterviewFeedback(
        assignment_id=assignment_id,
        rating=rating,
        notes=notes,
        submitted_by=submitted_by,
    )
    db.add(feedback)
    await db.flush()
    await db.refresh(feedback)
    return feedback


# ---------------------------------------------------------------------------
# HR Dashboard Tests (SCRUM-15609)
# ---------------------------------------------------------------------------


class TestHRDashboard:
    async def test_hr_dashboard_accessible_by_admin(
        self,
        admin_client: httpx.AsyncClient,
        db_session: AsyncSession,
        admin_user: User,
    ):
        response = await admin_client.get("/dashboard/hr", follow_redirects=False)
        assert response.status_code == 200
        assert "HR Dashboard" in response.text

    async def test_hr_dashboard_accessible_by_recruiter(
        self,
        recruiter_client: httpx.AsyncClient,
        db_session: AsyncSession,
        recruiter_user: User,
    ):
        response = await recruiter_client.get("/dashboard/hr", follow_redirects=False)
        assert response.status_code == 200
        assert "HR Dashboard" in response.text

    async def test_hr_dashboard_shows_metrics(
        self,
        admin_client: httpx.AsyncClient,
        db_session: AsyncSession,
        admin_user: User,
    ):
        job = await _create_job(db_session, owner_id=admin_user.id, status="Published")
        candidate = await _create_candidate(db_session)
        await _create_application(db_session, candidate_id=candidate.id, job_id=job.id)
        await db_session.commit()

        response = await admin_client.get("/dashboard/hr", follow_redirects=False)
        assert response.status_code == 200
        text = response.text
        assert "Total Jobs" in text
        assert "Total Candidates" in text
        assert "Total Applications" in text
        assert "Total Interviews" in text

    async def test_hr_dashboard_shows_pipeline_stages(
        self,
        admin_client: httpx.AsyncClient,
        db_session: AsyncSession,
        admin_user: User,
    ):
        job = await _create_job(db_session, owner_id=admin_user.id)
        c1 = await _create_candidate(db_session, email="c1@example.com")
        c2 = await _create_candidate(db_session, email="c2@example.com", first_name="Bob")
        await _create_application(db_session, candidate_id=c1.id, job_id=job.id, status="Applied")
        await _create_application(db_session, candidate_id=c2.id, job_id=job.id, status="Screening")
        await db_session.commit()

        response = await admin_client.get("/dashboard/hr", follow_redirects=False)
        assert response.status_code == 200
        assert "Pipeline Stage Distribution" in response.text
        assert "Applied" in response.text
        assert "Screening" in response.text

    async def test_hr_dashboard_shows_audit_logs(
        self,
        admin_client: httpx.AsyncClient,
        db_session: AsyncSession,
        admin_user: User,
    ):
        from app.services.audit_service import log_action

        await log_action(
            db=db_session,
            user_id=admin_user.id,
            username=admin_user.username,
            action="Job Created",
            details="Test audit log entry",
        )
        await db_session.commit()

        response = await admin_client.get("/dashboard/hr", follow_redirects=False)
        assert response.status_code == 200
        assert "Recent Audit Log" in response.text
        assert "Job Created" in response.text

    async def test_hr_dashboard_forbidden_for_interviewer(
        self,
        interviewer_client: httpx.AsyncClient,
        interviewer_user: User,
    ):
        response = await interviewer_client.get("/dashboard/hr", follow_redirects=False)
        assert response.status_code == 403

    async def test_hr_dashboard_forbidden_for_hiring_manager(
        self,
        hiring_manager_client: httpx.AsyncClient,
        hiring_manager_user: User,
    ):
        response = await hiring_manager_client.get("/dashboard/hr", follow_redirects=False)
        assert response.status_code == 403


# ---------------------------------------------------------------------------
# Hiring Manager Dashboard Tests (SCRUM-15608)
# ---------------------------------------------------------------------------


class TestHiringManagerDashboard:
    async def test_hm_dashboard_accessible_by_hiring_manager(
        self,
        hiring_manager_client: httpx.AsyncClient,
        db_session: AsyncSession,
        hiring_manager_user: User,
    ):
        response = await hiring_manager_client.get(
            "/dashboard/hiring-manager", follow_redirects=False
        )
        assert response.status_code == 200
        assert "Hiring Manager Dashboard" in response.text

    async def test_hm_dashboard_accessible_by_admin(
        self,
        admin_client: httpx.AsyncClient,
        db_session: AsyncSession,
        admin_user: User,
    ):
        response = await admin_client.get(
            "/dashboard/hiring-manager", follow_redirects=False
        )
        assert response.status_code == 200

    async def test_hm_dashboard_shows_own_jobs(
        self,
        hiring_manager_client: httpx.AsyncClient,
        db_session: AsyncSession,
        hiring_manager_user: User,
    ):
        job = await _create_job(
            db_session,
            owner_id=hiring_manager_user.id,
            title="HM Test Position",
            status="Published",
        )
        candidate = await _create_candidate(db_session, email="hm_cand@example.com")
        await _create_application(db_session, candidate_id=candidate.id, job_id=job.id)
        await db_session.commit()

        response = await hiring_manager_client.get(
            "/dashboard/hiring-manager", follow_redirects=False
        )
        assert response.status_code == 200
        text = response.text
        assert "HM Test Position" in text
        assert "Total Jobs" in text
        assert "Published Jobs" in text
        assert "Total Applications" in text

    async def test_hm_dashboard_shows_metrics(
        self,
        hiring_manager_client: httpx.AsyncClient,
        db_session: AsyncSession,
        hiring_manager_user: User,
    ):
        await _create_job(
            db_session,
            owner_id=hiring_manager_user.id,
            title="Job A",
            status="Published",
        )
        await _create_job(
            db_session,
            owner_id=hiring_manager_user.id,
            title="Job B",
            status="Draft",
        )
        await db_session.commit()

        response = await hiring_manager_client.get(
            "/dashboard/hiring-manager", follow_redirects=False
        )
        assert response.status_code == 200
        text = response.text
        assert "Total Jobs" in text
        assert "Published Jobs" in text

    async def test_hm_dashboard_forbidden_for_interviewer(
        self,
        interviewer_client: httpx.AsyncClient,
        interviewer_user: User,
    ):
        response = await interviewer_client.get(
            "/dashboard/hiring-manager", follow_redirects=False
        )
        assert response.status_code == 403

    async def test_hm_dashboard_empty_state(
        self,
        hiring_manager_client: httpx.AsyncClient,
        db_session: AsyncSession,
        hiring_manager_user: User,
    ):
        response = await hiring_manager_client.get(
            "/dashboard/hiring-manager", follow_redirects=False
        )
        assert response.status_code == 200
        assert "No job requisitions" in response.text or "Hiring Manager Dashboard" in response.text


# ---------------------------------------------------------------------------
# Interviewer Dashboard Tests (SCRUM-15610)
# ---------------------------------------------------------------------------


class TestInterviewerDashboard:
    async def test_interviewer_dashboard_accessible_by_interviewer(
        self,
        interviewer_client: httpx.AsyncClient,
        db_session: AsyncSession,
        interviewer_user: User,
    ):
        response = await interviewer_client.get(
            "/dashboard/interviewer", follow_redirects=False
        )
        assert response.status_code == 200
        assert "Interviewer Dashboard" in response.text

    async def test_interviewer_dashboard_accessible_by_admin(
        self,
        admin_client: httpx.AsyncClient,
        db_session: AsyncSession,
        admin_user: User,
    ):
        response = await admin_client.get(
            "/dashboard/interviewer", follow_redirects=False
        )
        assert response.status_code == 200

    async def test_interviewer_dashboard_shows_stats(
        self,
        interviewer_client: httpx.AsyncClient,
        db_session: AsyncSession,
        interviewer_user: User,
        admin_user: User,
    ):
        job = await _create_job(db_session, owner_id=admin_user.id)
        candidate = await _create_candidate(db_session, email="int_cand@example.com")
        application = await _create_application(
            db_session, candidate_id=candidate.id, job_id=job.id
        )
        await _create_interview_assignment(
            db_session,
            application_id=application.id,
            interviewer_id=interviewer_user.id,
            scheduled_time=datetime.utcnow() + timedelta(days=2),
        )
        await db_session.commit()

        response = await interviewer_client.get(
            "/dashboard/interviewer", follow_redirects=False
        )
        assert response.status_code == 200
        text = response.text
        assert "Total Assignments" in text
        assert "Upcoming Interviews" in text

    async def test_interviewer_dashboard_shows_upcoming_interviews(
        self,
        interviewer_client: httpx.AsyncClient,
        db_session: AsyncSession,
        interviewer_user: User,
        admin_user: User,
    ):
        job = await _create_job(db_session, owner_id=admin_user.id, title="Upcoming Job")
        candidate = await _create_candidate(
            db_session, first_name="Alice", last_name="Smith", email="alice@example.com"
        )
        application = await _create_application(
            db_session, candidate_id=candidate.id, job_id=job.id
        )
        await _create_interview_assignment(
            db_session,
            application_id=application.id,
            interviewer_id=interviewer_user.id,
            scheduled_time=datetime.utcnow() + timedelta(days=3),
        )
        await db_session.commit()

        response = await interviewer_client.get(
            "/dashboard/interviewer", follow_redirects=False
        )
        assert response.status_code == 200
        text = response.text
        assert "Alice Smith" in text
        assert "Upcoming Job" in text

    async def test_interviewer_dashboard_shows_pending_feedback(
        self,
        interviewer_client: httpx.AsyncClient,
        db_session: AsyncSession,
        interviewer_user: User,
        admin_user: User,
    ):
        job = await _create_job(db_session, owner_id=admin_user.id, title="Feedback Job")
        candidate = await _create_candidate(
            db_session, first_name="Bob", last_name="Jones", email="bob.jones@example.com"
        )
        application = await _create_application(
            db_session, candidate_id=candidate.id, job_id=job.id
        )
        # Create a past interview (completed) without feedback
        past_time = datetime.utcnow() - timedelta(days=1)
        await _create_interview_assignment(
            db_session,
            application_id=application.id,
            interviewer_id=interviewer_user.id,
            scheduled_time=past_time,
        )
        await db_session.commit()

        response = await interviewer_client.get(
            "/dashboard/interviewer", follow_redirects=False
        )
        assert response.status_code == 200
        text = response.text
        assert "Feedback Required" in text or "Pending Feedback" in text
        assert "Bob Jones" in text

    async def test_interviewer_dashboard_shows_recent_feedback(
        self,
        interviewer_client: httpx.AsyncClient,
        db_session: AsyncSession,
        interviewer_user: User,
        admin_user: User,
    ):
        job = await _create_job(db_session, owner_id=admin_user.id, title="Feedback Done Job")
        candidate = await _create_candidate(
            db_session,
            first_name="Carol",
            last_name="White",
            email="carol.white@example.com",
        )
        application = await _create_application(
            db_session, candidate_id=candidate.id, job_id=job.id
        )
        past_time = datetime.utcnow() - timedelta(days=2)
        assignment = await _create_interview_assignment(
            db_session,
            application_id=application.id,
            interviewer_id=interviewer_user.id,
            scheduled_time=past_time,
        )
        await _create_feedback(
            db_session,
            assignment_id=assignment.id,
            submitted_by=interviewer_user.id,
            rating=5,
            notes="Excellent candidate, highly recommend.",
        )
        await db_session.commit()

        response = await interviewer_client.get(
            "/dashboard/interviewer", follow_redirects=False
        )
        assert response.status_code == 200
        text = response.text
        assert "Recent Feedback Submitted" in text
        assert "Carol White" in text

    async def test_interviewer_dashboard_empty_state(
        self,
        interviewer_client: httpx.AsyncClient,
        db_session: AsyncSession,
        interviewer_user: User,
    ):
        response = await interviewer_client.get(
            "/dashboard/interviewer", follow_redirects=False
        )
        assert response.status_code == 200
        text = response.text
        assert "No upcoming interviews" in text or "Interviewer Dashboard" in text


# ---------------------------------------------------------------------------
# Dashboard Redirect Tests
# ---------------------------------------------------------------------------


class TestDashboardRedirect:
    async def test_admin_redirects_to_hr_dashboard(
        self,
        admin_client: httpx.AsyncClient,
        admin_user: User,
    ):
        response = await admin_client.get("/dashboard", follow_redirects=False)
        assert response.status_code == 302
        assert "/dashboard/hr" in response.headers["location"]

    async def test_recruiter_redirects_to_hr_dashboard(
        self,
        recruiter_client: httpx.AsyncClient,
        recruiter_user: User,
    ):
        response = await recruiter_client.get("/dashboard", follow_redirects=False)
        assert response.status_code == 302
        assert "/dashboard/hr" in response.headers["location"]

    async def test_hiring_manager_redirects_to_hm_dashboard(
        self,
        hiring_manager_client: httpx.AsyncClient,
        hiring_manager_user: User,
    ):
        response = await hiring_manager_client.get("/dashboard", follow_redirects=False)
        assert response.status_code == 302
        assert "/dashboard/hiring-manager" in response.headers["location"]

    async def test_interviewer_redirects_to_interviewer_dashboard(
        self,
        interviewer_client: httpx.AsyncClient,
        interviewer_user: User,
    ):
        response = await interviewer_client.get("/dashboard", follow_redirects=False)
        assert response.status_code == 302
        assert "/dashboard/interviewer" in response.headers["location"]


# ---------------------------------------------------------------------------
# Unauthenticated Access Tests
# ---------------------------------------------------------------------------


class TestDashboardUnauthenticated:
    async def test_hr_dashboard_requires_auth(
        self,
        client: httpx.AsyncClient,
    ):
        response = await client.get("/dashboard/hr", follow_redirects=False)
        assert response.status_code in (401, 403)

    async def test_hm_dashboard_requires_auth(
        self,
        client: httpx.AsyncClient,
    ):
        response = await client.get("/dashboard/hiring-manager", follow_redirects=False)
        assert response.status_code in (401, 403)

    async def test_interviewer_dashboard_requires_auth(
        self,
        client: httpx.AsyncClient,
    ):
        response = await client.get("/dashboard/interviewer", follow_redirects=False)
        assert response.status_code in (401, 403)

    async def test_dashboard_redirect_requires_auth(
        self,
        client: httpx.AsyncClient,
    ):
        response = await client.get("/dashboard", follow_redirects=False)
        assert response.status_code in (401, 403)