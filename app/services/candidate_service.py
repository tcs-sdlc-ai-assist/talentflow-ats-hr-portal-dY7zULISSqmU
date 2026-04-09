from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.candidate import Candidate, candidate_skills
from app.models.skill import Skill
from app.services.audit_service import log_action


async def create_candidate(
    db: AsyncSession,
    data: dict[str, Any],
    user_id: Optional[str] = None,
    username: Optional[str] = None,
) -> Candidate:
    errors = validate_candidate_data(data)
    if errors:
        raise ValueError("; ".join(errors))

    existing_result = await db.execute(
        select(Candidate).where(Candidate.email == data["email"].strip())
    )
    existing = existing_result.scalar_one_or_none()
    if existing is not None:
        raise ValueError("A candidate with this email already exists.")

    candidate = Candidate(
        first_name=data["first_name"].strip(),
        last_name=data["last_name"].strip(),
        email=data["email"].strip(),
        phone=data.get("phone", "").strip() or None,
        resume_text=data.get("resume_text", "").strip() or None,
        linkedin_url=data.get("linkedin_url", "").strip() or None,
    )
    db.add(candidate)
    await db.flush()
    await db.refresh(candidate)

    await log_action(
        db=db,
        user_id=user_id,
        username=username,
        action="Candidate Created",
        details=f"Candidate '{candidate.first_name} {candidate.last_name}' (ID: {candidate.id}) created",
    )

    return candidate


async def edit_candidate(
    db: AsyncSession,
    candidate_id: str,
    data: dict[str, Any],
    user_id: Optional[str] = None,
    username: Optional[str] = None,
) -> Optional[Candidate]:
    result = await db.execute(
        select(Candidate)
        .where(Candidate.id == candidate_id)
        .options(selectinload(Candidate.skills))
    )
    candidate = result.scalar_one_or_none()
    if candidate is None:
        return None

    errors = validate_candidate_data(data, is_edit=True)
    if errors:
        raise ValueError("; ".join(errors))

    if "email" in data and data["email"].strip():
        new_email = data["email"].strip()
        if new_email != candidate.email:
            dup_result = await db.execute(
                select(Candidate).where(
                    Candidate.email == new_email,
                    Candidate.id != candidate_id,
                )
            )
            dup = dup_result.scalar_one_or_none()
            if dup is not None:
                raise ValueError("A candidate with this email already exists.")
            candidate.email = new_email

    if "first_name" in data and data["first_name"].strip():
        candidate.first_name = data["first_name"].strip()
    if "last_name" in data and data["last_name"].strip():
        candidate.last_name = data["last_name"].strip()
    if "phone" in data:
        candidate.phone = data["phone"].strip() or None
    if "resume_text" in data:
        candidate.resume_text = data["resume_text"].strip() or None
    if "linkedin_url" in data:
        candidate.linkedin_url = data["linkedin_url"].strip() or None

    candidate.updated_at = datetime.utcnow()
    await db.flush()
    await db.refresh(candidate)

    await log_action(
        db=db,
        user_id=user_id,
        username=username,
        action="Candidate Updated",
        details=f"Candidate '{candidate.first_name} {candidate.last_name}' (ID: {candidate.id}) updated",
    )

    return candidate


async def get_candidates(
    db: AsyncSession,
    filters: Optional[dict[str, Any]] = None,
) -> list[Candidate]:
    query = (
        select(Candidate)
        .options(selectinload(Candidate.skills))
        .order_by(Candidate.created_at.desc())
    )

    if filters:
        if filters.get("search"):
            search_term = f"%{filters['search']}%"
            query = query.where(
                (Candidate.first_name.ilike(search_term))
                | (Candidate.last_name.ilike(search_term))
                | (Candidate.email.ilike(search_term))
            )
        if filters.get("skill"):
            skill_name = filters["skill"]
            query = (
                query
                .join(candidate_skills, Candidate.id == candidate_skills.c.candidate_id)
                .join(Skill, Skill.id == candidate_skills.c.skill_id)
                .where(Skill.name == skill_name)
            )

    result = await db.execute(query)
    return list(result.scalars().unique().all())


async def get_candidate(
    db: AsyncSession,
    candidate_id: str,
) -> Optional[Candidate]:
    result = await db.execute(
        select(Candidate)
        .where(Candidate.id == candidate_id)
        .options(
            selectinload(Candidate.skills),
            selectinload(Candidate.applications),
        )
    )
    return result.scalar_one_or_none()


async def add_skill(
    db: AsyncSession,
    candidate_id: str,
    skill_name: str,
    user_id: Optional[str] = None,
    username: Optional[str] = None,
) -> Skill:
    skill_name = skill_name.strip()
    if not skill_name:
        raise ValueError("Skill name is required.")

    result = await db.execute(
        select(Candidate)
        .where(Candidate.id == candidate_id)
        .options(selectinload(Candidate.skills))
    )
    candidate = result.scalar_one_or_none()
    if candidate is None:
        raise ValueError("Candidate not found.")

    skill_result = await db.execute(
        select(Skill).where(Skill.name == skill_name)
    )
    skill = skill_result.scalar_one_or_none()

    if skill is None:
        skill = Skill(name=skill_name)
        db.add(skill)
        await db.flush()
        await db.refresh(skill)

    existing_ids = {s.id for s in candidate.skills}
    if skill.id in existing_ids:
        raise ValueError(f"Skill '{skill_name}' is already assigned to this candidate.")

    candidate.skills.append(skill)
    await db.flush()

    await log_action(
        db=db,
        user_id=user_id,
        username=username,
        action="Skill Added",
        details=f"Skill '{skill_name}' added to candidate '{candidate.first_name} {candidate.last_name}' (ID: {candidate.id})",
    )

    return skill


async def remove_skill(
    db: AsyncSession,
    candidate_id: str,
    skill_id: str,
    user_id: Optional[str] = None,
    username: Optional[str] = None,
) -> None:
    result = await db.execute(
        select(Candidate)
        .where(Candidate.id == candidate_id)
        .options(selectinload(Candidate.skills))
    )
    candidate = result.scalar_one_or_none()
    if candidate is None:
        raise ValueError("Candidate not found.")

    skill_to_remove = None
    for s in candidate.skills:
        if s.id == skill_id:
            skill_to_remove = s
            break

    if skill_to_remove is None:
        raise ValueError("Skill not found on this candidate.")

    candidate.skills.remove(skill_to_remove)
    await db.flush()

    await log_action(
        db=db,
        user_id=user_id,
        username=username,
        action="Skill Removed",
        details=f"Skill '{skill_to_remove.name}' removed from candidate '{candidate.first_name} {candidate.last_name}' (ID: {candidate.id})",
    )


async def get_all_skills(db: AsyncSession) -> list[Skill]:
    result = await db.execute(
        select(Skill).order_by(Skill.name.asc())
    )
    return list(result.scalars().all())


def validate_candidate_data(
    data: dict[str, Any],
    is_edit: bool = False,
) -> list[str]:
    errors: list[str] = []

    if not is_edit:
        if not data.get("first_name", "").strip():
            errors.append("First name is required.")
        if not data.get("last_name", "").strip():
            errors.append("Last name is required.")
        if not data.get("email", "").strip():
            errors.append("Email is required.")
        elif "@" not in data["email"]:
            errors.append("Email must be a valid email address.")
    else:
        if "first_name" in data and not data["first_name"].strip():
            errors.append("First name cannot be empty.")
        if "last_name" in data and not data["last_name"].strip():
            errors.append("Last name cannot be empty.")
        if "email" in data:
            email = data["email"].strip()
            if not email:
                errors.append("Email cannot be empty.")
            elif "@" not in email:
                errors.append("Email must be a valid email address.")

    linkedin_url = data.get("linkedin_url", "").strip()
    if linkedin_url and not (linkedin_url.startswith("http://") or linkedin_url.startswith("https://")):
        errors.append("LinkedIn URL must start with http:// or https://.")

    return errors