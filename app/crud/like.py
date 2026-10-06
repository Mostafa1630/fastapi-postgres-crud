from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.models.comment import Comment
from app.models.like import CommentLike, PostLike
from app.models.post import Post
from app.models.user import User
from app.schemas.like import LikeUserRead


async def like_post(db: AsyncSession, user_id: int, post_id: int) -> tuple[bool, int]:
    post = await db.get(Post, post_id)
    if not post:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Post not found",
        )

    # Check existing like (idempotency)
    existing = await db.scalar(
        select(PostLike).where(PostLike.user_id == user_id, PostLike.post_id == post_id)
    )
    if not existing:
        like = PostLike(user_id=user_id, post_id=post_id)
        db.add(like)
        try:
            await db.commit()
        except IntegrityError:
            await db.rollback()

    count = await db.scalar(
        select(func.count(PostLike.id)).where(PostLike.post_id == post_id)
    ) or 0
    return True, count


async def unlike_post(db: AsyncSession, user_id: int, post_id: int) -> tuple[bool, int]:
    post = await db.get(Post, post_id)
    if not post:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Post not found",
        )

    existing = await db.scalar(
        select(PostLike).where(PostLike.user_id == user_id, PostLike.post_id == post_id)
    )
    if existing:
        await db.delete(existing)
        await db.commit()

    count = await db.scalar(
        select(func.count(PostLike.id)).where(PostLike.post_id == post_id)
    ) or 0
    return False, count


async def get_post_likes(
    db: AsyncSession, post_id: int, page: int = 1, limit: int = 20
) -> tuple[list[LikeUserRead], int]:
    post = await db.get(Post, post_id)
    if not post:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Post not found",
        )

    total = await db.scalar(
        select(func.count(PostLike.id)).where(PostLike.post_id == post_id)
    ) or 0

    result = await db.execute(
        select(PostLike)
        .options(joinedload(PostLike.user))
        .where(PostLike.post_id == post_id)
        .order_by(PostLike.created_at.desc())
        .offset((page - 1) * limit)
        .limit(limit)
    )
    likes = result.scalars().all()
    items = [
        LikeUserRead(
            user_id=like.user.id,
            username=like.user.username,
            created_at=like.created_at,
        )
        for like in likes
    ]
    return items, total


async def like_comment(db: AsyncSession, user_id: int, comment_id: int) -> tuple[bool, int]:
    comment = await db.get(Comment, comment_id)
    if not comment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Comment not found",
        )

    existing = await db.scalar(
        select(CommentLike).where(
            CommentLike.user_id == user_id, CommentLike.comment_id == comment_id
        )
    )
    if not existing:
        like = CommentLike(user_id=user_id, comment_id=comment_id)
        db.add(like)
        try:
            await db.commit()
        except IntegrityError:
            await db.rollback()

    count = await db.scalar(
        select(func.count(CommentLike.id)).where(CommentLike.comment_id == comment_id)
    ) or 0
    return True, count


async def unlike_comment(db: AsyncSession, user_id: int, comment_id: int) -> tuple[bool, int]:
    comment = await db.get(Comment, comment_id)
    if not comment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Comment not found",
        )

    existing = await db.scalar(
        select(CommentLike).where(
            CommentLike.user_id == user_id, CommentLike.comment_id == comment_id
        )
    )
    if existing:
        await db.delete(existing)
        await db.commit()

    count = await db.scalar(
        select(func.count(CommentLike.id)).where(CommentLike.comment_id == comment_id)
    ) or 0
    return False, count


async def get_comment_likes(
    db: AsyncSession, comment_id: int, page: int = 1, limit: int = 20
) -> tuple[list[LikeUserRead], int]:
    comment = await db.get(Comment, comment_id)
    if not comment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Comment not found",
        )

    total = await db.scalar(
        select(func.count(CommentLike.id)).where(CommentLike.comment_id == comment_id)
    ) or 0

    result = await db.execute(
        select(CommentLike)
        .options(joinedload(CommentLike.user))
        .where(CommentLike.comment_id == comment_id)
        .order_by(CommentLike.created_at.desc())
        .offset((page - 1) * limit)
        .limit(limit)
    )
    likes = result.scalars().all()
    items = [
        LikeUserRead(
            user_id=like.user.id,
            username=like.user.username,
            created_at=like.created_at,
        )
        for like in likes
    ]
    return items, total
