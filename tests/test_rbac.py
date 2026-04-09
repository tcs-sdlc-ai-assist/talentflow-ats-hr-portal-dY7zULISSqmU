import pytest
import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_session_cookie, hash_password
from app.models.user import User


# ---------------------------------------------------------------------------
# Helper: create a user with a given role
# ---------------------------------------------------------------------------

async def _create_user(db: AsyncSession, username: str, role: str) -> User:
    user = User(
        username=username,
        password_hash=hash_password("testpass123"),
        role=role,
    )
    db.add(user)
    await db.flush()
    await db.refresh(user)
    return user


def _auth_cookies(user: User) -> dict[str, str]:
    return {"session_token": create_session_cookie(user.id)}


# ---------------------------------------------------------------------------
# Unauthenticated access → 401 or redirect
# ---------------------------------------------------------------------------


class TestUnauthenticatedAccess:
    """Unauthenticated users must be denied access to protected routes."""

    @pytest.mark.asyncio
    async def test_dashboard_requires_auth(self, client: httpx.AsyncClient):
        response = await client.get("/dashboard", follow_redirects=False)
        # Should get 401 (API-level) or a redirect to login
        assert response.status_code in (401, 302, 303)

    @pytest.mark.asyncio
    async def test_jobs_list_requires_auth(self, client: httpx.AsyncClient):
        response = await client.get("/jobs", follow_redirects=False)
        assert response.status_code in (401, 302, 303)

    @pytest.mark.asyncio
    async def test_candidates_list_requires_auth(self, client: httpx.AsyncClient):
        response = await client.get("/candidates", follow_redirects=False)
        assert response.status_code in (401, 302, 303)

    @pytest.mark.asyncio
    async def test_applications_list_requires_auth(self, client: httpx.AsyncClient):
        response = await client.get("/applications", follow_redirects=False)
        assert response.status_code in (401, 302, 303)

    @pytest.mark.asyncio
    async def test_interviews_list_requires_auth(self, client: httpx.AsyncClient):
        response = await client.get("/interviews", follow_redirects=False)
        assert response.status_code in (401, 302, 303)

    @pytest.mark.asyncio
    async def test_audit_log_requires_auth(self, client: httpx.AsyncClient):
        response = await client.get("/audit-log", follow_redirects=False)
        assert response.status_code in (401, 302, 303)


# ---------------------------------------------------------------------------
# Role string values are Title Case with spaces
# ---------------------------------------------------------------------------


class TestRoleStringValues:
    """Role constants must be Title Case with spaces, matching the User model."""

    def test_system_admin_role_value(self):
        from app.core.constants import UserRole

        assert UserRole.SYSTEM_ADMIN == "System Admin"

    def test_hr_recruiter_role_value(self):
        from app.core.constants import UserRole

        assert UserRole.HR_RECRUITER == "HR Recruiter"

    def test_hiring_manager_role_value(self):
        from app.core.constants import UserRole

        assert UserRole.HIRING_MANAGER == "Hiring Manager"

    def test_interviewer_role_value(self):
        from app.core.constants import UserRole

        assert UserRole.INTERVIEWER == "Interviewer"

    def test_all_roles_are_title_case_with_spaces(self):
        from app.core.constants import UserRole

        for role in UserRole.ALL:
            # Each word should start with uppercase
            assert role == role.strip()
            words = role.split(" ")
            for word in words:
                assert word[0].isupper(), f"Role '{role}' word '{word}' is not title case"


# ---------------------------------------------------------------------------
# System Admin access
# ---------------------------------------------------------------------------


class TestSystemAdminAccess:
    """System Admin should have access to all protected routes."""

    @pytest.mark.asyncio
    async def test_admin_can_access_hr_dashboard(self, admin_client: httpx.AsyncClient):
        response = await admin_client.get("/dashboard/hr", follow_redirects=False)
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_admin_can_access_hiring_manager_dashboard(
        self, admin_client: httpx.AsyncClient
    ):
        response = await admin_client.get(
            "/dashboard/hiring-manager", follow_redirects=False
        )
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_admin_can_access_interviewer_dashboard(
        self, admin_client: httpx.AsyncClient
    ):
        response = await admin_client.get(
            "/dashboard/interviewer", follow_redirects=False
        )
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_admin_can_access_jobs(self, admin_client: httpx.AsyncClient):
        response = await admin_client.get("/jobs", follow_redirects=False)
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_admin_can_access_candidates(self, admin_client: httpx.AsyncClient):
        response = await admin_client.get("/candidates", follow_redirects=False)
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_admin_can_access_applications(self, admin_client: httpx.AsyncClient):
        response = await admin_client.get("/applications", follow_redirects=False)
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_admin_can_access_interviews(self, admin_client: httpx.AsyncClient):
        response = await admin_client.get("/interviews", follow_redirects=False)
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_admin_can_access_audit_log(self, admin_client: httpx.AsyncClient):
        response = await admin_client.get("/audit-log", follow_redirects=False)
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_admin_can_access_job_create(self, admin_client: httpx.AsyncClient):
        response = await admin_client.get("/jobs/create", follow_redirects=False)
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_admin_can_access_candidate_create(
        self, admin_client: httpx.AsyncClient
    ):
        response = await admin_client.get("/candidates/create", follow_redirects=False)
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_admin_can_access_application_create(
        self, admin_client: httpx.AsyncClient
    ):
        response = await admin_client.get(
            "/applications/create", follow_redirects=False
        )
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_admin_can_access_interview_schedule(
        self, admin_client: httpx.AsyncClient
    ):
        response = await admin_client.get(
            "/interviews/schedule", follow_redirects=False
        )
        assert response.status_code == 200


# ---------------------------------------------------------------------------
# HR Recruiter access
# ---------------------------------------------------------------------------


class TestHRRecruiterAccess:
    """HR Recruiter should have access to most routes including audit log."""

    @pytest.mark.asyncio
    async def test_recruiter_can_access_hr_dashboard(
        self, recruiter_client: httpx.AsyncClient
    ):
        response = await recruiter_client.get("/dashboard/hr", follow_redirects=False)
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_recruiter_can_access_audit_log(
        self, recruiter_client: httpx.AsyncClient
    ):
        response = await recruiter_client.get("/audit-log", follow_redirects=False)
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_recruiter_can_access_jobs(
        self, recruiter_client: httpx.AsyncClient
    ):
        response = await recruiter_client.get("/jobs", follow_redirects=False)
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_recruiter_can_access_candidates(
        self, recruiter_client: httpx.AsyncClient
    ):
        response = await recruiter_client.get("/candidates", follow_redirects=False)
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_recruiter_can_access_applications(
        self, recruiter_client: httpx.AsyncClient
    ):
        response = await recruiter_client.get("/applications", follow_redirects=False)
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_recruiter_can_access_interviews(
        self, recruiter_client: httpx.AsyncClient
    ):
        response = await recruiter_client.get("/interviews", follow_redirects=False)
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_recruiter_can_access_interview_schedule(
        self, recruiter_client: httpx.AsyncClient
    ):
        response = await recruiter_client.get(
            "/interviews/schedule", follow_redirects=False
        )
        assert response.status_code == 200


# ---------------------------------------------------------------------------
# Hiring Manager access
# ---------------------------------------------------------------------------


class TestHiringManagerAccess:
    """Hiring Manager should access their dashboard and job-related routes."""

    @pytest.mark.asyncio
    async def test_hm_can_access_hiring_manager_dashboard(
        self, hiring_manager_client: httpx.AsyncClient
    ):
        response = await hiring_manager_client.get(
            "/dashboard/hiring-manager", follow_redirects=False
        )
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_hm_can_access_jobs(
        self, hiring_manager_client: httpx.AsyncClient
    ):
        response = await hiring_manager_client.get("/jobs", follow_redirects=False)
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_hm_can_access_candidates(
        self, hiring_manager_client: httpx.AsyncClient
    ):
        response = await hiring_manager_client.get(
            "/candidates", follow_redirects=False
        )
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_hm_can_access_applications(
        self, hiring_manager_client: httpx.AsyncClient
    ):
        response = await hiring_manager_client.get(
            "/applications", follow_redirects=False
        )
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_hm_can_access_interviews(
        self, hiring_manager_client: httpx.AsyncClient
    ):
        response = await hiring_manager_client.get(
            "/interviews", follow_redirects=False
        )
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_hm_cannot_access_audit_log(
        self, hiring_manager_client: httpx.AsyncClient
    ):
        response = await hiring_manager_client.get(
            "/audit-log", follow_redirects=False
        )
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_hm_can_access_job_create(
        self, hiring_manager_client: httpx.AsyncClient
    ):
        response = await hiring_manager_client.get(
            "/jobs/create", follow_redirects=False
        )
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_hm_can_access_interview_schedule(
        self, hiring_manager_client: httpx.AsyncClient
    ):
        response = await hiring_manager_client.get(
            "/interviews/schedule", follow_redirects=False
        )
        assert response.status_code == 200


# ---------------------------------------------------------------------------
# Interviewer access
# ---------------------------------------------------------------------------


class TestInterviewerAccess:
    """Interviewer should have limited access — no audit log, no job creation."""

    @pytest.mark.asyncio
    async def test_interviewer_can_access_interviewer_dashboard(
        self, interviewer_client: httpx.AsyncClient
    ):
        response = await interviewer_client.get(
            "/dashboard/interviewer", follow_redirects=False
        )
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_interviewer_can_access_jobs(
        self, interviewer_client: httpx.AsyncClient
    ):
        response = await interviewer_client.get("/jobs", follow_redirects=False)
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_interviewer_can_access_candidates(
        self, interviewer_client: httpx.AsyncClient
    ):
        response = await interviewer_client.get("/candidates", follow_redirects=False)
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_interviewer_can_access_applications(
        self, interviewer_client: httpx.AsyncClient
    ):
        response = await interviewer_client.get(
            "/applications", follow_redirects=False
        )
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_interviewer_can_access_interviews(
        self, interviewer_client: httpx.AsyncClient
    ):
        response = await interviewer_client.get("/interviews", follow_redirects=False)
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_interviewer_cannot_access_audit_log(
        self, interviewer_client: httpx.AsyncClient
    ):
        response = await interviewer_client.get("/audit-log", follow_redirects=False)
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_interviewer_cannot_access_hr_dashboard(
        self, interviewer_client: httpx.AsyncClient
    ):
        response = await interviewer_client.get("/dashboard/hr", follow_redirects=False)
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_interviewer_cannot_create_candidate(
        self, interviewer_client: httpx.AsyncClient
    ):
        response = await interviewer_client.get(
            "/candidates/create", follow_redirects=False
        )
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_interviewer_redirected_from_job_create(
        self, interviewer_client: httpx.AsyncClient
    ):
        response = await interviewer_client.get(
            "/jobs/create", follow_redirects=False
        )
        # Job create checks role inline and redirects non-permitted users
        assert response.status_code in (302, 303)

    @pytest.mark.asyncio
    async def test_interviewer_redirected_from_interview_schedule(
        self, interviewer_client: httpx.AsyncClient
    ):
        response = await interviewer_client.get(
            "/interviews/schedule", follow_redirects=False
        )
        # Interview schedule checks role inline and redirects non-permitted users
        assert response.status_code in (302, 303)

    @pytest.mark.asyncio
    async def test_interviewer_redirected_from_application_create(
        self, interviewer_client: httpx.AsyncClient
    ):
        response = await interviewer_client.get(
            "/applications/create", follow_redirects=False
        )
        # Application create checks role inline and redirects non-permitted users
        assert response.status_code in (302, 303)


# ---------------------------------------------------------------------------
# Invalid / expired session
# ---------------------------------------------------------------------------


class TestInvalidSession:
    """Requests with invalid or tampered session cookies should be rejected."""

    @pytest.mark.asyncio
    async def test_invalid_session_cookie_rejected(self, client: httpx.AsyncClient):
        client.cookies.set("session_token", "totally-invalid-garbage-value")
        response = await client.get("/dashboard", follow_redirects=False)
        assert response.status_code in (401, 302, 303)

    @pytest.mark.asyncio
    async def test_empty_session_cookie_rejected(self, client: httpx.AsyncClient):
        client.cookies.set("session_token", "")
        response = await client.get("/jobs", follow_redirects=False)
        assert response.status_code in (401, 302, 303)


# ---------------------------------------------------------------------------
# Dashboard redirect based on role
# ---------------------------------------------------------------------------


class TestDashboardRedirect:
    """GET /dashboard should redirect to the role-appropriate dashboard."""

    @pytest.mark.asyncio
    async def test_admin_redirected_to_hr_dashboard(
        self, admin_client: httpx.AsyncClient
    ):
        response = await admin_client.get("/dashboard", follow_redirects=False)
        assert response.status_code == 302
        assert "/dashboard/hr" in response.headers.get("location", "")

    @pytest.mark.asyncio
    async def test_recruiter_redirected_to_hr_dashboard(
        self, recruiter_client: httpx.AsyncClient
    ):
        response = await recruiter_client.get("/dashboard", follow_redirects=False)
        assert response.status_code == 302
        assert "/dashboard/hr" in response.headers.get("location", "")

    @pytest.mark.asyncio
    async def test_hiring_manager_redirected_to_hm_dashboard(
        self, hiring_manager_client: httpx.AsyncClient
    ):
        response = await hiring_manager_client.get("/dashboard", follow_redirects=False)
        assert response.status_code == 302
        assert "/dashboard/hiring-manager" in response.headers.get("location", "")

    @pytest.mark.asyncio
    async def test_interviewer_redirected_to_interviewer_dashboard(
        self, interviewer_client: httpx.AsyncClient
    ):
        response = await interviewer_client.get("/dashboard", follow_redirects=False)
        assert response.status_code == 302
        assert "/dashboard/interviewer" in response.headers.get("location", "")


# ---------------------------------------------------------------------------
# require_roles dependency unit tests
# ---------------------------------------------------------------------------


class TestRequireRolesDependency:
    """Unit tests for the require_roles dependency function."""

    @pytest.mark.asyncio
    async def test_require_roles_allows_matching_role(
        self, db_session: AsyncSession
    ):
        from app.dependencies.rbac import require_roles

        user = await _create_user(db_session, "rbac_test_admin", "System Admin")
        checker = require_roles(["System Admin", "HR Recruiter"])
        # Should return the user without raising
        result = await checker(current_user=user)
        assert result.id == user.id
        assert result.role == "System Admin"

    @pytest.mark.asyncio
    async def test_require_roles_denies_non_matching_role(
        self, db_session: AsyncSession
    ):
        from fastapi import HTTPException

        from app.dependencies.rbac import require_roles

        user = await _create_user(db_session, "rbac_test_viewer", "Interviewer")
        checker = require_roles(["System Admin"])
        with pytest.raises(HTTPException) as exc_info:
            await checker(current_user=user)
        assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    async def test_require_roles_denies_empty_allowed_list(
        self, db_session: AsyncSession
    ):
        from fastapi import HTTPException

        from app.dependencies.rbac import require_roles

        user = await _create_user(db_session, "rbac_test_empty", "System Admin")
        checker = require_roles([])
        with pytest.raises(HTTPException) as exc_info:
            await checker(current_user=user)
        assert exc_info.value.status_code == 403


# ---------------------------------------------------------------------------
# Public routes remain accessible without auth
# ---------------------------------------------------------------------------


class TestPublicRoutes:
    """Public routes should be accessible without authentication."""

    @pytest.mark.asyncio
    async def test_landing_page_accessible(self, client: httpx.AsyncClient):
        response = await client.get("/", follow_redirects=False)
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_health_check_accessible(self, client: httpx.AsyncClient):
        response = await client.get("/health", follow_redirects=False)
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"

    @pytest.mark.asyncio
    async def test_login_page_accessible(self, client: httpx.AsyncClient):
        response = await client.get("/auth/login", follow_redirects=False)
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_register_page_accessible(self, client: httpx.AsyncClient):
        response = await client.get("/auth/register", follow_redirects=False)
        assert response.status_code == 200