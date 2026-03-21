"""Admin-only: user management and topic unit CRUD."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.deps import get_current_admin
from app.db.session import get_db
from app.models.conversation import Topic, TopicUnit
from app.models.role import ROLE_ADMIN, Role, UserRole
from app.models.user import User
from app.schemas.admin import (
    AdminUserListOut,
    AdminUserOut,
    AdminUserPatch,
    TopicUnitCreateIn,
    TopicUnitUpdateIn,
)
from app.schemas.roadmap import TopicUnitOut

router = APIRouter()


async def _count_distinct_admin_users(db: AsyncSession) -> int:
    q = await db.execute(
        select(func.count(func.distinct(UserRole.user_id)))
        .select_from(UserRole)
        .join(Role, Role.id == UserRole.role_id)
        .where(Role.name == ROLE_ADMIN)
    )
    return int(q.scalar() or 0)


async def _user_has_admin(db: AsyncSession, user_id: int) -> bool:
    q = await db.execute(
        select(UserRole.user_id)
        .join(Role, Role.id == UserRole.role_id)
        .where(UserRole.user_id == user_id, Role.name == ROLE_ADMIN)
        .limit(1)
    )
    return q.scalar_one_or_none() is not None


@router.get("/users", response_model=AdminUserListOut)
async def admin_list_users(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(get_current_admin),
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


@router.patch("/users/{user_id}", response_model=AdminUserOut)
async def admin_patch_user(
    user_id: int,
    body: AdminUserPatch,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_admin),
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
        had_admin = await _user_has_admin(db, user_id)
        will_have_admin = ROLE_ADMIN in slugs
        if had_admin and not will_have_admin:
            if await _count_distinct_admin_users(db) <= 1:
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


@router.post(
    "/topics/{topic_id}/units",
    response_model=TopicUnitOut,
    status_code=201,
)
async def admin_create_topic_unit(
    topic_id: int,
    body: TopicUnitCreateIn,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(get_current_admin),
) -> TopicUnitOut:
    t = await db.get(Topic, topic_id)
    if not t:
        raise HTTPException(status_code=404, detail="Topic not found")
    unit = TopicUnit(
        topic_id=topic_id,
        sort_order=body.sort_order,
        title=body.title.strip(),
        objective=body.objective.strip(),
        prompt_hint=body.prompt_hint.strip(),
        min_turns_to_complete=body.min_turns_to_complete,
        min_avg_overall=body.min_avg_overall,
        max_scored_turns=body.max_scored_turns,
    )
    db.add(unit)
    await db.commit()
    await db.refresh(unit)
    return TopicUnitOut.model_validate(unit)


@router.patch(
    "/topics/{topic_id}/units/{unit_id}",
    response_model=TopicUnitOut,
)
async def admin_update_topic_unit(
    topic_id: int,
    unit_id: int,
    body: TopicUnitUpdateIn,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(get_current_admin),
) -> TopicUnitOut:
    unit = await db.get(TopicUnit, unit_id)
    if not unit or unit.topic_id != topic_id:
        raise HTTPException(status_code=404, detail="Topic unit not found")
    if body.sort_order is not None:
        unit.sort_order = body.sort_order
    if body.title is not None:
        unit.title = body.title.strip()
    if body.objective is not None:
        unit.objective = body.objective.strip()
    if body.prompt_hint is not None:
        unit.prompt_hint = body.prompt_hint.strip()
    if body.min_turns_to_complete is not None:
        unit.min_turns_to_complete = body.min_turns_to_complete
    if body.min_avg_overall is not None:
        unit.min_avg_overall = body.min_avg_overall
    patch_data = body.model_dump(exclude_unset=True)
    if "max_scored_turns" in patch_data:
        unit.max_scored_turns = patch_data["max_scored_turns"]
    await db.commit()
    await db.refresh(unit)
    return TopicUnitOut.model_validate(unit)


@router.delete("/topics/{topic_id}/units/{unit_id}", status_code=204)
async def admin_delete_topic_unit(
    topic_id: int,
    unit_id: int,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(get_current_admin),
) -> None:
    unit = await db.get(TopicUnit, unit_id)
    if not unit or unit.topic_id != topic_id:
        raise HTTPException(status_code=404, detail="Topic unit not found")
    await db.delete(unit)
    await db.commit()
