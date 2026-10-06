from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_optional_current_user, require_permissions
from app.core.responses import paginated_response, success_response
from app.crud import like as crud_like
from app.crud import post as crud_post
from app.db.session import get_db
from app.models.user import User
from app.schemas.common.response import APIResponse, PaginatedResponse
from app.schemas.like import LikeToggleResponse, LikeUserRead
from app.schemas.post import PostCreate, PostRead, PostUpdate

router = APIRouter(prefix="/posts", tags=["posts"])
DB = Annotated[AsyncSession, Depends(get_db)]


@router.get("/", response_model=PaginatedResponse[PostRead])
async def list_posts(
    db: DB,
    current_user: Annotated[User | None, Depends(get_optional_current_user)],
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
):
    current_user_id = current_user.id if current_user else None
    posts, total = await crud_post.get_posts(db, page, limit, current_user_id)
    return paginated_response(
        items=posts,
        total=total,
        page=page,
        limit=limit,
        message="Posts retrieved successfully",
    )


@router.get("/{post_id}", response_model=APIResponse[PostRead])
async def read_post(
    post_id: int,
    db: DB,
    current_user: Annotated[User | None, Depends(get_optional_current_user)],
):
    current_user_id = current_user.id if current_user else None
    post = await crud_post.get_post(db, post_id, current_user_id)
    if not post:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Post not found")
    return success_response(data=post, message="Post retrieved successfully")


@router.post(
    "/",
    response_model=APIResponse[PostRead],
    status_code=status.HTTP_201_CREATED,
)
async def create_post(
    data: PostCreate,
    db: DB,
    current_user: Annotated[User, Depends(require_permissions("post:create"))],
):
    post = await crud_post.create_post(db, data, current_user)
    return success_response(
        data=post,
        message="Post created successfully",
        status_code=status.HTTP_201_CREATED,
    )


@router.patch("/{post_id}", response_model=APIResponse[PostRead])
async def update_post(
    post_id: int,
    data: PostUpdate,
    db: DB,
    current_user: Annotated[User, Depends(get_current_user)],
):
    post = await crud_post.update_post(db, post_id, data, current_user)
    return success_response(data=post, message="Post updated successfully")


@router.delete("/{post_id}", response_model=APIResponse[None])
async def delete_post(
    post_id: int,
    db: DB,
    current_user: Annotated[User, Depends(get_current_user)],
):
    await crud_post.delete_post(db, post_id, current_user)
    return success_response(message="Post deleted successfully")


# --- Post Likes Endpoints ---


@router.post("/{post_id}/like", response_model=APIResponse[LikeToggleResponse])
async def like_post(
    post_id: int,
    db: DB,
    current_user: Annotated[User, Depends(require_permissions("like:create"))],
):
    liked, count = await crud_like.like_post(db, current_user.id, post_id)
    return success_response(
        data=LikeToggleResponse(liked=liked, likes_count=count, message="Post liked"),
        message="Post liked successfully",
    )


@router.delete("/{post_id}/like", response_model=APIResponse[LikeToggleResponse])
async def unlike_post(
    post_id: int,
    db: DB,
    current_user: Annotated[User, Depends(require_permissions("like:create"))],
):
    liked, count = await crud_like.unlike_post(db, current_user.id, post_id)
    return success_response(
        data=LikeToggleResponse(liked=liked, likes_count=count, message="Post unliked"),
        message="Post unliked successfully",
    )


@router.get("/{post_id}/likes", response_model=PaginatedResponse[LikeUserRead])
async def get_post_likes(
    post_id: int,
    db: DB,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
):
    likes, total = await crud_like.get_post_likes(db, post_id, page, limit)
    return paginated_response(
        items=likes,
        total=total,
        page=page,
        limit=limit,
        message="Post likes retrieved successfully",
    )