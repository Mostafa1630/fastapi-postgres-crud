from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.post import Post
from app.schemas.post import PostCreate, PostUpdate


async def get_posts(
    db: AsyncSession, page: int = 1, limit: int = 20
) -> tuple[list[Post], int]:
    total = await db.scalar(select(func.count()).select_from(Post)) or 0

    result = await db.execute(
        select(Post)
        .order_by(Post.id.desc())
        .offset((page - 1) * limit)
        .limit(limit)
    )
    return list(result.scalars().all()), total


async def get_post(db: AsyncSession, post_id: int) -> Post | None:
    return await db.get(Post, post_id)


async def create_post(db: AsyncSession, data: PostCreate) -> Post:
    post = Post(**data.model_dump())
    db.add(post)
    await db.commit()
    await db.refresh(post)
    return post


async def update_post(db: AsyncSession, post: Post, data: PostUpdate) -> Post:
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(post, field, value)
    await db.commit()
    await db.refresh(post)
    return post


async def delete_post(db: AsyncSession, post: Post) -> None:
    await db.delete(post)
    await db.commit()