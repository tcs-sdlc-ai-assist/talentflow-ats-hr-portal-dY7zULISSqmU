from pathlib import Path

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import UserRole
from app.core.database import get_db
from app.dependencies.auth import get_current_user
from app.dependencies.rbac import require_roles
from app.models.user import User
from app.services.candidate_service import (
    add_skill,
    create_candidate,
    edit_candidate,
    get_all_skills,
    get_candidate,
    get_candidates,
    remove_skill,
)

router = APIRouter(prefix="/candidates", tags=["candidates"])

templates = Jinja2Templates(
    directory=str(Path(__file__).resolve().parent.parent / "templates")
)

ALLOWED_ROLES = [UserRole.SYSTEM_ADMIN, UserRole.HR_RECRUITER, UserRole.HIRING_MANAGER, UserRole.INTERVIEWER]
EDIT_ROLES = [UserRole.SYSTEM_ADMIN, UserRole.HR_RECRUITER, UserRole.HIRING_MANAGER]


@router.get("")
async def candidate_list(
    request: Request,
    search: str = "",
    skill: str = "",
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    filters = {}
    if search:
        filters["search"] = search
    if skill:
        filters["skill"] = skill

    candidates_list = await get_candidates(db, filters=filters if filters else None)
    all_skills = await get_all_skills(db)

    enriched_candidates = []
    for c in candidates_list:
        c.name = f"{c.first_name} {c.last_name}"
        enriched_candidates.append(c)

    return templates.TemplateResponse(
        request,
        "candidates/candidate_list.html",
        context={
            "user": user,
            "candidates": enriched_candidates,
            "skills": all_skills,
            "search": search,
            "selected_skill": skill,
        },
    )


@router.get("/create")
async def candidate_create_form(
    request: Request,
    user: User = Depends(require_roles(EDIT_ROLES)),
):
    return templates.TemplateResponse(
        request,
        "candidates/candidate_form.html",
        context={
            "user": user,
            "candidate": None,
            "form_data": None,
            "errors": None,
        },
    )


@router.post("/create")
async def candidate_create_submit(
    request: Request,
    first_name: str = Form(""),
    last_name: str = Form(""),
    email: str = Form(""),
    phone: str = Form(""),
    linkedin_url: str = Form(""),
    resume_text: str = Form(""),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_roles(EDIT_ROLES)),
):
    form_data = {
        "first_name": first_name,
        "last_name": last_name,
        "email": email,
        "phone": phone,
        "linkedin_url": linkedin_url,
        "resume_text": resume_text,
    }

    try:
        candidate = await create_candidate(
            db=db,
            data=form_data,
            user_id=user.id,
            username=user.username,
        )
        return RedirectResponse(url=f"/candidates/{candidate.id}", status_code=302)
    except ValueError as e:
        errors = str(e).split("; ")
        return templates.TemplateResponse(
            request,
            "candidates/candidate_form.html",
            context={
                "user": user,
                "candidate": None,
                "form_data": type("FormData", (), form_data)(),
                "errors": errors,
            },
            status_code=400,
        )


@router.get("/{candidate_id}")
async def candidate_detail(
    request: Request,
    candidate_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    candidate = await get_candidate(db, candidate_id)
    if candidate is None:
        return RedirectResponse(url="/candidates", status_code=302)

    candidate.name = f"{candidate.first_name} {candidate.last_name}"

    skills = candidate.skills if candidate.skills else []
    applications = candidate.applications if candidate.applications else []

    return templates.TemplateResponse(
        request,
        "candidates/candidate_detail.html",
        context={
            "user": user,
            "candidate": candidate,
            "skills": skills,
            "applications": applications,
        },
    )


@router.get("/{candidate_id}/edit")
async def candidate_edit_form(
    request: Request,
    candidate_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_roles(EDIT_ROLES)),
):
    candidate = await get_candidate(db, candidate_id)
    if candidate is None:
        return RedirectResponse(url="/candidates", status_code=302)

    candidate.name = f"{candidate.first_name} {candidate.last_name}"

    return templates.TemplateResponse(
        request,
        "candidates/candidate_form.html",
        context={
            "user": user,
            "candidate": candidate,
            "form_data": None,
            "errors": None,
        },
    )


@router.post("/{candidate_id}/edit")
async def candidate_edit_submit(
    request: Request,
    candidate_id: str,
    first_name: str = Form(""),
    last_name: str = Form(""),
    email: str = Form(""),
    phone: str = Form(""),
    linkedin_url: str = Form(""),
    resume_text: str = Form(""),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_roles(EDIT_ROLES)),
):
    form_data = {
        "first_name": first_name,
        "last_name": last_name,
        "email": email,
        "phone": phone,
        "linkedin_url": linkedin_url,
        "resume_text": resume_text,
    }

    try:
        candidate = await edit_candidate(
            db=db,
            candidate_id=candidate_id,
            data=form_data,
            user_id=user.id,
            username=user.username,
        )
        if candidate is None:
            return RedirectResponse(url="/candidates", status_code=302)
        return RedirectResponse(url=f"/candidates/{candidate.id}", status_code=302)
    except ValueError as e:
        errors = str(e).split("; ")

        existing_candidate = await get_candidate(db, candidate_id)
        if existing_candidate is None:
            return RedirectResponse(url="/candidates", status_code=302)

        existing_candidate.name = f"{existing_candidate.first_name} {existing_candidate.last_name}"

        return templates.TemplateResponse(
            request,
            "candidates/candidate_form.html",
            context={
                "user": user,
                "candidate": existing_candidate,
                "form_data": type("FormData", (), form_data)(),
                "errors": errors,
            },
            status_code=400,
        )


@router.post("/{candidate_id}/skills")
async def candidate_add_skill(
    request: Request,
    candidate_id: str,
    skill_name: str = Form(""),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_roles(EDIT_ROLES)),
):
    try:
        await add_skill(
            db=db,
            candidate_id=candidate_id,
            skill_name=skill_name,
            user_id=user.id,
            username=user.username,
        )
    except ValueError:
        pass

    return RedirectResponse(url=f"/candidates/{candidate_id}", status_code=302)


@router.post("/{candidate_id}/skills/{skill_id}/remove")
async def candidate_remove_skill(
    request: Request,
    candidate_id: str,
    skill_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_roles(EDIT_ROLES)),
):
    try:
        await remove_skill(
            db=db,
            candidate_id=candidate_id,
            skill_id=skill_id,
            user_id=user.id,
            username=user.username,
        )
    except ValueError:
        pass

    return RedirectResponse(url=f"/candidates/{candidate_id}", status_code=302)