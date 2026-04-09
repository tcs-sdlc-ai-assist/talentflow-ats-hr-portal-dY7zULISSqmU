from __future__ import annotations

from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_log import AuditLog


async def log_action(
    db: AsyncSession,
    user_id: Optional[str],
    username: Optional[str],
    action: str,
    details: Optional[str] = None,
) -> AuditLog:
    entry = AuditLog(
        user_id=user_id,
        username=username,
        action=action,
        details=details,
    )
    db.add(entry)
    await db.flush()
    return entry


async def get_audit_logs(
    db: AsyncSession,
    page: int = 1,
    per_page: int = 20,
    action_filter: Optional[str] = None,
    user_name_filter: Optional[str] = None,
    entity_type_filter: Optional[str] = None,
) -> tuple[list[AuditLog], int]:
    base_query = select(AuditLog)
    count_query = select(func.count()).select_from(AuditLog)

    if action_filter:
        base_query = base_query.where(AuditLog.action.ilike(f"%{action_filter}%"))
        count_query = count_query.where(AuditLog.action.ilike(f"%{action_filter}%"))

    if user_name_filter:
        base_query = base_query.where(AuditLog.username.ilike(f"%{user_name_filter}%"))
        count_query = count_query.where(AuditLog.username.ilike(f"%{user_name_filter}%"))

    if entity_type_filter:
        base_query = base_query.where(AuditLog.details.ilike(f"%{entity_type_filter}%"))
        count_query = count_query.where(AuditLog.details.ilike(f"%{entity_type_filter}%"))

    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    offset = (page - 1) * per_page
    query = (
        base_query
        .order_by(AuditLog.timestamp.desc())
        .offset(offset)
        .limit(per_page)
    )

    result = await db.execute(query)
    logs = list(result.scalars().all())

    return logs, total