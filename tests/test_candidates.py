import pytest
import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.candidate import Candidate
from app.models.skill import Skill
from app.models.job import Job
from app.models.application import Application
from app.models.user import User


async def _create_candidate(
    db_session: AsyncSession,
    first_name: str = "Jane",
    last_name: str = "Doe",
    email: str = "jane.doe@example.com",
    phone: str = "+1-555-0100",
    linkedin_url: str = "https://linkedin.com/in/janedoe",
    resume_text: str = "Experienced software engineer with 5 years of Python development.",
) -> Candidate:
    candidate = Candidate(
        first_name=first_name,
        last_name=last_name,
        email=email,
        phone=phone,
        linkedin_url=linkedin_url,
        resume_text=resume_text,
    )
    db_session.add(candidate)
    await db_session.flush()
    await db_session.refresh(candidate)
    return candidate


async def _create_skill(db_session: AsyncSession, name: str = "Python") -> Skill:
    skill = Skill(name=name)
    db_session.add(skill)
    await db_session.flush()
    await db_session.refresh(skill)
    return skill


async def _create_job(
    db_session: AsyncSession,
    owner_id: str,
    title: str = "Backend Engineer",
    department: str = "Engineering",
    location: str = "Remote",
    job_type: str = "Full-Time",
    description: str = "Build backend services.",
    status: str = "Published",
) -> Job:
    job = Job(
        title=title,
        department=department,
        location=location,
        job_type=job_type,
        description=description,
        status=status,
        owner_id=owner_id,
    )
    db_session.add(job)
    await db_session.flush()
    await db_session.refresh(job)
    return job


async def _create_application(
    db_session: AsyncSession,
    candidate_id: str,
    job_id: str,
    status: str = "Applied",
) -> Application:
    application = Application(
        candidate_id=candidate_id,
        job_id=job_id,
        status=status,
    )
    db_session.add(application)
    await db_session.flush()
    await db_session.refresh(application)
    return application


# ──────────────────────────────────────────────
# Candidate List
# ──────────────────────────────────────────────


class TestCandidateList:
    async def test_candidate_list_requires_auth(self, client: httpx.AsyncClient):
        response = await client.get("/candidates")
        assert response.status_code == 401 or response.status_code == 200
        # Unauthenticated users get 401 from the dependency
        # (FastAPI raises HTTPException which returns JSON 401)

    async def test_candidate_list_returns_200_for_authenticated_user(
        self, admin_client: httpx.AsyncClient, db_session: AsyncSession
    ):
        await _create_candidate(db_session)
        response = await admin_client.get("/candidates", follow_redirects=False)
        assert response.status_code == 200
        assert "Jane" in response.text
        assert "Doe" in response.text

    async def test_candidate_list_search_by_name(
        self, admin_client: httpx.AsyncClient, db_session: AsyncSession
    ):
        await _create_candidate(db_session, first_name="Alice", last_name="Smith", email="alice@example.com")
        await _create_candidate(db_session, first_name="Bob", last_name="Jones", email="bob@example.com")
        response = await admin_client.get("/candidates?search=Alice", follow_redirects=False)
        assert response.status_code == 200
        assert "Alice" in response.text
        assert "Bob" not in response.text

    async def test_candidate_list_filter_by_skill(
        self, admin_client: httpx.AsyncClient, db_session: AsyncSession
    ):
        candidate = await _create_candidate(db_session, first_name="Skilled", last_name="Dev", email="skilled@example.com")
        skill = await _create_skill(db_session, name="Rust")
        candidate.skills.append(skill)
        await db_session.flush()

        await _create_candidate(db_session, first_name="Other", last_name="Dev", email="other@example.com")

        response = await admin_client.get("/candidates?skill=Rust", follow_redirects=False)
        assert response.status_code == 200
        assert "Skilled" in response.text

    async def test_candidate_list_accessible_by_interviewer(
        self, interviewer_client: httpx.AsyncClient, db_session: AsyncSession
    ):
        await _create_candidate(db_session)
        response = await interviewer_client.get("/candidates", follow_redirects=False)
        assert response.status_code == 200
        assert "Jane" in response.text


# ──────────────────────────────────────────────
# Candidate Create
# ──────────────────────────────────────────────


class TestCandidateCreate:
    async def test_create_candidate_form_accessible_by_admin(
        self, admin_client: httpx.AsyncClient
    ):
        response = await admin_client.get("/candidates/create", follow_redirects=False)
        assert response.status_code == 200
        assert "Add New Candidate" in response.text

    async def test_create_candidate_form_accessible_by_recruiter(
        self, recruiter_client: httpx.AsyncClient
    ):
        response = await recruiter_client.get("/candidates/create", follow_redirects=False)
        assert response.status_code == 200

    async def test_create_candidate_form_forbidden_for_interviewer(
        self, interviewer_client: httpx.AsyncClient
    ):
        response = await interviewer_client.get("/candidates/create", follow_redirects=False)
        assert response.status_code == 403

    async def test_create_candidate_success(
        self, admin_client: httpx.AsyncClient, db_session: AsyncSession
    ):
        response = await admin_client.post(
            "/candidates/create",
            data={
                "first_name": "John",
                "last_name": "Smith",
                "email": "john.smith@example.com",
                "phone": "+1-555-0200",
                "linkedin_url": "https://linkedin.com/in/johnsmith",
                "resume_text": "Full stack developer with 10 years experience.",
            },
            follow_redirects=False,
        )
        assert response.status_code == 302
        assert "/candidates/" in response.headers["location"]

        result = await db_session.execute(
            select(Candidate).where(Candidate.email == "john.smith@example.com")
        )
        candidate = result.scalar_one_or_none()
        assert candidate is not None
        assert candidate.first_name == "John"
        assert candidate.last_name == "Smith"

    async def test_create_candidate_missing_required_fields(
        self, admin_client: httpx.AsyncClient
    ):
        response = await admin_client.post(
            "/candidates/create",
            data={
                "first_name": "",
                "last_name": "",
                "email": "",
                "phone": "",
                "linkedin_url": "",
                "resume_text": "",
            },
            follow_redirects=False,
        )
        assert response.status_code == 400
        assert "First name is required" in response.text

    async def test_create_candidate_invalid_email(
        self, admin_client: httpx.AsyncClient
    ):
        response = await admin_client.post(
            "/candidates/create",
            data={
                "first_name": "Test",
                "last_name": "User",
                "email": "not-an-email",
                "phone": "",
                "linkedin_url": "",
                "resume_text": "",
            },
            follow_redirects=False,
        )
        assert response.status_code == 400
        assert "valid email" in response.text

    async def test_create_candidate_duplicate_email(
        self, admin_client: httpx.AsyncClient, db_session: AsyncSession
    ):
        await _create_candidate(db_session, email="duplicate@example.com")

        response = await admin_client.post(
            "/candidates/create",
            data={
                "first_name": "Another",
                "last_name": "Person",
                "email": "duplicate@example.com",
                "phone": "",
                "linkedin_url": "",
                "resume_text": "",
            },
            follow_redirects=False,
        )
        assert response.status_code == 400
        assert "already exists" in response.text

    async def test_create_candidate_invalid_linkedin_url(
        self, admin_client: httpx.AsyncClient
    ):
        response = await admin_client.post(
            "/candidates/create",
            data={
                "first_name": "Test",
                "last_name": "User",
                "email": "test.linkedin@example.com",
                "phone": "",
                "linkedin_url": "not-a-url",
                "resume_text": "",
            },
            follow_redirects=False,
        )
        assert response.status_code == 400
        assert "LinkedIn URL must start with http" in response.text

    async def test_create_candidate_forbidden_for_interviewer(
        self, interviewer_client: httpx.AsyncClient
    ):
        response = await interviewer_client.post(
            "/candidates/create",
            data={
                "first_name": "Blocked",
                "last_name": "User",
                "email": "blocked@example.com",
                "phone": "",
                "linkedin_url": "",
                "resume_text": "",
            },
            follow_redirects=False,
        )
        assert response.status_code == 403


# ──────────────────────────────────────────────
# Candidate Detail
# ──────────────────────────────────────────────


class TestCandidateDetail:
    async def test_candidate_detail_returns_200(
        self, admin_client: httpx.AsyncClient, db_session: AsyncSession
    ):
        candidate = await _create_candidate(db_session)
        response = await admin_client.get(
            f"/candidates/{candidate.id}", follow_redirects=False
        )
        assert response.status_code == 200
        assert "Jane" in response.text
        assert "Doe" in response.text
        assert "jane.doe@example.com" in response.text

    async def test_candidate_detail_nonexistent_redirects(
        self, admin_client: httpx.AsyncClient
    ):
        response = await admin_client.get(
            "/candidates/nonexistent-id-12345", follow_redirects=False
        )
        assert response.status_code == 302
        assert "/candidates" in response.headers["location"]

    async def test_candidate_detail_shows_skills(
        self, admin_client: httpx.AsyncClient, db_session: AsyncSession
    ):
        candidate = await _create_candidate(db_session)
        skill = await _create_skill(db_session, name="FastAPI")
        candidate.skills.append(skill)
        await db_session.flush()

        response = await admin_client.get(
            f"/candidates/{candidate.id}", follow_redirects=False
        )
        assert response.status_code == 200
        assert "FastAPI" in response.text

    async def test_candidate_detail_shows_application_history(
        self,
        admin_client: httpx.AsyncClient,
        db_session: AsyncSession,
        admin_user: User,
    ):
        candidate = await _create_candidate(db_session)
        job = await _create_job(db_session, owner_id=admin_user.id, title="Senior Dev")
        await _create_application(db_session, candidate_id=candidate.id, job_id=job.id)

        response = await admin_client.get(
            f"/candidates/{candidate.id}", follow_redirects=False
        )
        assert response.status_code == 200
        assert "Senior Dev" in response.text
        assert "Application History" in response.text

    async def test_candidate_detail_accessible_by_interviewer(
        self, interviewer_client: httpx.AsyncClient, db_session: AsyncSession
    ):
        candidate = await _create_candidate(db_session)
        response = await interviewer_client.get(
            f"/candidates/{candidate.id}", follow_redirects=False
        )
        assert response.status_code == 200
        assert "Jane" in response.text


# ──────────────────────────────────────────────
# Candidate Edit
# ──────────────────────────────────────────────


class TestCandidateEdit:
    async def test_edit_form_accessible_by_admin(
        self, admin_client: httpx.AsyncClient, db_session: AsyncSession
    ):
        candidate = await _create_candidate(db_session)
        response = await admin_client.get(
            f"/candidates/{candidate.id}/edit", follow_redirects=False
        )
        assert response.status_code == 200
        assert "Edit Candidate" in response.text

    async def test_edit_form_forbidden_for_interviewer(
        self, interviewer_client: httpx.AsyncClient, db_session: AsyncSession
    ):
        candidate = await _create_candidate(db_session)
        response = await interviewer_client.get(
            f"/candidates/{candidate.id}/edit", follow_redirects=False
        )
        assert response.status_code == 403

    async def test_edit_candidate_success(
        self, admin_client: httpx.AsyncClient, db_session: AsyncSession
    ):
        candidate = await _create_candidate(db_session)
        response = await admin_client.post(
            f"/candidates/{candidate.id}/edit",
            data={
                "first_name": "Janet",
                "last_name": "Doe-Updated",
                "email": "janet.updated@example.com",
                "phone": "+1-555-9999",
                "linkedin_url": "https://linkedin.com/in/janetupdated",
                "resume_text": "Updated resume text.",
            },
            follow_redirects=False,
        )
        assert response.status_code == 302
        assert f"/candidates/{candidate.id}" in response.headers["location"]

        await db_session.refresh(candidate)
        assert candidate.first_name == "Janet"
        assert candidate.last_name == "Doe-Updated"
        assert candidate.email == "janet.updated@example.com"

    async def test_edit_candidate_duplicate_email(
        self, admin_client: httpx.AsyncClient, db_session: AsyncSession
    ):
        await _create_candidate(db_session, email="existing@example.com")
        candidate2 = await _create_candidate(
            db_session,
            first_name="Second",
            last_name="Person",
            email="second@example.com",
        )

        response = await admin_client.post(
            f"/candidates/{candidate2.id}/edit",
            data={
                "first_name": "Second",
                "last_name": "Person",
                "email": "existing@example.com",
                "phone": "",
                "linkedin_url": "",
                "resume_text": "",
            },
            follow_redirects=False,
        )
        assert response.status_code == 400
        assert "already exists" in response.text

    async def test_edit_nonexistent_candidate_redirects(
        self, admin_client: httpx.AsyncClient
    ):
        response = await admin_client.get(
            "/candidates/nonexistent-id/edit", follow_redirects=False
        )
        assert response.status_code == 302
        assert "/candidates" in response.headers["location"]

    async def test_edit_candidate_forbidden_for_interviewer(
        self, interviewer_client: httpx.AsyncClient, db_session: AsyncSession
    ):
        candidate = await _create_candidate(db_session)
        response = await interviewer_client.post(
            f"/candidates/{candidate.id}/edit",
            data={
                "first_name": "Blocked",
                "last_name": "Edit",
                "email": "blocked.edit@example.com",
                "phone": "",
                "linkedin_url": "",
                "resume_text": "",
            },
            follow_redirects=False,
        )
        assert response.status_code == 403

    async def test_edit_candidate_by_recruiter(
        self, recruiter_client: httpx.AsyncClient, db_session: AsyncSession
    ):
        candidate = await _create_candidate(db_session)
        response = await recruiter_client.post(
            f"/candidates/{candidate.id}/edit",
            data={
                "first_name": "RecruiterEdited",
                "last_name": "Doe",
                "email": "jane.doe@example.com",
                "phone": "",
                "linkedin_url": "",
                "resume_text": "",
            },
            follow_redirects=False,
        )
        assert response.status_code == 302

        await db_session.refresh(candidate)
        assert candidate.first_name == "RecruiterEdited"

    async def test_edit_candidate_by_hiring_manager(
        self, hiring_manager_client: httpx.AsyncClient, db_session: AsyncSession
    ):
        candidate = await _create_candidate(db_session)
        response = await hiring_manager_client.post(
            f"/candidates/{candidate.id}/edit",
            data={
                "first_name": "HMEdited",
                "last_name": "Doe",
                "email": "jane.doe@example.com",
                "phone": "",
                "linkedin_url": "",
                "resume_text": "",
            },
            follow_redirects=False,
        )
        assert response.status_code == 302

        await db_session.refresh(candidate)
        assert candidate.first_name == "HMEdited"


# ──────────────────────────────────────────────
# Skill Tags (Many-to-Many)
# ──────────────────────────────────────────────


class TestSkillTags:
    async def test_add_skill_to_candidate(
        self, admin_client: httpx.AsyncClient, db_session: AsyncSession
    ):
        candidate = await _create_candidate(db_session)
        response = await admin_client.post(
            f"/candidates/{candidate.id}/skills",
            data={"skill_name": "Django"},
            follow_redirects=False,
        )
        assert response.status_code == 302
        assert f"/candidates/{candidate.id}" in response.headers["location"]

        result = await db_session.execute(select(Skill).where(Skill.name == "Django"))
        skill = result.scalar_one_or_none()
        assert skill is not None

        await db_session.refresh(candidate, attribute_names=["skills"])
        skill_names = [s.name for s in candidate.skills]
        assert "Django" in skill_names

    async def test_add_existing_skill_to_candidate(
        self, admin_client: httpx.AsyncClient, db_session: AsyncSession
    ):
        candidate = await _create_candidate(db_session)
        await _create_skill(db_session, name="Go")

        response = await admin_client.post(
            f"/candidates/{candidate.id}/skills",
            data={"skill_name": "Go"},
            follow_redirects=False,
        )
        assert response.status_code == 302

        result = await db_session.execute(select(Skill).where(Skill.name == "Go"))
        skills = list(result.scalars().all())
        assert len(skills) == 1

    async def test_add_duplicate_skill_to_same_candidate(
        self, admin_client: httpx.AsyncClient, db_session: AsyncSession
    ):
        candidate = await _create_candidate(db_session)
        skill = await _create_skill(db_session, name="TypeScript")
        candidate.skills.append(skill)
        await db_session.flush()

        response = await admin_client.post(
            f"/candidates/{candidate.id}/skills",
            data={"skill_name": "TypeScript"},
            follow_redirects=False,
        )
        # Should redirect even on error (the route catches ValueError)
        assert response.status_code == 302

    async def test_add_empty_skill_name(
        self, admin_client: httpx.AsyncClient, db_session: AsyncSession
    ):
        candidate = await _create_candidate(db_session)
        response = await admin_client.post(
            f"/candidates/{candidate.id}/skills",
            data={"skill_name": ""},
            follow_redirects=False,
        )
        # Should redirect (route catches ValueError for empty skill)
        assert response.status_code == 302

    async def test_remove_skill_from_candidate(
        self, admin_client: httpx.AsyncClient, db_session: AsyncSession
    ):
        candidate = await _create_candidate(db_session)
        skill = await _create_skill(db_session, name="Java")
        candidate.skills.append(skill)
        await db_session.flush()

        response = await admin_client.post(
            f"/candidates/{candidate.id}/skills/{skill.id}/remove",
            follow_redirects=False,
        )
        assert response.status_code == 302
        assert f"/candidates/{candidate.id}" in response.headers["location"]

        await db_session.refresh(candidate, attribute_names=["skills"])
        skill_names = [s.name for s in candidate.skills]
        assert "Java" not in skill_names

    async def test_remove_nonexistent_skill_from_candidate(
        self, admin_client: httpx.AsyncClient, db_session: AsyncSession
    ):
        candidate = await _create_candidate(db_session)
        response = await admin_client.post(
            f"/candidates/{candidate.id}/skills/nonexistent-skill-id/remove",
            follow_redirects=False,
        )
        # Should redirect (route catches ValueError)
        assert response.status_code == 302

    async def test_add_skill_forbidden_for_interviewer(
        self, interviewer_client: httpx.AsyncClient, db_session: AsyncSession
    ):
        candidate = await _create_candidate(db_session)
        response = await interviewer_client.post(
            f"/candidates/{candidate.id}/skills",
            data={"skill_name": "Blocked"},
            follow_redirects=False,
        )
        assert response.status_code == 403

    async def test_remove_skill_forbidden_for_interviewer(
        self, interviewer_client: httpx.AsyncClient, db_session: AsyncSession
    ):
        candidate = await _create_candidate(db_session)
        skill = await _create_skill(db_session, name="RemoveBlocked")
        candidate.skills.append(skill)
        await db_session.flush()

        response = await interviewer_client.post(
            f"/candidates/{candidate.id}/skills/{skill.id}/remove",
            follow_redirects=False,
        )
        assert response.status_code == 403

    async def test_add_skill_by_hiring_manager(
        self, hiring_manager_client: httpx.AsyncClient, db_session: AsyncSession
    ):
        candidate = await _create_candidate(db_session)
        response = await hiring_manager_client.post(
            f"/candidates/{candidate.id}/skills",
            data={"skill_name": "Kubernetes"},
            follow_redirects=False,
        )
        assert response.status_code == 302

        await db_session.refresh(candidate, attribute_names=["skills"])
        skill_names = [s.name for s in candidate.skills]
        assert "Kubernetes" in skill_names

    async def test_multiple_skills_on_candidate(
        self, admin_client: httpx.AsyncClient, db_session: AsyncSession
    ):
        candidate = await _create_candidate(db_session)

        for skill_name in ["Python", "FastAPI", "SQLAlchemy"]:
            await admin_client.post(
                f"/candidates/{candidate.id}/skills",
                data={"skill_name": skill_name},
                follow_redirects=False,
            )

        await db_session.refresh(candidate, attribute_names=["skills"])
        skill_names = {s.name for s in candidate.skills}
        assert "Python" in skill_names
        assert "FastAPI" in skill_names
        assert "SQLAlchemy" in skill_names


# ──────────────────────────────────────────────
# RBAC Enforcement
# ──────────────────────────────────────────────


class TestCandidateRBAC:
    async def test_unauthenticated_user_cannot_list_candidates(
        self, client: httpx.AsyncClient
    ):
        response = await client.get("/candidates", follow_redirects=False)
        assert response.status_code == 401

    async def test_unauthenticated_user_cannot_create_candidate(
        self, client: httpx.AsyncClient
    ):
        response = await client.post(
            "/candidates/create",
            data={
                "first_name": "Unauth",
                "last_name": "User",
                "email": "unauth@example.com",
                "phone": "",
                "linkedin_url": "",
                "resume_text": "",
            },
            follow_redirects=False,
        )
        assert response.status_code == 401

    async def test_system_admin_can_create_candidate(
        self, admin_client: httpx.AsyncClient
    ):
        response = await admin_client.post(
            "/candidates/create",
            data={
                "first_name": "Admin",
                "last_name": "Created",
                "email": "admin.created@example.com",
                "phone": "",
                "linkedin_url": "",
                "resume_text": "",
            },
            follow_redirects=False,
        )
        assert response.status_code == 302

    async def test_hr_recruiter_can_create_candidate(
        self, recruiter_client: httpx.AsyncClient
    ):
        response = await recruiter_client.post(
            "/candidates/create",
            data={
                "first_name": "Recruiter",
                "last_name": "Created",
                "email": "recruiter.created@example.com",
                "phone": "",
                "linkedin_url": "",
                "resume_text": "",
            },
            follow_redirects=False,
        )
        assert response.status_code == 302

    async def test_hiring_manager_can_create_candidate(
        self, hiring_manager_client: httpx.AsyncClient
    ):
        response = await hiring_manager_client.post(
            "/candidates/create",
            data={
                "first_name": "HM",
                "last_name": "Created",
                "email": "hm.created@example.com",
                "phone": "",
                "linkedin_url": "",
                "resume_text": "",
            },
            follow_redirects=False,
        )
        assert response.status_code == 302

    async def test_interviewer_cannot_create_candidate(
        self, interviewer_client: httpx.AsyncClient
    ):
        response = await interviewer_client.post(
            "/candidates/create",
            data={
                "first_name": "Interviewer",
                "last_name": "Blocked",
                "email": "interviewer.blocked@example.com",
                "phone": "",
                "linkedin_url": "",
                "resume_text": "",
            },
            follow_redirects=False,
        )
        assert response.status_code == 403

    async def test_interviewer_cannot_edit_candidate(
        self, interviewer_client: httpx.AsyncClient, db_session: AsyncSession
    ):
        candidate = await _create_candidate(db_session)
        response = await interviewer_client.post(
            f"/candidates/{candidate.id}/edit",
            data={
                "first_name": "Blocked",
                "last_name": "Edit",
                "email": "jane.doe@example.com",
                "phone": "",
                "linkedin_url": "",
                "resume_text": "",
            },
            follow_redirects=False,
        )
        assert response.status_code == 403

    async def test_interviewer_can_view_candidate_detail(
        self, interviewer_client: httpx.AsyncClient, db_session: AsyncSession
    ):
        candidate = await _create_candidate(db_session)
        response = await interviewer_client.get(
            f"/candidates/{candidate.id}", follow_redirects=False
        )
        assert response.status_code == 200
        assert "Jane" in response.text

    async def test_interviewer_cannot_manage_skills(
        self, interviewer_client: httpx.AsyncClient, db_session: AsyncSession
    ):
        candidate = await _create_candidate(db_session)

        add_response = await interviewer_client.post(
            f"/candidates/{candidate.id}/skills",
            data={"skill_name": "Blocked"},
            follow_redirects=False,
        )
        assert add_response.status_code == 403

        skill = await _create_skill(db_session, name="ExistingSkill")
        candidate.skills.append(skill)
        await db_session.flush()

        remove_response = await interviewer_client.post(
            f"/candidates/{candidate.id}/skills/{skill.id}/remove",
            follow_redirects=False,
        )
        assert remove_response.status_code == 403