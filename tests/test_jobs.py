import pytest
import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.job import Job
from app.models.user import User


@pytest.mark.asyncio
async def test_job_list_requires_auth(client: httpx.AsyncClient):
    response = await client.get("/jobs", follow_redirects=False)
    assert response.status_code == 401 or response.status_code == 302


@pytest.mark.asyncio
async def test_job_list_authenticated(admin_client: httpx.AsyncClient):
    response = await admin_client.get("/jobs", follow_redirects=False)
    assert response.status_code == 200
    assert b"Job Requisitions" in response.content


@pytest.mark.asyncio
async def test_create_job_form_accessible_by_admin(admin_client: httpx.AsyncClient):
    response = await admin_client.get("/jobs/create", follow_redirects=False)
    assert response.status_code == 200
    assert b"Create" in response.content


@pytest.mark.asyncio
async def test_create_job_form_accessible_by_recruiter(recruiter_client: httpx.AsyncClient):
    response = await recruiter_client.get("/jobs/create", follow_redirects=False)
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_create_job_form_accessible_by_hiring_manager(hiring_manager_client: httpx.AsyncClient):
    response = await hiring_manager_client.get("/jobs/create", follow_redirects=False)
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_create_job_form_redirects_for_interviewer(interviewer_client: httpx.AsyncClient):
    response = await interviewer_client.get("/jobs/create", follow_redirects=False)
    assert response.status_code == 302
    assert "/jobs" in response.headers.get("location", "")


@pytest.mark.asyncio
async def test_create_job_success(admin_client: httpx.AsyncClient):
    response = await admin_client.post(
        "/jobs/create",
        data={
            "title": "Senior Backend Engineer",
            "department": "Engineering",
            "location": "Remote",
            "job_type": "Full-Time",
            "salary_min": "120000",
            "salary_max": "160000",
            "description": "Lead backend development for our platform.",
        },
        follow_redirects=False,
    )
    assert response.status_code == 302
    location = response.headers.get("location", "")
    assert location.startswith("/jobs/")


@pytest.mark.asyncio
async def test_create_job_validation_errors(admin_client: httpx.AsyncClient):
    response = await admin_client.post(
        "/jobs/create",
        data={
            "title": "",
            "department": "",
            "location": "",
            "job_type": "",
            "salary_min": "",
            "salary_max": "",
            "description": "",
        },
        follow_redirects=False,
    )
    assert response.status_code == 400
    assert b"Job title is required" in response.content


@pytest.mark.asyncio
async def test_create_job_salary_min_exceeds_max(admin_client: httpx.AsyncClient):
    response = await admin_client.post(
        "/jobs/create",
        data={
            "title": "Test Job",
            "department": "Engineering",
            "location": "Remote",
            "job_type": "Full-Time",
            "salary_min": "200000",
            "salary_max": "100000",
            "description": "A test job description for validation.",
        },
        follow_redirects=False,
    )
    assert response.status_code == 400
    assert b"Minimum salary cannot exceed maximum salary" in response.content


@pytest.mark.asyncio
async def test_view_job_detail(
    admin_client: httpx.AsyncClient,
    db_session: AsyncSession,
    admin_user: User,
):
    job = Job(
        title="QA Engineer",
        department="Quality",
        location="New York",
        job_type="Full-Time",
        salary_min=80000,
        salary_max=110000,
        description="Quality assurance role.",
        status="Draft",
        owner_id=admin_user.id,
    )
    db_session.add(job)
    await db_session.flush()
    await db_session.refresh(job)

    response = await admin_client.get(f"/jobs/{job.id}", follow_redirects=False)
    assert response.status_code == 200
    assert b"QA Engineer" in response.content
    assert b"Quality" in response.content


@pytest.mark.asyncio
async def test_view_nonexistent_job_redirects(admin_client: httpx.AsyncClient):
    response = await admin_client.get("/jobs/nonexistent-id-12345", follow_redirects=False)
    assert response.status_code == 302
    assert "/jobs" in response.headers.get("location", "")


@pytest.mark.asyncio
async def test_edit_job_form(
    admin_client: httpx.AsyncClient,
    db_session: AsyncSession,
    admin_user: User,
):
    job = Job(
        title="DevOps Engineer",
        department="Infrastructure",
        location="Remote",
        job_type="Full-Time",
        salary_min=100000,
        salary_max=140000,
        description="DevOps role.",
        status="Draft",
        owner_id=admin_user.id,
    )
    db_session.add(job)
    await db_session.flush()
    await db_session.refresh(job)

    response = await admin_client.get(f"/jobs/{job.id}/edit", follow_redirects=False)
    assert response.status_code == 200
    assert b"DevOps Engineer" in response.content


@pytest.mark.asyncio
async def test_edit_job_submit(
    admin_client: httpx.AsyncClient,
    db_session: AsyncSession,
    admin_user: User,
):
    job = Job(
        title="Original Title",
        department="Engineering",
        location="Remote",
        job_type="Full-Time",
        salary_min=90000,
        salary_max=130000,
        description="Original description.",
        status="Draft",
        owner_id=admin_user.id,
    )
    db_session.add(job)
    await db_session.flush()
    await db_session.refresh(job)

    response = await admin_client.post(
        f"/jobs/{job.id}/edit",
        data={
            "title": "Updated Title",
            "department": "Product",
            "location": "San Francisco",
            "job_type": "Contract",
            "salary_min": "95000",
            "salary_max": "135000",
            "description": "Updated description for the role.",
        },
        follow_redirects=False,
    )
    assert response.status_code == 302
    assert f"/jobs/{job.id}" in response.headers.get("location", "")


@pytest.mark.asyncio
async def test_status_change_draft_to_published(
    admin_client: httpx.AsyncClient,
    db_session: AsyncSession,
    admin_user: User,
):
    job = Job(
        title="Status Test Job",
        department="Engineering",
        location="Remote",
        job_type="Full-Time",
        salary_min=100000,
        salary_max=150000,
        description="Testing status transitions.",
        status="Draft",
        owner_id=admin_user.id,
    )
    db_session.add(job)
    await db_session.flush()
    await db_session.refresh(job)

    response = await admin_client.post(
        f"/jobs/{job.id}/status",
        data={"status": "Published"},
        follow_redirects=False,
    )
    assert response.status_code == 302

    await db_session.refresh(job)
    assert job.status == "Published"


@pytest.mark.asyncio
async def test_status_change_published_to_closed(
    admin_client: httpx.AsyncClient,
    db_session: AsyncSession,
    admin_user: User,
):
    job = Job(
        title="Close Test Job",
        department="Engineering",
        location="Remote",
        job_type="Full-Time",
        salary_min=100000,
        salary_max=150000,
        description="Testing close transition.",
        status="Published",
        owner_id=admin_user.id,
    )
    db_session.add(job)
    await db_session.flush()
    await db_session.refresh(job)

    response = await admin_client.post(
        f"/jobs/{job.id}/status",
        data={"status": "Closed"},
        follow_redirects=False,
    )
    assert response.status_code == 302

    await db_session.refresh(job)
    assert job.status == "Closed"


@pytest.mark.asyncio
async def test_status_change_closed_to_draft(
    admin_client: httpx.AsyncClient,
    db_session: AsyncSession,
    admin_user: User,
):
    job = Job(
        title="Reopen Test Job",
        department="Engineering",
        location="Remote",
        job_type="Full-Time",
        salary_min=100000,
        salary_max=150000,
        description="Testing reopen transition.",
        status="Closed",
        owner_id=admin_user.id,
    )
    db_session.add(job)
    await db_session.flush()
    await db_session.refresh(job)

    response = await admin_client.post(
        f"/jobs/{job.id}/status",
        data={"status": "Draft"},
        follow_redirects=False,
    )
    assert response.status_code == 302

    await db_session.refresh(job)
    assert job.status == "Draft"


@pytest.mark.asyncio
async def test_status_change_invalid_status_ignored(
    admin_client: httpx.AsyncClient,
    db_session: AsyncSession,
    admin_user: User,
):
    job = Job(
        title="Invalid Status Job",
        department="Engineering",
        location="Remote",
        job_type="Full-Time",
        salary_min=100000,
        salary_max=150000,
        description="Testing invalid status.",
        status="Draft",
        owner_id=admin_user.id,
    )
    db_session.add(job)
    await db_session.flush()
    await db_session.refresh(job)

    response = await admin_client.post(
        f"/jobs/{job.id}/status",
        data={"status": "InvalidStatus"},
        follow_redirects=False,
    )
    assert response.status_code == 302

    await db_session.refresh(job)
    assert job.status == "Draft"


@pytest.mark.asyncio
async def test_interviewer_cannot_create_job(interviewer_client: httpx.AsyncClient):
    response = await interviewer_client.post(
        "/jobs/create",
        data={
            "title": "Unauthorized Job",
            "department": "Engineering",
            "location": "Remote",
            "job_type": "Full-Time",
            "salary_min": "100000",
            "salary_max": "150000",
            "description": "Should not be created.",
        },
        follow_redirects=False,
    )
    assert response.status_code == 302
    assert "/jobs" in response.headers.get("location", "")


@pytest.mark.asyncio
async def test_interviewer_cannot_edit_job(
    interviewer_client: httpx.AsyncClient,
    db_session: AsyncSession,
    admin_user: User,
):
    job = Job(
        title="Protected Job",
        department="Engineering",
        location="Remote",
        job_type="Full-Time",
        salary_min=100000,
        salary_max=150000,
        description="Protected from interviewers.",
        status="Draft",
        owner_id=admin_user.id,
    )
    db_session.add(job)
    await db_session.flush()
    await db_session.refresh(job)

    response = await interviewer_client.get(f"/jobs/{job.id}/edit", follow_redirects=False)
    assert response.status_code == 302


@pytest.mark.asyncio
async def test_interviewer_cannot_change_status(
    interviewer_client: httpx.AsyncClient,
    db_session: AsyncSession,
    admin_user: User,
):
    job = Job(
        title="Status Protected Job",
        department="Engineering",
        location="Remote",
        job_type="Full-Time",
        salary_min=100000,
        salary_max=150000,
        description="Status protected from interviewers.",
        status="Draft",
        owner_id=admin_user.id,
    )
    db_session.add(job)
    await db_session.flush()
    await db_session.refresh(job)

    response = await interviewer_client.post(
        f"/jobs/{job.id}/status",
        data={"status": "Published"},
        follow_redirects=False,
    )
    assert response.status_code == 302

    await db_session.refresh(job)
    assert job.status == "Draft"


@pytest.mark.asyncio
async def test_hiring_manager_can_edit_own_job(
    hiring_manager_client: httpx.AsyncClient,
    db_session: AsyncSession,
    hiring_manager_user: User,
):
    job = Job(
        title="HM Own Job",
        department="Product",
        location="Remote",
        job_type="Full-Time",
        salary_min=90000,
        salary_max=130000,
        description="Hiring manager's own job.",
        status="Draft",
        owner_id=hiring_manager_user.id,
    )
    db_session.add(job)
    await db_session.flush()
    await db_session.refresh(job)

    response = await hiring_manager_client.get(f"/jobs/{job.id}/edit", follow_redirects=False)
    assert response.status_code == 200

    response = await hiring_manager_client.post(
        f"/jobs/{job.id}/edit",
        data={
            "title": "HM Updated Job",
            "department": "Product",
            "location": "Remote",
            "job_type": "Full-Time",
            "salary_min": "95000",
            "salary_max": "135000",
            "description": "Updated by hiring manager.",
        },
        follow_redirects=False,
    )
    assert response.status_code == 302
    assert f"/jobs/{job.id}" in response.headers.get("location", "")


@pytest.mark.asyncio
async def test_hiring_manager_cannot_edit_others_job(
    hiring_manager_client: httpx.AsyncClient,
    db_session: AsyncSession,
    admin_user: User,
):
    job = Job(
        title="Admin's Job",
        department="Engineering",
        location="Remote",
        job_type="Full-Time",
        salary_min=100000,
        salary_max=150000,
        description="Owned by admin, not hiring manager.",
        status="Draft",
        owner_id=admin_user.id,
    )
    db_session.add(job)
    await db_session.flush()
    await db_session.refresh(job)

    response = await hiring_manager_client.get(f"/jobs/{job.id}/edit", follow_redirects=False)
    assert response.status_code == 302


@pytest.mark.asyncio
async def test_hiring_manager_cannot_change_status_of_others_job(
    hiring_manager_client: httpx.AsyncClient,
    db_session: AsyncSession,
    admin_user: User,
):
    job = Job(
        title="Admin Status Job",
        department="Engineering",
        location="Remote",
        job_type="Full-Time",
        salary_min=100000,
        salary_max=150000,
        description="Admin's job for status test.",
        status="Draft",
        owner_id=admin_user.id,
    )
    db_session.add(job)
    await db_session.flush()
    await db_session.refresh(job)

    response = await hiring_manager_client.post(
        f"/jobs/{job.id}/status",
        data={"status": "Published"},
        follow_redirects=False,
    )
    assert response.status_code == 302

    await db_session.refresh(job)
    assert job.status == "Draft"


@pytest.mark.asyncio
async def test_hiring_manager_can_change_status_of_own_job(
    hiring_manager_client: httpx.AsyncClient,
    db_session: AsyncSession,
    hiring_manager_user: User,
):
    job = Job(
        title="HM Status Job",
        department="Product",
        location="Remote",
        job_type="Full-Time",
        salary_min=90000,
        salary_max=130000,
        description="HM's job for status test.",
        status="Draft",
        owner_id=hiring_manager_user.id,
    )
    db_session.add(job)
    await db_session.flush()
    await db_session.refresh(job)

    response = await hiring_manager_client.post(
        f"/jobs/{job.id}/status",
        data={"status": "Published"},
        follow_redirects=False,
    )
    assert response.status_code == 302

    await db_session.refresh(job)
    assert job.status == "Published"


@pytest.mark.asyncio
async def test_recruiter_full_access_create_and_edit(
    recruiter_client: httpx.AsyncClient,
    db_session: AsyncSession,
    recruiter_user: User,
):
    response = await recruiter_client.post(
        "/jobs/create",
        data={
            "title": "Recruiter Created Job",
            "department": "Sales",
            "location": "Chicago",
            "job_type": "Full-Time",
            "salary_min": "70000",
            "salary_max": "100000",
            "description": "Created by recruiter.",
        },
        follow_redirects=False,
    )
    assert response.status_code == 302
    location = response.headers.get("location", "")
    assert location.startswith("/jobs/")

    job_id = location.split("/jobs/")[1]

    response = await recruiter_client.get(f"/jobs/{job_id}/edit", follow_redirects=False)
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_published_jobs_appear_on_landing_page(
    client: httpx.AsyncClient,
    db_session: AsyncSession,
    admin_user: User,
):
    published_job = Job(
        title="Public Visible Job",
        department="Marketing",
        location="London",
        job_type="Full-Time",
        salary_min=60000,
        salary_max=90000,
        description="This job should appear on the landing page.",
        status="Published",
        owner_id=admin_user.id,
    )
    db_session.add(published_job)

    draft_job = Job(
        title="Hidden Draft Job",
        department="Engineering",
        location="Remote",
        job_type="Full-Time",
        salary_min=100000,
        salary_max=150000,
        description="This job should NOT appear on the landing page.",
        status="Draft",
        owner_id=admin_user.id,
    )
    db_session.add(draft_job)
    await db_session.flush()

    response = await client.get("/", follow_redirects=False)
    assert response.status_code == 200
    assert b"Public Visible Job" in response.content
    assert b"Hidden Draft Job" not in response.content


@pytest.mark.asyncio
async def test_closed_jobs_not_on_landing_page(
    client: httpx.AsyncClient,
    db_session: AsyncSession,
    admin_user: User,
):
    closed_job = Job(
        title="Closed Position",
        department="Finance",
        location="Boston",
        job_type="Full-Time",
        salary_min=80000,
        salary_max=120000,
        description="This closed job should not appear publicly.",
        status="Closed",
        owner_id=admin_user.id,
    )
    db_session.add(closed_job)
    await db_session.flush()

    response = await client.get("/", follow_redirects=False)
    assert response.status_code == 200
    assert b"Closed Position" not in response.content


@pytest.mark.asyncio
async def test_job_list_filter_by_status(
    admin_client: httpx.AsyncClient,
    db_session: AsyncSession,
    admin_user: User,
):
    published_job = Job(
        title="Published Filter Job",
        department="Engineering",
        location="Remote",
        job_type="Full-Time",
        salary_min=100000,
        salary_max=150000,
        description="Published job for filter test.",
        status="Published",
        owner_id=admin_user.id,
    )
    db_session.add(published_job)

    draft_job = Job(
        title="Draft Filter Job",
        department="Engineering",
        location="Remote",
        job_type="Full-Time",
        salary_min=100000,
        salary_max=150000,
        description="Draft job for filter test.",
        status="Draft",
        owner_id=admin_user.id,
    )
    db_session.add(draft_job)
    await db_session.flush()

    response = await admin_client.get("/jobs?status=Published", follow_redirects=False)
    assert response.status_code == 200
    assert b"Published Filter Job" in response.content
    assert b"Draft Filter Job" not in response.content


@pytest.mark.asyncio
async def test_job_list_search(
    admin_client: httpx.AsyncClient,
    db_session: AsyncSession,
    admin_user: User,
):
    job = Job(
        title="Unique Searchable Title XYZ",
        department="Engineering",
        location="Remote",
        job_type="Full-Time",
        salary_min=100000,
        salary_max=150000,
        description="A job with a unique title for search.",
        status="Draft",
        owner_id=admin_user.id,
    )
    db_session.add(job)
    await db_session.flush()

    response = await admin_client.get("/jobs?search=Unique+Searchable", follow_redirects=False)
    assert response.status_code == 200
    assert b"Unique Searchable Title XYZ" in response.content


@pytest.mark.asyncio
async def test_hiring_manager_sees_only_own_jobs(
    hiring_manager_client: httpx.AsyncClient,
    db_session: AsyncSession,
    hiring_manager_user: User,
    admin_user: User,
):
    hm_job = Job(
        title="HM Visible Job",
        department="Product",
        location="Remote",
        job_type="Full-Time",
        salary_min=90000,
        salary_max=130000,
        description="Hiring manager's job.",
        status="Draft",
        owner_id=hiring_manager_user.id,
    )
    db_session.add(hm_job)

    admin_job = Job(
        title="Admin Only Job",
        department="Engineering",
        location="Remote",
        job_type="Full-Time",
        salary_min=100000,
        salary_max=150000,
        description="Admin's job, not visible to HM in list.",
        status="Draft",
        owner_id=admin_user.id,
    )
    db_session.add(admin_job)
    await db_session.flush()

    response = await hiring_manager_client.get("/jobs", follow_redirects=False)
    assert response.status_code == 200
    assert b"HM Visible Job" in response.content
    assert b"Admin Only Job" not in response.content


@pytest.mark.asyncio
async def test_static_routes_before_dynamic_jobs_create(
    admin_client: httpx.AsyncClient,
):
    response = await admin_client.get("/jobs/create", follow_redirects=False)
    assert response.status_code == 200
    assert b"Create" in response.content or b"create" in response.content.lower()


@pytest.mark.asyncio
async def test_health_check(client: httpx.AsyncClient):
    response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"


@pytest.mark.asyncio
async def test_create_job_with_recruiter_and_verify_detail(
    recruiter_client: httpx.AsyncClient,
):
    response = await recruiter_client.post(
        "/jobs/create",
        data={
            "title": "Full Stack Developer",
            "department": "Engineering",
            "location": "Austin, TX",
            "job_type": "Full-Time",
            "salary_min": "110000",
            "salary_max": "145000",
            "description": "Build and maintain full stack applications.",
        },
        follow_redirects=False,
    )
    assert response.status_code == 302
    location = response.headers.get("location", "")
    assert location.startswith("/jobs/")

    detail_response = await recruiter_client.get(location, follow_redirects=False)
    assert detail_response.status_code == 200
    assert b"Full Stack Developer" in detail_response.content
    assert b"Austin, TX" in detail_response.content
    assert b"Draft" in detail_response.content


@pytest.mark.asyncio
async def test_pipeline_view_for_job(
    admin_client: httpx.AsyncClient,
    db_session: AsyncSession,
    admin_user: User,
):
    job = Job(
        title="Pipeline Test Job",
        department="Engineering",
        location="Remote",
        job_type="Full-Time",
        salary_min=100000,
        salary_max=150000,
        description="Job for pipeline view test.",
        status="Published",
        owner_id=admin_user.id,
    )
    db_session.add(job)
    await db_session.flush()
    await db_session.refresh(job)

    response = await admin_client.get(f"/jobs/{job.id}/pipeline", follow_redirects=False)
    assert response.status_code == 200
    assert b"Pipeline" in response.content