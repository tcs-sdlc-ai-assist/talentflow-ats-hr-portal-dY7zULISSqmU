import asyncio
from collections.abc import AsyncGenerator
from typing import Optional

import httpx
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.security import create_session_cookie, hash_password
from app.models.base import Base
from app.models.user import User

# Import all models so Base.metadata knows about them
import app.models  # noqa: F401


TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

engine = create_async_engine(TEST_DATABASE_URL, echo=False, future=True)

test_async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(autouse=True)
async def setup_database():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    async with test_async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


@pytest_asyncio.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[httpx.AsyncClient, None]:
    from app.core.database import get_db
    from app.main import app

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://testserver",
    ) as ac:
        yield ac

    app.dependency_overrides.clear()


async def _create_user(
    db_session: AsyncSession,
    username: str,
    password: str,
    role: str,
) -> User:
    user = User(
        username=username,
        password_hash=hash_password(password),
        role=role,
    )
    db_session.add(user)
    await db_session.flush()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def admin_user(db_session: AsyncSession) -> User:
    return await _create_user(
        db_session,
        username="testadmin",
        password="adminpass123",
        role="System Admin",
    )


@pytest_asyncio.fixture
async def recruiter_user(db_session: AsyncSession) -> User:
    return await _create_user(
        db_session,
        username="testrecruiter",
        password="recruiterpass123",
        role="HR Recruiter",
    )


@pytest_asyncio.fixture
async def hiring_manager_user(db_session: AsyncSession) -> User:
    return await _create_user(
        db_session,
        username="testhiringmgr",
        password="hmpass123",
        role="Hiring Manager",
    )


@pytest_asyncio.fixture
async def interviewer_user(db_session: AsyncSession) -> User:
    return await _create_user(
        db_session,
        username="testinterviewer",
        password="interviewerpass123",
        role="Interviewer",
    )


def _make_auth_cookies(user: User) -> dict[str, str]:
    cookie_value = create_session_cookie(user.id)
    return {"session_token": cookie_value}


@pytest_asyncio.fixture
async def admin_client(
    client: httpx.AsyncClient,
    admin_user: User,
) -> httpx.AsyncClient:
    cookies = _make_auth_cookies(admin_user)
    client.cookies.set("session_token", cookies["session_token"])
    return client


@pytest_asyncio.fixture
async def recruiter_client(
    client: httpx.AsyncClient,
    recruiter_user: User,
) -> httpx.AsyncClient:
    cookies = _make_auth_cookies(recruiter_user)
    client.cookies.set("session_token", cookies["session_token"])
    return client


@pytest_asyncio.fixture
async def hiring_manager_client(
    client: httpx.AsyncClient,
    hiring_manager_user: User,
) -> httpx.AsyncClient:
    cookies = _make_auth_cookies(hiring_manager_user)
    client.cookies.set("session_token", cookies["session_token"])
    return client


@pytest_asyncio.fixture
async def interviewer_client(
    client: httpx.AsyncClient,
    interviewer_user: User,
) -> httpx.AsyncClient:
    cookies = _make_auth_cookies(interviewer_user)
    client.cookies.set("session_token", cookies["session_token"])
    return client