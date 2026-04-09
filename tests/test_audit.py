import pytest
import httpx
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_log import AuditLog
from app.models.user import User
from app.services.audit_service import log_action, get_audit_logs


@pytest.mark.asyncio
async def test_log_action_creates_entry(db_session: AsyncSession, admin_user: User):
    entry = await log_action(
        db=db_session,
        user_id=admin_user.id,
        username=admin_user.username,
        action="Test Action",
        details="Some detail text",
    )

    assert entry is not None
    assert entry.id is not None
    assert entry.action == "Test Action"
    assert entry.user_id == admin_user.id
    assert entry.username == admin_user.username
    assert entry.details == "Some detail text"
    assert entry.timestamp is not None


@pytest.mark.asyncio
async def test_log_action_without_details(db_session: AsyncSession, admin_user: User):
    entry = await log_action(
        db=db_session,
        user_id=admin_user.id,
        username=admin_user.username,
        action="Action Without Details",
    )

    assert entry is not None
    assert entry.action == "Action Without Details"
    assert entry.details is None


@pytest.mark.asyncio
async def test_log_action_with_none_user(db_session: AsyncSession):
    entry = await log_action(
        db=db_session,
        user_id=None,
        username=None,
        action="System Action",
        details="Automated system event",
    )

    assert entry is not None
    assert entry.user_id is None
    assert entry.username is None
    assert entry.action == "System Action"


@pytest.mark.asyncio
async def test_get_audit_logs_returns_entries(db_session: AsyncSession, admin_user: User):
    for i in range(5):
        await log_action(
            db=db_session,
            user_id=admin_user.id,
            username=admin_user.username,
            action=f"Action {i}",
            details=f"Detail {i}",
        )
    await db_session.flush()

    logs, total = await get_audit_logs(db=db_session, page=1, per_page=10)

    assert total >= 5
    assert len(logs) >= 5


@pytest.mark.asyncio
async def test_get_audit_logs_pagination(db_session: AsyncSession, admin_user: User):
    for i in range(15):
        await log_action(
            db=db_session,
            user_id=admin_user.id,
            username=admin_user.username,
            action=f"Paginated Action {i}",
        )
    await db_session.flush()

    page1_logs, total = await get_audit_logs(db=db_session, page=1, per_page=5)
    page2_logs, total2 = await get_audit_logs(db=db_session, page=2, per_page=5)

    assert len(page1_logs) == 5
    assert len(page2_logs) == 5
    assert total == total2
    assert total >= 15

    page1_ids = {log.id for log in page1_logs}
    page2_ids = {log.id for log in page2_logs}
    assert page1_ids.isdisjoint(page2_ids)


@pytest.mark.asyncio
async def test_get_audit_logs_filter_by_action(db_session: AsyncSession, admin_user: User):
    await log_action(
        db=db_session,
        user_id=admin_user.id,
        username=admin_user.username,
        action="Job Created",
        details="Created a job",
    )
    await log_action(
        db=db_session,
        user_id=admin_user.id,
        username=admin_user.username,
        action="Candidate Created",
        details="Created a candidate",
    )
    await db_session.flush()

    logs, total = await get_audit_logs(
        db=db_session, page=1, per_page=50, action_filter="Job"
    )

    assert total >= 1
    for log in logs:
        assert "Job" in log.action


@pytest.mark.asyncio
async def test_get_audit_logs_filter_by_username(db_session: AsyncSession, admin_user: User):
    await log_action(
        db=db_session,
        user_id=admin_user.id,
        username=admin_user.username,
        action="Filtered By User",
    )
    await db_session.flush()

    logs, total = await get_audit_logs(
        db=db_session, page=1, per_page=50, user_name_filter=admin_user.username
    )

    assert total >= 1
    for log in logs:
        assert admin_user.username.lower() in (log.username or "").lower()


@pytest.mark.asyncio
async def test_get_audit_logs_filter_by_entity_type(db_session: AsyncSession, admin_user: User):
    await log_action(
        db=db_session,
        user_id=admin_user.id,
        username=admin_user.username,
        action="Job Created",
        details="Job 'Senior Engineer' (ID: abc123) created",
    )
    await db_session.flush()

    logs, total = await get_audit_logs(
        db=db_session, page=1, per_page=50, entity_type_filter="Senior Engineer"
    )

    assert total >= 1
    for log in logs:
        assert "Senior Engineer" in (log.details or "")


@pytest.mark.asyncio
async def test_audit_log_page_accessible_by_admin(admin_client: httpx.AsyncClient):
    response = await admin_client.get("/audit-log")
    assert response.status_code == 200
    assert "Audit Log" in response.text


@pytest.mark.asyncio
async def test_audit_log_page_accessible_by_recruiter(recruiter_client: httpx.AsyncClient):
    response = await recruiter_client.get("/audit-log")
    assert response.status_code == 200
    assert "Audit Log" in response.text


@pytest.mark.asyncio
async def test_audit_log_page_forbidden_for_hiring_manager(
    hiring_manager_client: httpx.AsyncClient,
):
    response = await hiring_manager_client.get("/audit-log", follow_redirects=False)
    assert response.status_code in (403, 302)


@pytest.mark.asyncio
async def test_audit_log_page_forbidden_for_interviewer(
    interviewer_client: httpx.AsyncClient,
):
    response = await interviewer_client.get("/audit-log", follow_redirects=False)
    assert response.status_code in (403, 302)


@pytest.mark.asyncio
async def test_audit_log_page_requires_authentication(client: httpx.AsyncClient):
    response = await client.get("/audit-log", follow_redirects=False)
    assert response.status_code in (401, 302)


@pytest.mark.asyncio
async def test_audit_log_page_pagination_params(admin_client: httpx.AsyncClient, db_session: AsyncSession, admin_user: User):
    for i in range(25):
        await log_action(
            db=db_session,
            user_id=admin_user.id,
            username=admin_user.username,
            action=f"Bulk Action {i}",
        )
    await db_session.flush()

    response = await admin_client.get("/audit-log?page=1&page_size=10")
    assert response.status_code == 200
    assert "Showing" in response.text

    response2 = await admin_client.get("/audit-log?page=2&page_size=10")
    assert response2.status_code == 200


@pytest.mark.asyncio
async def test_audit_log_page_filter_params(admin_client: httpx.AsyncClient, db_session: AsyncSession, admin_user: User):
    await log_action(
        db=db_session,
        user_id=admin_user.id,
        username=admin_user.username,
        action="Job Published",
        details="Job 'Test Role' published",
    )
    await db_session.flush()

    response = await admin_client.get("/audit-log?action=Job+Published")
    assert response.status_code == 200

    response2 = await admin_client.get(f"/audit-log?user_name={admin_user.username}")
    assert response2.status_code == 200


@pytest.mark.asyncio
async def test_login_creates_audit_log_entry(client: httpx.AsyncClient, db_session: AsyncSession, admin_user: User):
    count_before_result = await db_session.execute(
        select(func.count(AuditLog.id))
    )
    count_before = count_before_result.scalar() or 0

    response = await client.post(
        "/auth/login",
        data={"username": "testadmin", "password": "adminpass123"},
        follow_redirects=False,
    )
    assert response.status_code == 302

    await db_session.flush()

    count_after_result = await db_session.execute(
        select(func.count(AuditLog.id))
    )
    count_after = count_after_result.scalar() or 0

    assert count_after > count_before

    result = await db_session.execute(
        select(AuditLog)
        .where(AuditLog.action == "User Login")
        .where(AuditLog.user_id == admin_user.id)
        .order_by(AuditLog.timestamp.desc())
        .limit(1)
    )
    login_log = result.scalar_one_or_none()
    assert login_log is not None
    assert login_log.username == admin_user.username
    assert "logged in" in (login_log.details or "").lower()


@pytest.mark.asyncio
async def test_registration_creates_audit_log_entry(client: httpx.AsyncClient, db_session: AsyncSession):
    response = await client.post(
        "/auth/register",
        data={
            "username": "newaudituser",
            "password": "securepass123",
            "confirm_password": "securepass123",
        },
        follow_redirects=False,
    )
    assert response.status_code == 302

    await db_session.flush()

    result = await db_session.execute(
        select(AuditLog)
        .where(AuditLog.action == "User Registered")
        .where(AuditLog.username == "newaudituser")
        .order_by(AuditLog.timestamp.desc())
        .limit(1)
    )
    register_log = result.scalar_one_or_none()
    assert register_log is not None
    assert register_log.username == "newaudituser"
    assert "registered" in (register_log.details or "").lower()


@pytest.mark.asyncio
async def test_audit_log_entry_has_required_fields(db_session: AsyncSession, admin_user: User):
    entry = await log_action(
        db=db_session,
        user_id=admin_user.id,
        username=admin_user.username,
        action="Completeness Check",
        details="Verifying all fields present",
    )
    await db_session.flush()

    result = await db_session.execute(
        select(AuditLog).where(AuditLog.id == entry.id)
    )
    log = result.scalar_one()

    assert log.id is not None
    assert log.timestamp is not None
    assert log.user_id == admin_user.id
    assert log.username == admin_user.username
    assert log.action == "Completeness Check"
    assert log.details == "Verifying all fields present"
    assert log.created_at is not None


@pytest.mark.asyncio
async def test_audit_log_ordered_by_timestamp_desc(db_session: AsyncSession, admin_user: User):
    for i in range(5):
        await log_action(
            db=db_session,
            user_id=admin_user.id,
            username=admin_user.username,
            action=f"Ordered Action {i}",
        )
    await db_session.flush()

    logs, _ = await get_audit_logs(db=db_session, page=1, per_page=50)

    for i in range(len(logs) - 1):
        assert logs[i].timestamp >= logs[i + 1].timestamp


@pytest.mark.asyncio
async def test_audit_log_no_delete_endpoint(admin_client: httpx.AsyncClient, db_session: AsyncSession, admin_user: User):
    entry = await log_action(
        db=db_session,
        user_id=admin_user.id,
        username=admin_user.username,
        action="Immutable Entry",
    )
    await db_session.flush()

    response = await admin_client.request("DELETE", f"/audit-log/{entry.id}")
    assert response.status_code in (404, 405)


@pytest.mark.asyncio
async def test_audit_log_no_put_endpoint(admin_client: httpx.AsyncClient, db_session: AsyncSession, admin_user: User):
    entry = await log_action(
        db=db_session,
        user_id=admin_user.id,
        username=admin_user.username,
        action="Immutable Entry",
    )
    await db_session.flush()

    response = await admin_client.put(
        f"/audit-log/{entry.id}",
        data={"action": "Modified Action"},
    )
    assert response.status_code in (404, 405)


@pytest.mark.asyncio
async def test_job_creation_creates_audit_log(
    admin_client: httpx.AsyncClient,
    db_session: AsyncSession,
    admin_user: User,
):
    response = await admin_client.post(
        "/jobs/create",
        data={
            "title": "Audit Test Engineer",
            "department": "QA",
            "location": "Remote",
            "job_type": "Full-Time",
            "salary_min": "80000",
            "salary_max": "120000",
            "description": "A job created to test audit logging functionality.",
        },
        follow_redirects=False,
    )
    assert response.status_code == 302

    await db_session.flush()

    result = await db_session.execute(
        select(AuditLog)
        .where(AuditLog.action == "Job Created")
        .where(AuditLog.user_id == admin_user.id)
        .order_by(AuditLog.timestamp.desc())
        .limit(1)
    )
    job_log = result.scalar_one_or_none()
    assert job_log is not None
    assert "Audit Test Engineer" in (job_log.details or "")


@pytest.mark.asyncio
async def test_audit_log_page_empty_filters(admin_client: httpx.AsyncClient):
    response = await admin_client.get("/audit-log?action=&user_name=&entity_type=")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_audit_log_page_shows_total_entries(
    admin_client: httpx.AsyncClient,
    db_session: AsyncSession,
    admin_user: User,
):
    for i in range(3):
        await log_action(
            db=db_session,
            user_id=admin_user.id,
            username=admin_user.username,
            action=f"Display Action {i}",
        )
    await db_session.flush()

    response = await admin_client.get("/audit-log")
    assert response.status_code == 200
    assert "total entries" in response.text