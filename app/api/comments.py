from typing import Annotated
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_optional_current_user, require_permissions
from app.core.responses import paginated_response, success_response
from app.crud import comment as crud_comment
from app.crud import like as crud_like
from app.db.session import get_db
from app.models.user import User
from app.schemas.comment import CommentCreate, CommentRead, CommentUpdate
from app.schemas.common.response import APIResponse, PaginatedResponse
from app.schemas.like import LikeToggleResponse, LikeUserRead

router = APIRouter(tags=["comments"])
DB = Annotated[AsyncSession, Depends(get_db)]


@router.get("/posts/{post_id}/comments", response_model=PaginatedResponse[CommentRead])
async def list_comments_for_post(
    post_id: int,
    db: DB,
    current_user: Annotated[User | None, Depends(get_optional_current_user)],
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
):
    current_user_id = current_user.id if current_user else None
    comments, total = await crud_comment.get_comments(
        db, post_id, page, limit, current_user_id
    )
    return paginated_response(
        items=comments,
        total=total,
        page=page,
        limit=limit,
        message="Comments retrieved successfully",
    )


@router.post(
    "/posts/{post_id}/comments",
    response_model=APIResponse[CommentRead],
    status_code=status.HTTP_201_CREATED,
)
async def create_comment_for_post(
    post_id: int,
    data: CommentCreate,
    db: DB,
    current_user: Annotated[User, Depends(require_permissions("comment:create"))],
):
    comment = await crud_comment.create_comment(db, post_id, data, current_user)
    return success_response(
        data=comment,
        message="Comment created successfully",
        status_code=status.HTTP_201_CREATED,
    )


@router.patch("/comments/{comment_id}", response_model=APIResponse[CommentRead])
async def update_comment(
    comment_id: int,
    data: CommentUpdate,
    db: DB,
    current_user: Annotated[User, Depends(get_current_user)],
):
    comment = await crud_comment.update_comment(db, comment_id, data, current_user)
    return success_response(
        data=comment,
        message="Comment updated successfully",
    )


@router.delete("/comments/{comment_id}", response_model=APIResponse[None])
async def delete_comment(
    comment_id: int,
    db: DB,
    current_user: Annotated[User, Depends(get_current_user)],
):
    await crud_comment.delete_comment(db, comment_id, current_user)
    return success_response(
        message="Comment deleted successfully",
    )


# --- Comment Likes Endpoints ---


@router.post("/comments/{comment_id}/like", response_model=APIResponse[LikeToggleResponse])
async def like_comment(
    comment_id: int,
    db: DB,
    current_user: Annotated[User, Depends(require_permissions("like:create"))],
):
    liked, count = await crud_like.like_comment(db, current_user.id, comment_id)
    return success_response(
        data=LikeToggleResponse(liked=liked, likes_count=count, message="Comment liked"),
        message="Comment liked successfully",
    )


@router.delete("/comments/{comment_id}/like", response_model=APIResponse[LikeToggleResponse])
async def unlike_comment(
    comment_id: int,
    db: DB,
    current_user: Annotated[User, Depends(require_permissions("like:create"))],
):
    liked, count = await crud_like.unlike_comment(db, current_user.id, comment_id)
    return success_response(
        data=LikeToggleResponse(liked=liked, likes_count=count, message="Comment unliked"),
        message="Comment unliked successfully",
    )


@router.get("/comments/{comment_id}/likes", response_model=PaginatedResponse[LikeUserRead])
async def get_comment_likes(
    comment_id: int,
    db: DB,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
):
    likes, total = await crud_like.get_comment_likes(db, comment_id, page, limit)
    return paginated_response(
        items=likes,
        total=total,
        page=page,
        limit=limit,
        message="Comment likes retrieved successfully",
    )
