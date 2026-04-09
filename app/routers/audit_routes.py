from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.dependencies.auth import get_current_user
from app.dependencies.rbac import require_roles
from app.models.user import User
from app.services.audit_service import get_audit_logs

router = APIRouter(tags=["audit"])

templates = Jinja2Templates(
    directory=str(Path(__file__).resolve().parent.parent / "templates")
)


@router.get("/audit-log")
async def audit_log_page(
    request: Request,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    action: Optional[str] = Query(None),
    user_name: Optional[str] = Query(None),
    entity_type: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_roles(["System Admin", "HR Recruiter"])),
):
    logs, total = await get_audit_logs(
        db=db,
        page=page,
        per_page=page_size,
        action_filter=action if action and action.strip() else None,
        user_name_filter=user_name if user_name and user_name.strip() else None,
        entity_type_filter=entity_type if entity_type and entity_type.strip() else None,
    )

    filters = {
        "action": action or "",
        "user_name": user_name or "",
        "entity_type": entity_type or "",
    }

    total_pages = max(1, (total + page_size - 1) // page_size)

    return templates.TemplateResponse(
        request,
        "audit_log.html",
        context={
            "user": user,
            "logs": logs,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": total_pages,
            "filters": filters,
        },
    )