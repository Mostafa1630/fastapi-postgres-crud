# endpoints
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.responses import paginated_response, success_response
from app.crud import post as crud
from app.db.session import get_db
from app.schemas.common.response import APIResponse, PaginatedResponse
from app.schemas.post import PostCreate, PostRead, PostUpdate

router = APIRouter(prefix="/posts", tags=["posts"])

DB = Annotated[AsyncSession, Depends(get_db)]


@router.get("/", response_model=PaginatedResponse[PostRead])
async def list_posts(
    db: DB,
    page: int = Query(1, ge=1),
    limit: int = Query(5, ge=1, le=100),
):
    posts, total = await crud.get_posts(db, page, limit)
    return paginated_response(
        items=posts,
        total=total,
        page=page,
        limit=limit,
        message="Posts retrieved successfully",
    )


@router.get("/{post_id}", response_model=APIResponse[PostRead])
async def read_post(post_id: int, db: DB):
    post = await crud.get_post(db, post_id)
    if not post:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Post not found")
    return success_response(data=post, message="Post retrieved successfully")


@router.post(
    "/",
    response_model=APIResponse[PostRead],
    status_code=status.HTTP_201_CREATED,
)
async def create_post(data: PostCreate, db: DB):
    post = await crud.create_post(db, data)
    return success_response(
        data=post,
        message="Post created successfully",
        status_code=status.HTTP_201_CREATED,
    )


@router.patch("/{post_id}", response_model=APIResponse[PostRead])
async def update_post(post_id: int, data: PostUpdate, db: DB):
    post = await crud.get_post(db, post_id)
    if not post:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Post not found")
    post = await crud.update_post(db, post, data)
    return success_response(data=post, message="Post updated successfully")


@router.delete("/{post_id}", response_model=APIResponse[None])
async def delete_post(post_id: int, db: DB):
    post = await crud.get_post(db, post_id)
    if not post:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Post not found")
    await crud.delete_post(db, post)
    return success_response(message="Post deleted successfully")


@router.delete("/{post_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_post(post_id: int, db: DB):
    post = await crud.get_post(db, post_id)
    if not post:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Post not found")
    await crud.delete_post(db, post)