from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload

from app.models.rbac import Role
from app.models.user import User


async def get_users(
    db: AsyncSession, page: int = 1, limit: int = 20
) -> tuple[list[User], int]:
    total = await db.scalar(select(func.count()).select_from(User)) or 0
    result = await db.execute(
        select(User)
        .options(joinedload(User.role).selectinload(Role.permissions))
        .order_by(User.id.asc())
        .offset((page - 1) * limit)
        .limit(limit)
    )
    return list(result.scalars().all()), total


async def get_user_by_id(db: AsyncSession, user_id: int) -> User | None:
    result = await db.execute(
        select(User)
        .where(User.id == user_id)
        .options(joinedload(User.role).selectinload(Role.permissions))
    )
    return result.scalar_one_or_none()


async def update_user_role(db: AsyncSession, user_id: int, role_name: str) -> User:
    user = await get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    role = await db.scalar(select(Role).where(Role.name == role_name))
    if not role:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Role '{role_name}' does not exist",
        )

    user.role_id = role.id
    await db.commit()
    await db.refresh(user)

    result = await db.execute(
        select(User)
        .where(User.id == user.id)
        .options(joinedload(User.role).selectinload(Role.permissions))
    )
    return result.scalar_one()


async def update_user_status(db: AsyncSession, user_id: int, is_active: bool) -> User:
    user = await get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    user.is_active = is_active
    await db.commit()
    await db.refresh(user)

    result = await db.execute(
        select(User)
        .where(User.id == user.id)
        .options(joinedload(User.role).selectinload(Role.permissions))
    )
    return result.scalar_one()
