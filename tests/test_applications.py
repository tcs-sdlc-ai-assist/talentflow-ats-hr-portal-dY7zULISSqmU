import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.application import Application
from app.models.candidate import Candidate
from app.models.job import Job
from app.models.audit_log import AuditLog
from app.models.user import User
from sqlalchemy import select


@pytest_asyncio.fixture
async def sample_candidate(db_session: AsyncSession) -> Candidate:
    candidate = Candidate(
        first_name="Jane",
        last_name="Doe",
        email="jane.doe@example.com",
        phone="+1234567890",
        resume_text="Experienced software engineer with 5 years of Python development.",
        linkedin_url="https://linkedin.com/in/janedoe",
    )
    db_session.add(candidate)
    await db_session.flush()
    await db_session.refresh(candidate)
    return candidate


@pytest_asyncio.fixture
async def sample_candidate_2(db_session: AsyncSession) -> Candidate:
    candidate = Candidate(
        first_name="John",
        last_name="Smith",
        email="john.smith@example.com",
        phone="+0987654321",
        resume_text="Full-stack developer with React and Node.js experience.",
    )
    db_session.add(candidate)
    await db_session.flush()
    await db_session.refresh(candidate)
    return candidate


@pytest_asyncio.fixture
async def sample_job(db_session: AsyncSession, admin_user: User) -> Job:
    job = Job(
        title="Senior Backend Engineer",
        department="Engineering",
        location="Remote",
        job_type="Full-Time",
        salary_min=120000,
        salary_max=160000,
        description="Lead backend development for our core platform.",
        status="Published",
        owner_id=admin_user.id,
    )
    db_session.add(job)
    await db_session.flush()
    await db_session.refresh(job)
    return job


@pytest_asyncio.fixture
async def sample_job_2(db_session: AsyncSession, admin_user: User) -> Job:
    job = Job(
        title="Frontend Developer",
        department="Engineering",
        location="New York, NY",
        job_type="Full-Time",
        salary_min=100000,
        salary_max=140000,
        description="Build beautiful user interfaces.",
        status="Published",
        owner_id=admin_user.id,
    )
    db_session.add(job)
    await db_session.flush()
    await db_session.refresh(job)
    return job


@pytest_asyncio.fixture
async def sample_application(
    db_session: AsyncSession,
    sample_candidate: Candidate,
    sample_job: Job,
) -> Application:
    application = Application(
        candidate_id=sample_candidate.id,
        job_id=sample_job.id,
        status="Applied",
    )
    db_session.add(application)
    await db_session.flush()
    await db_session.refresh(application)
    return application


class TestCreateApplication:
    async def test_create_application_success(
        self,
        admin_client: AsyncClient,
        sample_candidate: Candidate,
        sample_job: Job,
    ):
        response = await admin_client.post(
            "/applications/create",
            data={
                "candidate_id": sample_candidate.id,
                "job_id": sample_job.id,
            },
            follow_redirects=False,
        )
        assert response.status_code == 302
        assert "/applications/" in response.headers["location"]

    async def test_create_application_redirects_to_detail(
        self,
        admin_client: AsyncClient,
        sample_candidate: Candidate,
        sample_job: Job,
        db_session: AsyncSession,
    ):
        response = await admin_client.post(
            "/applications/create",
            data={
                "candidate_id": sample_candidate.id,
                "job_id": sample_job.id,
            },
            follow_redirects=False,
        )
        assert response.status_code == 302

        result = await db_session.execute(
            select(Application).where(
                Application.candidate_id == sample_candidate.id,
                Application.job_id == sample_job.id,
            )
        )
        application = result.scalar_one_or_none()
        assert application is not None
        assert application.status == "Applied"

    async def test_create_application_duplicate_returns_error(
        self,
        admin_client: AsyncClient,
        sample_candidate: Candidate,
        sample_job: Job,
        sample_application: Application,
    ):
        response = await admin_client.post(
            "/applications/create",
            data={
                "candidate_id": sample_candidate.id,
                "job_id": sample_job.id,
            },
            follow_redirects=False,
        )
        assert response.status_code == 400

    async def test_create_application_missing_candidate(
        self,
        admin_client: AsyncClient,
        sample_job: Job,
    ):
        response = await admin_client.post(
            "/applications/create",
            data={
                "candidate_id": "",
                "job_id": sample_job.id,
            },
            follow_redirects=False,
        )
        assert response.status_code == 400

    async def test_create_application_missing_job(
        self,
        admin_client: AsyncClient,
        sample_candidate: Candidate,
    ):
        response = await admin_client.post(
            "/applications/create",
            data={
                "candidate_id": sample_candidate.id,
                "job_id": "",
            },
            follow_redirects=False,
        )
        assert response.status_code == 400

    async def test_create_application_nonexistent_candidate(
        self,
        admin_client: AsyncClient,
        sample_job: Job,
    ):
        response = await admin_client.post(
            "/applications/create",
            data={
                "candidate_id": "nonexistent-id-12345",
                "job_id": sample_job.id,
            },
            follow_redirects=False,
        )
        assert response.status_code == 400

    async def test_create_application_nonexistent_job(
        self,
        admin_client: AsyncClient,
        sample_candidate: Candidate,
    ):
        response = await admin_client.post(
            "/applications/create",
            data={
                "candidate_id": sample_candidate.id,
                "job_id": "nonexistent-job-id-12345",
            },
            follow_redirects=False,
        )
        assert response.status_code == 400

    async def test_create_application_form_page_loads(
        self,
        admin_client: AsyncClient,
    ):
        response = await admin_client.get("/applications/create")
        assert response.status_code == 200
        assert "Create New Application" in response.text

    async def test_create_application_form_with_job_id_preselected(
        self,
        admin_client: AsyncClient,
        sample_job: Job,
    ):
        response = await admin_client.get(
            f"/applications/create?job_id={sample_job.id}"
        )
        assert response.status_code == 200
        assert sample_job.id in response.text


class TestApplicationList:
    async def test_list_applications_empty(
        self,
        admin_client: AsyncClient,
    ):
        response = await admin_client.get("/applications")
        assert response.status_code == 200
        assert "Applications" in response.text

    async def test_list_applications_with_data(
        self,
        admin_client: AsyncClient,
        sample_application: Application,
        sample_candidate: Candidate,
        sample_job: Job,
    ):
        response = await admin_client.get("/applications")
        assert response.status_code == 200
        assert sample_candidate.first_name in response.text
        assert sample_job.title in response.text

    async def test_list_applications_filter_by_status(
        self,
        admin_client: AsyncClient,
        sample_application: Application,
    ):
        response = await admin_client.get("/applications?status=Applied")
        assert response.status_code == 200
        assert "Applied" in response.text

    async def test_list_applications_filter_by_status_no_results(
        self,
        admin_client: AsyncClient,
        sample_application: Application,
    ):
        response = await admin_client.get("/applications?status=Hired")
        assert response.status_code == 200
        assert "No applications found" in response.text or "Hired" in response.text


class TestApplicationDetail:
    async def test_view_application_detail(
        self,
        admin_client: AsyncClient,
        sample_application: Application,
        sample_candidate: Candidate,
        sample_job: Job,
    ):
        response = await admin_client.get(
            f"/applications/{sample_application.id}"
        )
        assert response.status_code == 200
        assert sample_candidate.first_name in response.text
        assert sample_job.title in response.text
        assert "Applied" in response.text

    async def test_view_nonexistent_application_redirects(
        self,
        admin_client: AsyncClient,
    ):
        response = await admin_client.get(
            "/applications/nonexistent-id-12345",
            follow_redirects=False,
        )
        assert response.status_code == 302
        assert response.headers["location"] == "/applications"


class TestApplicationStatusChange:
    async def test_change_status_applied_to_screening(
        self,
        admin_client: AsyncClient,
        sample_application: Application,
        db_session: AsyncSession,
    ):
        response = await admin_client.post(
            f"/applications/{sample_application.id}/status",
            data={"status": "Screening"},
            follow_redirects=False,
        )
        assert response.status_code == 302

        await db_session.refresh(sample_application)
        assert sample_application.status == "Screening"

    async def test_change_status_screening_to_interviewing(
        self,
        admin_client: AsyncClient,
        sample_application: Application,
        db_session: AsyncSession,
    ):
        sample_application.status = "Screening"
        await db_session.flush()

        response = await admin_client.post(
            f"/applications/{sample_application.id}/status",
            data={"status": "Interviewing"},
            follow_redirects=False,
        )
        assert response.status_code == 302

        await db_session.refresh(sample_application)
        assert sample_application.status == "Interviewing"

    async def test_change_status_interviewing_to_offered(
        self,
        admin_client: AsyncClient,
        sample_application: Application,
        db_session: AsyncSession,
    ):
        sample_application.status = "Interviewing"
        await db_session.flush()

        response = await admin_client.post(
            f"/applications/{sample_application.id}/status",
            data={"status": "Offered"},
            follow_redirects=False,
        )
        assert response.status_code == 302

        await db_session.refresh(sample_application)
        assert sample_application.status == "Offered"

    async def test_change_status_offered_to_hired(
        self,
        admin_client: AsyncClient,
        sample_application: Application,
        db_session: AsyncSession,
    ):
        sample_application.status = "Offered"
        await db_session.flush()

        response = await admin_client.post(
            f"/applications/{sample_application.id}/status",
            data={"status": "Hired"},
            follow_redirects=False,
        )
        assert response.status_code == 302

        await db_session.refresh(sample_application)
        assert sample_application.status == "Hired"

    async def test_change_status_to_rejected_from_applied(
        self,
        admin_client: AsyncClient,
        sample_application: Application,
        db_session: AsyncSession,
    ):
        response = await admin_client.post(
            f"/applications/{sample_application.id}/status",
            data={"status": "Rejected"},
            follow_redirects=False,
        )
        assert response.status_code == 302

        await db_session.refresh(sample_application)
        assert sample_application.status == "Rejected"

    async def test_change_status_to_rejected_from_screening(
        self,
        admin_client: AsyncClient,
        sample_application: Application,
        db_session: AsyncSession,
    ):
        sample_application.status = "Screening"
        await db_session.flush()

        response = await admin_client.post(
            f"/applications/{sample_application.id}/status",
            data={"status": "Rejected"},
            follow_redirects=False,
        )
        assert response.status_code == 302

        await db_session.refresh(sample_application)
        assert sample_application.status == "Rejected"

    async def test_change_status_to_rejected_from_interviewing(
        self,
        admin_client: AsyncClient,
        sample_application: Application,
        db_session: AsyncSession,
    ):
        sample_application.status = "Interviewing"
        await db_session.flush()

        response = await admin_client.post(
            f"/applications/{sample_application.id}/status",
            data={"status": "Rejected"},
            follow_redirects=False,
        )
        assert response.status_code == 302

        await db_session.refresh(sample_application)
        assert sample_application.status == "Rejected"

    async def test_change_status_to_rejected_from_offered(
        self,
        admin_client: AsyncClient,
        sample_application: Application,
        db_session: AsyncSession,
    ):
        sample_application.status = "Offered"
        await db_session.flush()

        response = await admin_client.post(
            f"/applications/{sample_application.id}/status",
            data={"status": "Rejected"},
            follow_redirects=False,
        )
        assert response.status_code == 302

        await db_session.refresh(sample_application)
        assert sample_application.status == "Rejected"

    async def test_invalid_transition_applied_to_hired(
        self,
        admin_client: AsyncClient,
        sample_application: Application,
        db_session: AsyncSession,
    ):
        response = await admin_client.post(
            f"/applications/{sample_application.id}/status",
            data={"status": "Hired"},
            follow_redirects=False,
        )
        assert response.status_code == 302

        await db_session.refresh(sample_application)
        assert sample_application.status == "Applied"

    async def test_invalid_transition_applied_to_offered(
        self,
        admin_client: AsyncClient,
        sample_application: Application,
        db_session: AsyncSession,
    ):
        response = await admin_client.post(
            f"/applications/{sample_application.id}/status",
            data={"status": "Offered"},
            follow_redirects=False,
        )
        assert response.status_code == 302

        await db_session.refresh(sample_application)
        assert sample_application.status == "Applied"

    async def test_invalid_transition_applied_to_interviewing(
        self,
        admin_client: AsyncClient,
        sample_application: Application,
        db_session: AsyncSession,
    ):
        response = await admin_client.post(
            f"/applications/{sample_application.id}/status",
            data={"status": "Interviewing"},
            follow_redirects=False,
        )
        assert response.status_code == 302

        await db_session.refresh(sample_application)
        assert sample_application.status == "Applied"

    async def test_no_transition_from_hired(
        self,
        admin_client: AsyncClient,
        sample_application: Application,
        db_session: AsyncSession,
    ):
        sample_application.status = "Hired"
        await db_session.flush()

        response = await admin_client.post(
            f"/applications/{sample_application.id}/status",
            data={"status": "Rejected"},
            follow_redirects=False,
        )
        assert response.status_code == 302

        await db_session.refresh(sample_application)
        assert sample_application.status == "Hired"

    async def test_no_transition_from_rejected(
        self,
        admin_client: AsyncClient,
        sample_application: Application,
        db_session: AsyncSession,
    ):
        sample_application.status = "Rejected"
        await db_session.flush()

        response = await admin_client.post(
            f"/applications/{sample_application.id}/status",
            data={"status": "Applied"},
            follow_redirects=False,
        )
        assert response.status_code == 302

        await db_session.refresh(sample_application)
        assert sample_application.status == "Rejected"

    async def test_full_pipeline_applied_to_hired(
        self,
        admin_client: AsyncClient,
        sample_application: Application,
        db_session: AsyncSession,
    ):
        stages = ["Screening", "Interviewing", "Offered", "Hired"]
        for stage in stages:
            response = await admin_client.post(
                f"/applications/{sample_application.id}/status",
                data={"status": stage},
                follow_redirects=False,
            )
            assert response.status_code == 302
            await db_session.refresh(sample_application)
            assert sample_application.status == stage


class TestPipelineKanbanView:
    async def test_pipeline_view_loads(
        self,
        admin_client: AsyncClient,
        sample_job: Job,
    ):
        response = await admin_client.get(f"/jobs/{sample_job.id}/pipeline")
        assert response.status_code == 200
        assert "Application Pipeline" in response.text

    async def test_pipeline_view_shows_stages(
        self,
        admin_client: AsyncClient,
        sample_job: Job,
    ):
        response = await admin_client.get(f"/jobs/{sample_job.id}/pipeline")
        assert response.status_code == 200
        assert "Applied" in response.text
        assert "Screening" in response.text
        assert "Interviewing" in response.text
        assert "Offered" in response.text
        assert "Hired" in response.text
        assert "Rejected" in response.text

    async def test_pipeline_view_groups_applications_by_stage(
        self,
        admin_client: AsyncClient,
        sample_job: Job,
        sample_application: Application,
        sample_candidate: Candidate,
    ):
        response = await admin_client.get(f"/jobs/{sample_job.id}/pipeline")
        assert response.status_code == 200
        assert sample_candidate.first_name in response.text

    async def test_pipeline_view_with_multiple_applications(
        self,
        admin_client: AsyncClient,
        sample_job: Job,
        sample_candidate: Candidate,
        sample_candidate_2: Candidate,
        db_session: AsyncSession,
    ):
        app1 = Application(
            candidate_id=sample_candidate.id,
            job_id=sample_job.id,
            status="Applied",
        )
        app2 = Application(
            candidate_id=sample_candidate_2.id,
            job_id=sample_job.id,
            status="Screening",
        )
        db_session.add(app1)
        db_session.add(app2)
        await db_session.flush()

        response = await admin_client.get(f"/jobs/{sample_job.id}/pipeline")
        assert response.status_code == 200
        assert sample_candidate.first_name in response.text
        assert sample_candidate_2.first_name in response.text

    async def test_pipeline_view_nonexistent_job_redirects(
        self,
        admin_client: AsyncClient,
    ):
        response = await admin_client.get(
            "/jobs/nonexistent-job-id/pipeline",
            follow_redirects=False,
        )
        assert response.status_code == 302
        assert response.headers["location"] == "/jobs"

    async def test_pipeline_stats_counts(
        self,
        admin_client: AsyncClient,
        sample_job: Job,
        sample_candidate: Candidate,
        sample_candidate_2: Candidate,
        db_session: AsyncSession,
    ):
        app1 = Application(
            candidate_id=sample_candidate.id,
            job_id=sample_job.id,
            status="Applied",
        )
        app2 = Application(
            candidate_id=sample_candidate_2.id,
            job_id=sample_job.id,
            status="Applied",
        )
        db_session.add(app1)
        db_session.add(app2)
        await db_session.flush()

        response = await admin_client.get(f"/jobs/{sample_job.id}/pipeline")
        assert response.status_code == 200
        assert "2" in response.text


class TestApplicationRBAC:
    async def test_interviewer_cannot_create_application(
        self,
        interviewer_client: AsyncClient,
        sample_candidate: Candidate,
        sample_job: Job,
    ):
        response = await interviewer_client.post(
            "/applications/create",
            data={
                "candidate_id": sample_candidate.id,
                "job_id": sample_job.id,
            },
            follow_redirects=False,
        )
        assert response.status_code == 302
        assert response.headers["location"] == "/applications"

    async def test_interviewer_cannot_change_status(
        self,
        interviewer_client: AsyncClient,
        sample_application: Application,
        db_session: AsyncSession,
    ):
        response = await interviewer_client.post(
            f"/applications/{sample_application.id}/status",
            data={"status": "Screening"},
            follow_redirects=False,
        )
        assert response.status_code == 302

        await db_session.refresh(sample_application)
        assert sample_application.status == "Applied"

    async def test_interviewer_can_view_application_list(
        self,
        interviewer_client: AsyncClient,
        sample_application: Application,
    ):
        response = await interviewer_client.get("/applications")
        assert response.status_code == 200

    async def test_interviewer_can_view_application_detail(
        self,
        interviewer_client: AsyncClient,
        sample_application: Application,
    ):
        response = await interviewer_client.get(
            f"/applications/{sample_application.id}"
        )
        assert response.status_code == 200

    async def test_interviewer_cannot_access_create_form(
        self,
        interviewer_client: AsyncClient,
    ):
        response = await interviewer_client.get(
            "/applications/create",
            follow_redirects=False,
        )
        assert response.status_code == 302
        assert response.headers["location"] == "/applications"

    async def test_recruiter_can_create_application(
        self,
        recruiter_client: AsyncClient,
        sample_candidate: Candidate,
        sample_job: Job,
    ):
        response = await recruiter_client.post(
            "/applications/create",
            data={
                "candidate_id": sample_candidate.id,
                "job_id": sample_job.id,
            },
            follow_redirects=False,
        )
        assert response.status_code == 302
        assert "/applications/" in response.headers["location"]

    async def test_recruiter_can_change_status(
        self,
        recruiter_client: AsyncClient,
        sample_application: Application,
        db_session: AsyncSession,
    ):
        response = await recruiter_client.post(
            f"/applications/{sample_application.id}/status",
            data={"status": "Screening"},
            follow_redirects=False,
        )
        assert response.status_code == 302

        await db_session.refresh(sample_application)
        assert sample_application.status == "Screening"

    async def test_hiring_manager_can_create_application(
        self,
        hiring_manager_client: AsyncClient,
        sample_candidate: Candidate,
        sample_job: Job,
    ):
        response = await hiring_manager_client.post(
            "/applications/create",
            data={
                "candidate_id": sample_candidate.id,
                "job_id": sample_job.id,
            },
            follow_redirects=False,
        )
        assert response.status_code == 302
        assert "/applications/" in response.headers["location"]

    async def test_hiring_manager_can_change_status(
        self,
        hiring_manager_client: AsyncClient,
        sample_application: Application,
        db_session: AsyncSession,
    ):
        response = await hiring_manager_client.post(
            f"/applications/{sample_application.id}/status",
            data={"status": "Screening"},
            follow_redirects=False,
        )
        assert response.status_code == 302

        await db_session.refresh(sample_application)
        assert sample_application.status == "Screening"

    async def test_unauthenticated_user_cannot_access_applications(
        self,
        client: AsyncClient,
    ):
        response = await client.get(
            "/applications",
            follow_redirects=False,
        )
        assert response.status_code == 401 or response.status_code == 302


class TestApplicationAuditLogging:
    async def test_create_application_creates_audit_log(
        self,
        admin_client: AsyncClient,
        sample_candidate: Candidate,
        sample_job: Job,
        db_session: AsyncSession,
    ):
        response = await admin_client.post(
            "/applications/create",
            data={
                "candidate_id": sample_candidate.id,
                "job_id": sample_job.id,
            },
            follow_redirects=False,
        )
        assert response.status_code == 302

        result = await db_session.execute(
            select(AuditLog).where(
                AuditLog.action == "Application Created"
            )
        )
        logs = list(result.scalars().all())
        assert len(logs) >= 1

        log = logs[-1]
        assert sample_candidate.id in log.details
        assert sample_job.id in log.details

    async def test_status_change_creates_audit_log(
        self,
        admin_client: AsyncClient,
        sample_application: Application,
        db_session: AsyncSession,
        admin_user: User,
    ):
        response = await admin_client.post(
            f"/applications/{sample_application.id}/status",
            data={"status": "Screening"},
            follow_redirects=False,
        )
        assert response.status_code == 302

        result = await db_session.execute(
            select(AuditLog).where(
                AuditLog.action == "Application Status Changed"
            )
        )
        logs = list(result.scalars().all())
        assert len(logs) >= 1

        log = logs[-1]
        assert "Applied" in log.details
        assert "Screening" in log.details
        assert sample_application.id in log.details
        assert log.user_id == admin_user.id

    async def test_multiple_status_changes_create_multiple_audit_logs(
        self,
        admin_client: AsyncClient,
        sample_application: Application,
        db_session: AsyncSession,
    ):
        await admin_client.post(
            f"/applications/{sample_application.id}/status",
            data={"status": "Screening"},
            follow_redirects=False,
        )
        await admin_client.post(
            f"/applications/{sample_application.id}/status",
            data={"status": "Interviewing"},
            follow_redirects=False,
        )

        result = await db_session.execute(
            select(AuditLog).where(
                AuditLog.action == "Application Status Changed"
            )
        )
        logs = list(result.scalars().all())
        assert len(logs) >= 2

    async def test_invalid_status_change_does_not_create_audit_log(
        self,
        admin_client: AsyncClient,
        sample_application: Application,
        db_session: AsyncSession,
    ):
        result_before = await db_session.execute(
            select(AuditLog).where(
                AuditLog.action == "Application Status Changed"
            )
        )
        count_before = len(list(result_before.scalars().all()))

        await admin_client.post(
            f"/applications/{sample_application.id}/status",
            data={"status": "Hired"},
            follow_redirects=False,
        )

        result_after = await db_session.execute(
            select(AuditLog).where(
                AuditLog.action == "Application Status Changed"
            )
        )
        count_after = len(list(result_after.scalars().all()))

        assert count_after == count_before


class TestApplicationServiceLogic:
    async def test_application_initial_status_is_applied(
        self,
        admin_client: AsyncClient,
        sample_candidate: Candidate,
        sample_job: Job,
        db_session: AsyncSession,
    ):
        await admin_client.post(
            "/applications/create",
            data={
                "candidate_id": sample_candidate.id,
                "job_id": sample_job.id,
            },
            follow_redirects=False,
        )

        result = await db_session.execute(
            select(Application).where(
                Application.candidate_id == sample_candidate.id,
                Application.job_id == sample_job.id,
            )
        )
        application = result.scalar_one_or_none()
        assert application is not None
        assert application.status == "Applied"
        assert application.applied_at is not None

    async def test_application_unique_constraint_candidate_job(
        self,
        admin_client: AsyncClient,
        sample_candidate: Candidate,
        sample_job: Job,
        sample_application: Application,
    ):
        response = await admin_client.post(
            "/applications/create",
            data={
                "candidate_id": sample_candidate.id,
                "job_id": sample_job.id,
            },
            follow_redirects=False,
        )
        assert response.status_code == 400

    async def test_candidate_can_apply_to_multiple_jobs(
        self,
        admin_client: AsyncClient,
        sample_candidate: Candidate,
        sample_job: Job,
        sample_job_2: Job,
        db_session: AsyncSession,
    ):
        response1 = await admin_client.post(
            "/applications/create",
            data={
                "candidate_id": sample_candidate.id,
                "job_id": sample_job.id,
            },
            follow_redirects=False,
        )
        assert response1.status_code == 302

        response2 = await admin_client.post(
            "/applications/create",
            data={
                "candidate_id": sample_candidate.id,
                "job_id": sample_job_2.id,
            },
            follow_redirects=False,
        )
        assert response2.status_code == 302

        result = await db_session.execute(
            select(Application).where(
                Application.candidate_id == sample_candidate.id,
            )
        )
        applications = list(result.scalars().all())
        assert len(applications) == 2

    async def test_multiple_candidates_can_apply_to_same_job(
        self,
        admin_client: AsyncClient,
        sample_candidate: Candidate,
        sample_candidate_2: Candidate,
        sample_job: Job,
        db_session: AsyncSession,
    ):
        response1 = await admin_client.post(
            "/applications/create",
            data={
                "candidate_id": sample_candidate.id,
                "job_id": sample_job.id,
            },
            follow_redirects=False,
        )
        assert response1.status_code == 302

        response2 = await admin_client.post(
            "/applications/create",
            data={
                "candidate_id": sample_candidate_2.id,
                "job_id": sample_job.id,
            },
            follow_redirects=False,
        )
        assert response2.status_code == 302

        result = await db_session.execute(
            select(Application).where(
                Application.job_id == sample_job.id,
            )
        )
        applications = list(result.scalars().all())
        assert len(applications) == 2