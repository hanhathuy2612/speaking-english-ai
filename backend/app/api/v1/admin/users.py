"""Admin user listing and role / active flag updates."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.v1.admin.constants import ADMIN_USERS_MAX_LIMIT
from app.api.v1.admin.supporting import count_distinct_admin_users, user_has_admin
from app.core.deps import get_current_admin
from app.db.session import get_db
from app.models.role import ROLE_ADMIN, Role, UserRole
from app.models.user import User
from app.schemas.admin import AdminUserListOut, AdminUserOut, AdminUserPatch

router = APIRouter()


@router.get("/users", responses={404: {"description": "User not found"}})
async def admin_list_users(
    db: Annotated[AsyncSession, Depends(get_db)],
    _admin: Annotated[User, Depends(get_current_admin)],
    page: Annotated[int, Query(ge=1)] = 1,
    limit: Annotated[int, Query(ge=1, le=ADMIN_USERS_MAX_LIMIT)] = 20,
) -> AdminUserListOut:
    total_q = await db.execute(select(func.count()).select_from(User))
    total = int(total_q.scalar() or 0)
    offset = (page - 1) * limit
    r = await db.execute(
        select(User)
        .options(selectinload(User.role_memberships).selectinload(UserRole.role))
        .order_by(User.id)
        .offset(offset)
        .limit(limit)
    )
    users = r.scalars().unique().all()
    items = []
    for u in users:
        roles = sorted({m.role.name for m in u.role_memberships})
        items.append(
            AdminUserOut(
                id=u.id,
                email=u.email,
                username=u.username,
                is_active=u.is_active,
                roles=roles,
                created_at=u.created_at.isoformat(),
            )
        )
    return AdminUserListOut(items=items, total=total)


@router.patch(
    "/users/{user_id}",
    responses={
        404: {"description": "User not found"},
        400: {"description": "Invalid request"},
    },
)
async def admin_patch_user(
    user_id: int,
    body: AdminUserPatch,
    db: Annotated[AsyncSession, Depends(get_db)],
    admin: Annotated[User, Depends(get_current_admin)],
) -> AdminUserOut:
    r = await db.execute(
        select(User)
        .options(selectinload(User.role_memberships).selectinload(UserRole.role))
        .where(User.id == user_id)
    )
    target = r.scalar_one_or_none()
    if not target:
        raise HTTPException(status_code=404, detail="User not found")

    if body.role_slugs is not None:
        slugs = sorted(set(body.role_slugs))
        if not slugs:
            raise HTTPException(
                status_code=400, detail="role_slugs must include at least one role"
            )
        had_admin = await user_has_admin(db, user_id)
        will_have_admin = ROLE_ADMIN in slugs
        if had_admin and not will_have_admin:
            if await count_distinct_admin_users(db) <= 1:
                raise HTTPException(
                    status_code=400,
                    detail="Cannot remove the last admin user",
                )
        roles_result = await db.execute(select(Role).where(Role.name.in_(slugs)))
        found = {role.name: role for role in roles_result.scalars().all()}
        missing = [s for s in slugs if s not in found]
        if missing:
            raise HTTPException(
                status_code=400,
                detail=f"Unknown role slugs: {', '.join(missing)}",
            )
        await db.execute(delete(UserRole).where(UserRole.user_id == user_id))
        for slug in slugs:
            db.add(UserRole(user_id=user_id, role_id=found[slug].id))
        await db.flush()

    if body.is_active is not None:
        if not body.is_active and user_id == admin.id:
            raise HTTPException(
                status_code=400, detail="You cannot deactivate your own account here"
            )
        target.is_active = body.is_active

    await db.commit()
    await db.refresh(target)
    r2 = await db.execute(
        select(User)
        .options(selectinload(User.role_memberships).selectinload(UserRole.role))
        .where(User.id == user_id)
    )
    target = r2.scalar_one()
    roles = sorted({m.role.name for m in target.role_memberships})
    return AdminUserOut(
        id=target.id,
        email=target.email,
        username=target.username,
        is_active=target.is_active,
        roles=roles,
        created_at=target.created_at.isoformat(),
    )
