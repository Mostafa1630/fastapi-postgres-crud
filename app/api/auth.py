from typing import Annotated
from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.limiter import limiter
from app.core.responses import success_response
from app.crud import auth as crud_auth
from app.db.session import get_db
from app.models.user import User
from app.schemas.auth import (
    RefreshTokenRequest,
    TokenResponse,
    UserLogin,
    UserRead,
    UserRegister,
)
from app.schemas.common.response import APIResponse

router = APIRouter(prefix="/auth", tags=["auth"])
DB = Annotated[AsyncSession, Depends(get_db)]


def map_user_read(user: User) -> UserRead:
    role_name = user.role.name if user.role else "user"
    perms = [p.name for p in user.role.permissions] if user.role and user.role.permissions else []
    return UserRead(
        id=user.id,
        username=user.username,
        email=user.email,
        is_active=user.is_active,
        role=role_name,
        permissions=perms,
        created_at=user.created_at,
    )


@router.post(
    "/register",
    response_model=APIResponse[UserRead],
    status_code=status.HTTP_201_CREATED,
)
@limiter.limit("5/minute")
async def register(
    request: Request,
    data: UserRegister,
    db: DB,
):
    user = await crud_auth.register_user(db, data)
    return success_response(
        data=map_user_read(user),
        message="User registered successfully",
        status_code=status.HTTP_201_CREATED,
    )


@router.post(
    "/login",
    response_model=APIResponse[TokenResponse],
)
@limiter.limit("5/minute")
async def login(
    request: Request,
    data: UserLogin,
    db: DB,
):
    tokens = await crud_auth.login_user(db, data)
    return success_response(
        data=tokens,
        message="Login successful",
    )


@router.post(
    "/refresh",
    response_model=APIResponse[TokenResponse],
)
@limiter.limit("5/minute")
async def refresh_token(
    request: Request,
    data: RefreshTokenRequest,
    db: DB,
):
    new_tokens = await crud_auth.rotate_refresh_token(db, data.refresh_token)
    return success_response(
        data=new_tokens,
        message="Token refreshed successfully",
    )


@router.post(
    "/logout",
    response_model=APIResponse[None],
)
async def logout(
    data: RefreshTokenRequest,
    db: DB,
):
    await crud_auth.revoke_refresh_token(db, data.refresh_token)
    return success_response(
        message="Logged out successfully",
    )


@router.post(
    "/logout-all",
    response_model=APIResponse[None],
)
async def logout_all(
    current_user: Annotated[User, Depends(get_current_user)],
    db: DB,
):
    await crud_auth.revoke_all_user_tokens(db, current_user.id)
    return success_response(
        message="All sessions revoked successfully",
    )


@router.get(
    "/me",
    response_model=APIResponse[UserRead],
)
async def get_me(
    current_user: Annotated[User, Depends(get_current_user)],
):
    return success_response(
        data=map_user_read(current_user),
        message="User profile retrieved successfully",
    )
