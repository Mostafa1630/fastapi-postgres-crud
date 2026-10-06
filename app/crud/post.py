from fastapi import HTTPException, status
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import sanitize_text
from app.models.like import PostLike
from app.models.post import Post
from app.models.user import User
from app.schemas.post import PostCreate, PostRead, PostUpdate


def check_post_ownership(post: Post, current_user: User, action: str) -> None:
    """Enforces ownership and permission rules in service/crud layer."""
    user_perms = {p.name for p in current_user.role.permissions}
    if f"post:{action}:any" in user_perms:
        return
    if f"post:{action}:own" in user_perms and post.user_id == current_user.id:
        return
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail=f"You do not have permission to {action} this post",
    )


def map_post_read(post: Post, likes_count: int, liked_by_me: bool) -> PostRead:
    return PostRead(
        id=post.id,
        author=post.author,
        user_id=post.user_id,
        title=post.title,
        content=post.content,
        created_at=post.created_at,
        updated_at=post.updated_at,
        likes_count=likes_count,
        liked_by_me=liked_by_me,
    )


async def get_posts(
    db: AsyncSession,
    page: int = 1,
    limit: int = 20,
    current_user_id: int | None = None,
) -> tuple[list[PostRead], int]:
    total = await db.scalar(select(func.count()).select_from(Post)) or 0

    likes_subq = (
        select(PostLike.post_id, func.count(PostLike.id).label("likes_count"))
        .group_by(PostLike.post_id)
        .subquery()
    )

    if current_user_id is not None:
        user_like_subq = (
            select(PostLike.post_id)
            .where(PostLike.user_id == current_user_id)
            .subquery()
        )
        stmt = (
            select(
                Post,
                func.coalesce(likes_subq.c.likes_count, 0).label("likes_count"),
                case((user_like_subq.c.post_id.is_not(None), True), else_=False).label(
                    "liked_by_me"
                ),
            )
            .outerjoin(likes_subq, Post.id == likes_subq.c.post_id)
            .outerjoin(user_like_subq, Post.id == user_like_subq.c.post_id)
            .order_by(Post.id.desc())
            .offset((page - 1) * limit)
            .limit(limit)
        )
        result = await db.execute(stmt)
        items = [
            map_post_read(post, likes_count, liked_by_me)
            for post, likes_count, liked_by_me in result.all()
        ]
    else:
        stmt = (
            select(
                Post,
                func.coalesce(likes_subq.c.likes_count, 0).label("likes_count"),
            )
            .outerjoin(likes_subq, Post.id == likes_subq.c.post_id)
            .order_by(Post.id.desc())
            .offset((page - 1) * limit)
            .limit(limit)
        )
        result = await db.execute(stmt)
        items = [
            map_post_read(post, likes_count, False)
            for post, likes_count in result.all()
        ]

    return items, total


async def get_post(
    db: AsyncSession, post_id: int, current_user_id: int | None = None
) -> PostRead | None:
    likes_subq = (
        select(PostLike.post_id, func.count(PostLike.id).label("likes_count"))
        .where(PostLike.post_id == post_id)
        .group_by(PostLike.post_id)
        .subquery()
    )

    if current_user_id is not None:
        user_like_subq = (
            select(PostLike.post_id)
            .where(PostLike.user_id == current_user_id, PostLike.post_id == post_id)
            .subquery()
        )
        stmt = (
            select(
                Post,
                func.coalesce(likes_subq.c.likes_count, 0).label("likes_count"),
                case((user_like_subq.c.post_id.is_not(None), True), else_=False).label(
                    "liked_by_me"
                ),
            )
            .outerjoin(likes_subq, Post.id == likes_subq.c.post_id)
            .outerjoin(user_like_subq, Post.id == user_like_subq.c.post_id)
            .where(Post.id == post_id)
        )
        result = await db.execute(stmt)
        row = result.first()
        if not row:
            return None
        post, likes_count, liked_by_me = row
        return map_post_read(post, likes_count, liked_by_me)
    else:
        stmt = (
            select(
                Post,
                func.coalesce(likes_subq.c.likes_count, 0).label("likes_count"),
            )
            .outerjoin(likes_subq, Post.id == likes_subq.c.post_id)
            .where(Post.id == post_id)
        )
        result = await db.execute(stmt)
        row = result.first()
        if not row:
            return None
        post, likes_count = row
        return map_post_read(post, likes_count, False)


async def get_post_entity(db: AsyncSession, post_id: int) -> Post | None:
    return await db.get(Post, post_id)


async def create_post(db: AsyncSession, data: PostCreate, current_user: User) -> PostRead:
    # Sanitize content and title against XSS
    clean_title = sanitize_text(data.title)
    clean_content = sanitize_text(data.content)
    author_name = sanitize_text(data.author) if data.author else current_user.username

    post = Post(
        title=clean_title,
        content=clean_content,
        author=author_name,
        user_id=current_user.id,
    )
    db.add(post)
    await db.commit()
    await db.refresh(post)
    return map_post_read(post, likes_count=0, liked_by_me=False)


async def update_post(
    db: AsyncSession, post_id: int, data: PostUpdate, current_user: User
) -> PostRead:
    post = await get_post_entity(db, post_id)
    if not post:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")

    # IDOR and permission check
    check_post_ownership(post, current_user, "update")

    update_dict = data.model_dump(exclude_unset=True)
    if "title" in update_dict and update_dict["title"] is not None:
        post.title = sanitize_text(update_dict["title"])
    if "content" in update_dict and update_dict["content"] is not None:
        post.content = sanitize_text(update_dict["content"])
    if "author" in update_dict and update_dict["author"] is not None:
        post.author = sanitize_text(update_dict["author"])

    await db.commit()
    await db.refresh(post)

    # Return updated post with like count
    updated = await get_post(db, post.id, current_user_id=current_user.id)
    return updated or map_post_read(post, 0, False)


async def delete_post(db: AsyncSession, post_id: int, current_user: User) -> None:
    post = await get_post_entity(db, post_id)
    if not post:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")

    # IDOR and permission check
    check_post_ownership(post, current_user, "delete")

    await db.delete(post)
    await db.commit()