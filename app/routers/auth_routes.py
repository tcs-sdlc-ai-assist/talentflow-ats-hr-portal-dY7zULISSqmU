from pathlib import Path

from fastapi import APIRouter, Depends, Form, Request, Response
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import create_session_cookie, hash_password, verify_password
from app.dependencies.auth import get_optional_user
from app.models.user import User
from app.services.audit_service import log_action

router = APIRouter(prefix="/auth", tags=["auth"])

templates = Jinja2Templates(
    directory=str(Path(__file__).resolve().parent.parent / "templates")
)


@router.get("/login")
async def login_page(
    request: Request,
    user: User | None = Depends(get_optional_user),
):
    if user is not None:
        return RedirectResponse(url="/dashboard", status_code=302)

    return templates.TemplateResponse(
        request,
        "auth/login.html",
        context={"error": None, "username": ""},
    )


@router.post("/login")
async def login_submit(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).where(User.username == username))
    user = result.scalars().first()

    if user is None or not verify_password(password, user.password_hash):
        return templates.TemplateResponse(
            request,
            "auth/login.html",
            context={
                "error": "Invalid username or password.",
                "username": username,
            },
            status_code=400,
        )

    session_cookie = create_session_cookie(user.id)

    await log_action(
        db=db,
        user_id=user.id,
        username=user.username,
        action="User Login",
        details=f"User '{user.username}' logged in",
    )

    if user.role == "System Admin" or user.role == "HR Recruiter":
        redirect_url = "/dashboard"
    elif user.role == "Hiring Manager":
        redirect_url = "/dashboard"
    elif user.role == "Interviewer":
        redirect_url = "/dashboard"
    else:
        redirect_url = "/dashboard"

    response = RedirectResponse(url=redirect_url, status_code=302)
    response.set_cookie(
        key="session_token",
        value=session_cookie,
        httponly=True,
        samesite="lax",
        max_age=3600,
    )
    return response


@router.get("/register")
async def register_page(
    request: Request,
    user: User | None = Depends(get_optional_user),
):
    if user is not None:
        return RedirectResponse(url="/dashboard", status_code=302)

    return templates.TemplateResponse(
        request,
        "auth/register.html",
        context={"error": None, "errors": None, "username": ""},
    )


@router.post("/register")
async def register_submit(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    confirm_password: str = Form(...),
    db: AsyncSession = Depends(get_db),
):
    errors: list[str] = []

    if not username or len(username.strip()) < 3:
        errors.append("Username must be at least 3 characters long.")

    if not password or len(password) < 8:
        errors.append("Password must be at least 8 characters long.")

    if password != confirm_password:
        errors.append("Passwords do not match.")

    if errors:
        return templates.TemplateResponse(
            request,
            "auth/register.html",
            context={
                "error": None,
                "errors": errors,
                "username": username,
            },
            status_code=400,
        )

    result = await db.execute(
        select(User).where(User.username == username.strip())
    )
    existing_user = result.scalars().first()

    if existing_user is not None:
        return templates.TemplateResponse(
            request,
            "auth/register.html",
            context={
                "error": "A user with that username already exists.",
                "errors": None,
                "username": username,
            },
            status_code=400,
        )

    new_user = User(
        username=username.strip(),
        password_hash=hash_password(password),
        role="Interviewer",
    )
    db.add(new_user)
    await db.flush()
    await db.refresh(new_user)

    await log_action(
        db=db,
        user_id=new_user.id,
        username=new_user.username,
        action="User Registered",
        details=f"New user '{new_user.username}' registered with role 'Interviewer'",
    )

    session_cookie = create_session_cookie(new_user.id)

    response = RedirectResponse(url="/dashboard", status_code=302)
    response.set_cookie(
        key="session_token",
        value=session_cookie,
        httponly=True,
        samesite="lax",
        max_age=3600,
    )
    return response


@router.post("/logout")
async def logout(
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User | None = Depends(get_optional_user),
):
    if user is not None:
        await log_action(
            db=db,
            user_id=user.id,
            username=user.username,
            action="User Logout",
            details=f"User '{user.username}' logged out",
        )

    response = RedirectResponse(url="/", status_code=302)
    response.delete_cookie(key="session_token")
    return response