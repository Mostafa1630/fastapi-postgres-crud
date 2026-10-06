from typing import Annotated
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import map_user_read
from app.api.deps import require_permissions
from app.core.responses import paginated_response, success_response
from app.crud import user as crud_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.auth import UserRead, UserRoleUpdate, UserStatusUpdate
from app.schemas.common.response import APIResponse, PaginatedResponse

router = APIRouter(prefix="/admin", tags=["admin"])
DB = Annotated[AsyncSession, Depends(get_db)]


@router.get(
    "/users",
    response_model=PaginatedResponse[UserRead],
    dependencies=[Depends(require_permissions("user:manage"))],
)
async def list_users(
    db: DB,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
):
    users, total = await crud_user.get_users(db, page, limit)
    items = [map_user_read(u) for u in users]
    return paginated_response(
        items=items,
        total=total,
        page=page,
        limit=limit,
        message="Users retrieved successfully",
    )


@router.patch(
    "/users/{user_id}/role",
    response_model=APIResponse[UserRead],
    dependencies=[Depends(require_permissions("role:manage"))],
)
async def update_role(
    user_id: int,
    data: UserRoleUpdate,
    db: DB,
):
    updated_user = await crud_user.update_user_role(db, user_id, data.role_name)
    return success_response(
        data=map_user_read(updated_user),
        message=f"User role successfully updated to {data.role_name}",
    )


@router.patch(
    "/users/{user_id}/status",
    response_model=APIResponse[UserRead],
    dependencies=[Depends(require_permissions("user:manage"))],
)
async def update_status(
    user_id: int,
    data: UserStatusUpdate,
    db: DB,
):
    updated_user = await crud_user.update_user_status(db, user_id, data.is_active)
    status_str = "activated" if data.is_active else "deactivated"
    return success_response(
        data=map_user_read(updated_user),
        message=f"User successfully {status_str}",
    )
