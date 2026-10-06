from fastapi import HTTPException, status
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.core.security import sanitize_text
from app.models.comment import Comment
from app.models.like import CommentLike
from app.models.post import Post
from app.models.user import User
from app.schemas.comment import CommentCreate, CommentRead, CommentUpdate


def check_comment_ownership(comment: Comment, current_user: User, action: str) -> None:
    """Enforces ownership and permission rules for comments."""
    user_perms = {p.name for p in current_user.role.permissions}
    if f"comment:{action}:any" in user_perms:
        return
    if f"comment:{action}:own" in user_perms and comment.user_id == current_user.id:
        return
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail=f"You do not have permission to {action} this comment",
    )


def map_comment_read(
    comment: Comment, username: str, likes_count: int, liked_by_me: bool
) -> CommentRead:
    return CommentRead(
        id=comment.id,
        post_id=comment.post_id,
        user_id=comment.user_id,
        username=username,
        content=comment.content,
        created_at=comment.created_at,
        updated_at=comment.updated_at,
        likes_count=likes_count,
        liked_by_me=liked_by_me,
    )


async def get_comments(
    db: AsyncSession,
    post_id: int,
    page: int = 1,
    limit: int = 20,
    current_user_id: int | None = None,
) -> tuple[list[CommentRead], int]:
    post = await db.get(Post, post_id)
    if not post:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")

    total = await db.scalar(
        select(func.count(Comment.id)).where(Comment.post_id == post_id)
    ) or 0

    likes_subq = (
        select(CommentLike.comment_id, func.count(CommentLike.id).label("likes_count"))
        .group_by(CommentLike.comment_id)
        .subquery()
    )

    if current_user_id is not None:
        user_like_subq = (
            select(CommentLike.comment_id)
            .where(CommentLike.user_id == current_user_id)
            .subquery()
        )
        stmt = (
            select(
                Comment,
                func.coalesce(likes_subq.c.likes_count, 0).label("likes_count"),
                case((user_like_subq.c.comment_id.is_not(None), True), else_=False).label(
                    "liked_by_me"
                ),
            )
            .options(joinedload(Comment.user))
            .outerjoin(likes_subq, Comment.id == likes_subq.c.comment_id)
            .outerjoin(user_like_subq, Comment.id == user_like_subq.c.comment_id)
            .where(Comment.post_id == post_id)
            .order_by(Comment.id.asc())
            .offset((page - 1) * limit)
            .limit(limit)
        )
        result = await db.execute(stmt)
        items = [
            map_comment_read(comment, comment.user.username, likes_count, liked_by_me)
            for comment, likes_count, liked_by_me in result.all()
        ]
    else:
        stmt = (
            select(
                Comment,
                func.coalesce(likes_subq.c.likes_count, 0).label("likes_count"),
            )
            .options(joinedload(Comment.user))
            .outerjoin(likes_subq, Comment.id == likes_subq.c.comment_id)
            .where(Comment.post_id == post_id)
            .order_by(Comment.id.asc())
            .offset((page - 1) * limit)
            .limit(limit)
        )
        result = await db.execute(stmt)
        items = [
            map_comment_read(comment, comment.user.username, likes_count, False)
            for comment, likes_count in result.all()
        ]

    return items, total


async def get_comment(
    db: AsyncSession, comment_id: int, current_user_id: int | None = None
) -> CommentRead | None:
    comment = await db.scalar(
        select(Comment).options(joinedload(Comment.user)).where(Comment.id == comment_id)
    )
    if not comment:
        return None

    likes_count = await db.scalar(
        select(func.count(CommentLike.id)).where(CommentLike.comment_id == comment_id)
    ) or 0

    liked_by_me = False
    if current_user_id is not None:
        liked = await db.scalar(
            select(CommentLike.id).where(
                CommentLike.user_id == current_user_id,
                CommentLike.comment_id == comment_id,
            )
        )
        liked_by_me = bool(liked)

    return map_comment_read(comment, comment.user.username, likes_count, liked_by_me)


async def create_comment(
    db: AsyncSession, post_id: int, data: CommentCreate, current_user: User
) -> CommentRead:
    post = await db.get(Post, post_id)
    if not post:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")

    clean_content = sanitize_text(data.content)
    comment = Comment(
        post_id=post_id,
        user_id=current_user.id,
        content=clean_content,
    )
    db.add(comment)
    await db.commit()
    await db.refresh(comment)

    return map_comment_read(
        comment,
        username=current_user.username,
        likes_count=0,
        liked_by_me=False,
    )


async def update_comment(
    db: AsyncSession, comment_id: int, data: CommentUpdate, current_user: User
) -> CommentRead:
    comment = await db.scalar(
        select(Comment).options(joinedload(Comment.user)).where(Comment.id == comment_id)
    )
    if not comment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Comment not found")

    check_comment_ownership(comment, current_user, "update")

    comment.content = sanitize_text(data.content)
    await db.commit()
    await db.refresh(comment)

    updated = await get_comment(db, comment.id, current_user_id=current_user.id)
    return updated or map_comment_read(comment, current_user.username, 0, False)


async def delete_comment(db: AsyncSession, comment_id: int, current_user: User) -> None:
    comment = await db.get(Comment, comment_id)
    if not comment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Comment not found")

    check_comment_ownership(comment, current_user, "delete")

    await db.delete(comment)
    await db.commit()
