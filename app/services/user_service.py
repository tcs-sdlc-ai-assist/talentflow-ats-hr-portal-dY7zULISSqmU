from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import hash_password, verify_password
from app.models.user import User


async def create_user(
    db: AsyncSession,
    username: str,
    password: str,
    role: str = "Interviewer",
) -> User:
    user = User(
        username=username,
        password_hash=hash_password(password),
        role=role,
    )
    db.add(user)
    await db.flush()
    await db.refresh(user)
    return user


async def authenticate_user(
    db: AsyncSession,
    username: str,
    password: str,
) -> User | None:
    result = await db.execute(
        select(User).where(User.username == username)
    )
    user = result.scalars().first()
    if user is None:
        return None
    if not verify_password(password, user.password_hash):
        return None
    return user


async def get_user_by_id(
    db: AsyncSession,
    user_id: str,
) -> User | None:
    result = await db.execute(
        select(User).where(User.id == user_id)
    )
    return result.scalars().first()


async def get_all_users(
    db: AsyncSession,
) -> list[User]:
    result = await db.execute(select(User))
    return list(result.scalars().all())


async def create_default_admin(db: AsyncSession) -> User | None:
    result = await db.execute(
        select(User).where(User.username == settings.DEFAULT_ADMIN_USERNAME)
    )
    existing = result.scalars().first()
    if existing is not None:
        return None

    admin = await create_user(
        db=db,
        username=settings.DEFAULT_ADMIN_USERNAME,
        password=settings.DEFAULT_ADMIN_PASSWORD,
        role="System Admin",
    )
    return admin