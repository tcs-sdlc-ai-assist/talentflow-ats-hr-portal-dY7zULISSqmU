import pytest
import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password, verify_password, create_session_cookie, verify_session_cookie
from app.models.user import User


pytestmark = pytest.mark.asyncio


class TestLogin:
    async def test_login_page_returns_200(self, client: httpx.AsyncClient):
        response = await client.get("/auth/login")
        assert response.status_code == 200
        assert "Sign in to TalentFlow" in response.text

    async def test_login_with_valid_credentials_redirects_to_dashboard(
        self,
        client: httpx.AsyncClient,
        db_session: AsyncSession,
    ):
        user = User(
            username="loginuser",
            password_hash=hash_password("validpass123"),
            role="System Admin",
        )
        db_session.add(user)
        await db_session.flush()
        await db_session.refresh(user)

        response = await client.post(
            "/auth/login",
            data={"username": "loginuser", "password": "validpass123"},
            follow_redirects=False,
        )
        assert response.status_code == 302
        assert response.headers["location"] == "/dashboard"

    async def test_login_sets_session_cookie(
        self,
        client: httpx.AsyncClient,
        db_session: AsyncSession,
    ):
        user = User(
            username="cookieuser",
            password_hash=hash_password("cookiepass123"),
            role="HR Recruiter",
        )
        db_session.add(user)
        await db_session.flush()
        await db_session.refresh(user)

        response = await client.post(
            "/auth/login",
            data={"username": "cookieuser", "password": "cookiepass123"},
            follow_redirects=False,
        )
        assert response.status_code == 302
        set_cookie_header = response.headers.get("set-cookie", "")
        assert "session_token=" in set_cookie_header
        assert "httponly" in set_cookie_header.lower()

    async def test_login_cookie_is_httponly(
        self,
        client: httpx.AsyncClient,
        db_session: AsyncSession,
    ):
        user = User(
            username="httponlyuser",
            password_hash=hash_password("httponlypass123"),
            role="Interviewer",
        )
        db_session.add(user)
        await db_session.flush()
        await db_session.refresh(user)

        response = await client.post(
            "/auth/login",
            data={"username": "httponlyuser", "password": "httponlypass123"},
            follow_redirects=False,
        )
        set_cookie_header = response.headers.get("set-cookie", "")
        assert "httponly" in set_cookie_header.lower()

    async def test_login_cookie_is_samesite_lax(
        self,
        client: httpx.AsyncClient,
        db_session: AsyncSession,
    ):
        user = User(
            username="samesiteuser",
            password_hash=hash_password("samesitepass123"),
            role="Interviewer",
        )
        db_session.add(user)
        await db_session.flush()
        await db_session.refresh(user)

        response = await client.post(
            "/auth/login",
            data={"username": "samesiteuser", "password": "samesitepass123"},
            follow_redirects=False,
        )
        set_cookie_header = response.headers.get("set-cookie", "")
        assert "samesite=lax" in set_cookie_header.lower()

    async def test_login_with_invalid_password_returns_400(
        self,
        client: httpx.AsyncClient,
        db_session: AsyncSession,
    ):
        user = User(
            username="badpassuser",
            password_hash=hash_password("correctpass123"),
            role="Interviewer",
        )
        db_session.add(user)
        await db_session.flush()

        response = await client.post(
            "/auth/login",
            data={"username": "badpassuser", "password": "wrongpassword"},
            follow_redirects=False,
        )
        assert response.status_code == 400
        assert "Invalid username or password" in response.text

    async def test_login_with_nonexistent_user_returns_400(
        self,
        client: httpx.AsyncClient,
    ):
        response = await client.post(
            "/auth/login",
            data={"username": "doesnotexist", "password": "anypassword"},
            follow_redirects=False,
        )
        assert response.status_code == 400
        assert "Invalid username or password" in response.text

    async def test_login_redirects_to_dashboard_for_all_roles(
        self,
        client: httpx.AsyncClient,
        db_session: AsyncSession,
    ):
        roles = ["System Admin", "HR Recruiter", "Hiring Manager", "Interviewer"]
        for i, role in enumerate(roles):
            user = User(
                username=f"roleuser{i}",
                password_hash=hash_password("rolepass123"),
                role=role,
            )
            db_session.add(user)
            await db_session.flush()

            response = await client.post(
                "/auth/login",
                data={"username": f"roleuser{i}", "password": "rolepass123"},
                follow_redirects=False,
            )
            assert response.status_code == 302
            assert response.headers["location"] == "/dashboard", (
                f"Expected redirect to /dashboard for role '{role}', "
                f"got '{response.headers.get('location')}'"
            )

    async def test_login_page_redirects_authenticated_user_to_dashboard(
        self,
        admin_client: httpx.AsyncClient,
    ):
        response = await admin_client.get("/auth/login", follow_redirects=False)
        assert response.status_code == 302
        assert response.headers["location"] == "/dashboard"


class TestRegistration:
    async def test_register_page_returns_200(self, client: httpx.AsyncClient):
        response = await client.get("/auth/register")
        assert response.status_code == 200
        assert "Create your account" in response.text

    async def test_register_creates_user_with_interviewer_role(
        self,
        client: httpx.AsyncClient,
        db_session: AsyncSession,
    ):
        response = await client.post(
            "/auth/register",
            data={
                "username": "newinterviewer",
                "password": "securepass123",
                "confirm_password": "securepass123",
            },
            follow_redirects=False,
        )
        assert response.status_code == 302
        assert response.headers["location"] == "/dashboard"

        from sqlalchemy import select

        result = await db_session.execute(
            select(User).where(User.username == "newinterviewer")
        )
        new_user = result.scalars().first()
        assert new_user is not None
        assert new_user.role == "Interviewer"

    async def test_register_sets_session_cookie(
        self,
        client: httpx.AsyncClient,
    ):
        response = await client.post(
            "/auth/register",
            data={
                "username": "cookiereg",
                "password": "securepass123",
                "confirm_password": "securepass123",
            },
            follow_redirects=False,
        )
        assert response.status_code == 302
        set_cookie_header = response.headers.get("set-cookie", "")
        assert "session_token=" in set_cookie_header
        assert "httponly" in set_cookie_header.lower()

    async def test_register_with_short_username_returns_400(
        self,
        client: httpx.AsyncClient,
    ):
        response = await client.post(
            "/auth/register",
            data={
                "username": "ab",
                "password": "securepass123",
                "confirm_password": "securepass123",
            },
            follow_redirects=False,
        )
        assert response.status_code == 400
        assert "Username must be at least 3 characters" in response.text

    async def test_register_with_short_password_returns_400(
        self,
        client: httpx.AsyncClient,
    ):
        response = await client.post(
            "/auth/register",
            data={
                "username": "shortpwduser",
                "password": "short",
                "confirm_password": "short",
            },
            follow_redirects=False,
        )
        assert response.status_code == 400
        assert "Password must be at least 8 characters" in response.text

    async def test_register_with_mismatched_passwords_returns_400(
        self,
        client: httpx.AsyncClient,
    ):
        response = await client.post(
            "/auth/register",
            data={
                "username": "mismatchuser",
                "password": "securepass123",
                "confirm_password": "differentpass123",
            },
            follow_redirects=False,
        )
        assert response.status_code == 400
        assert "Passwords do not match" in response.text

    async def test_register_with_duplicate_username_returns_400(
        self,
        client: httpx.AsyncClient,
        db_session: AsyncSession,
    ):
        user = User(
            username="existinguser",
            password_hash=hash_password("existingpass123"),
            role="Interviewer",
        )
        db_session.add(user)
        await db_session.flush()

        response = await client.post(
            "/auth/register",
            data={
                "username": "existinguser",
                "password": "newpassword123",
                "confirm_password": "newpassword123",
            },
            follow_redirects=False,
        )
        assert response.status_code == 400
        assert "already exists" in response.text

    async def test_register_page_redirects_authenticated_user_to_dashboard(
        self,
        admin_client: httpx.AsyncClient,
    ):
        response = await admin_client.get("/auth/register", follow_redirects=False)
        assert response.status_code == 302
        assert response.headers["location"] == "/dashboard"


class TestLogout:
    async def test_logout_clears_session_cookie(
        self,
        admin_client: httpx.AsyncClient,
    ):
        response = await admin_client.post("/auth/logout", follow_redirects=False)
        assert response.status_code == 302
        assert response.headers["location"] == "/"

        set_cookie_header = response.headers.get("set-cookie", "")
        assert "session_token=" in set_cookie_header
        lower_header = set_cookie_header.lower()
        has_empty_value = 'session_token=""' in set_cookie_header or 'session_token=;' in set_cookie_header
        has_max_age_zero = "max-age=0" in lower_header
        has_expires_past = "expires=" in lower_header
        assert has_empty_value or has_max_age_zero or has_expires_past

    async def test_logout_redirects_to_landing(
        self,
        admin_client: httpx.AsyncClient,
    ):
        response = await admin_client.post("/auth/logout", follow_redirects=False)
        assert response.status_code == 302
        assert response.headers["location"] == "/"

    async def test_logout_without_session_redirects_to_landing(
        self,
        client: httpx.AsyncClient,
    ):
        response = await client.post("/auth/logout", follow_redirects=False)
        assert response.status_code == 302
        assert response.headers["location"] == "/"


class TestSessionSecurity:
    async def test_session_cookie_can_be_verified(self):
        user_id = "test-user-id-12345"
        cookie = create_session_cookie(user_id)
        verified_id = verify_session_cookie(cookie)
        assert verified_id == user_id

    async def test_invalid_session_cookie_returns_none(self):
        result = verify_session_cookie("invalid-cookie-value")
        assert result is None

    async def test_tampered_session_cookie_returns_none(self):
        cookie = create_session_cookie("some-user-id")
        tampered = cookie[:-5] + "XXXXX"
        result = verify_session_cookie(tampered)
        assert result is None

    async def test_empty_session_cookie_returns_none(self):
        result = verify_session_cookie("")
        assert result is None


class TestProtectedRoutes:
    async def test_dashboard_requires_authentication(
        self,
        client: httpx.AsyncClient,
    ):
        response = await client.get("/dashboard", follow_redirects=False)
        assert response.status_code in (401, 302, 307)

    async def test_jobs_requires_authentication(
        self,
        client: httpx.AsyncClient,
    ):
        response = await client.get("/jobs", follow_redirects=False)
        assert response.status_code in (401, 302, 307)

    async def test_candidates_requires_authentication(
        self,
        client: httpx.AsyncClient,
    ):
        response = await client.get("/candidates", follow_redirects=False)
        assert response.status_code in (401, 302, 307)

    async def test_interviews_requires_authentication(
        self,
        client: httpx.AsyncClient,
    ):
        response = await client.get("/interviews", follow_redirects=False)
        assert response.status_code in (401, 302, 307)

    async def test_audit_log_requires_admin_or_recruiter_role(
        self,
        interviewer_client: httpx.AsyncClient,
    ):
        response = await interviewer_client.get("/audit-log", follow_redirects=False)
        assert response.status_code == 403

    async def test_audit_log_accessible_by_admin(
        self,
        admin_client: httpx.AsyncClient,
    ):
        response = await admin_client.get("/audit-log", follow_redirects=False)
        assert response.status_code == 200

    async def test_audit_log_accessible_by_recruiter(
        self,
        recruiter_client: httpx.AsyncClient,
    ):
        response = await recruiter_client.get("/audit-log", follow_redirects=False)
        assert response.status_code == 200


class TestRBACEnforcement:
    async def test_interviewer_cannot_create_job(
        self,
        interviewer_client: httpx.AsyncClient,
    ):
        response = await interviewer_client.get("/jobs/create", follow_redirects=False)
        assert response.status_code == 302
        assert response.headers["location"] == "/jobs"

    async def test_admin_can_access_hr_dashboard(
        self,
        admin_client: httpx.AsyncClient,
    ):
        response = await admin_client.get("/dashboard/hr", follow_redirects=False)
        assert response.status_code == 200

    async def test_interviewer_cannot_access_hr_dashboard(
        self,
        interviewer_client: httpx.AsyncClient,
    ):
        response = await interviewer_client.get("/dashboard/hr", follow_redirects=False)
        assert response.status_code == 403

    async def test_hiring_manager_cannot_access_hr_dashboard(
        self,
        hiring_manager_client: httpx.AsyncClient,
    ):
        response = await hiring_manager_client.get(
            "/dashboard/hr", follow_redirects=False
        )
        assert response.status_code == 403

    async def test_interviewer_can_access_interviewer_dashboard(
        self,
        interviewer_client: httpx.AsyncClient,
    ):
        response = await interviewer_client.get(
            "/dashboard/interviewer", follow_redirects=False
        )
        assert response.status_code == 200

    async def test_hiring_manager_can_access_hiring_manager_dashboard(
        self,
        hiring_manager_client: httpx.AsyncClient,
    ):
        response = await hiring_manager_client.get(
            "/dashboard/hiring-manager", follow_redirects=False
        )
        assert response.status_code == 200


class TestPasswordSecurity:
    async def test_password_is_hashed_not_stored_plain(self):
        plain = "mysecretpassword"
        hashed = hash_password(plain)
        assert hashed != plain
        assert hashed.startswith("$2b$") or hashed.startswith("$2a$")

    async def test_verify_password_correct(self):
        plain = "mysecretpassword"
        hashed = hash_password(plain)
        assert verify_password(plain, hashed) is True

    async def test_verify_password_incorrect(self):
        hashed = hash_password("correctpassword")
        assert verify_password("wrongpassword", hashed) is False