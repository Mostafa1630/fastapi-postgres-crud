import asyncio
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import settings
from app.core.limiter import limiter
from app.core.security import create_access_token, hash_password
from app.db.base import Base
from app.db.init_db import init_db
from app.db.session import get_db
from app.main import app
from app.models.rbac import Role
from app.models.user import User

TEST_DATABASE_URL = "postgresql+asyncpg://postgres:1632003@localhost:5432/blog_test"

test_engine = create_async_engine(
    TEST_DATABASE_URL,
    poolclass=NullPool,
)
TestingSessionLocal = async_sessionmaker(test_engine, expire_on_commit=False)


@pytest_asyncio.fixture(scope="session", autouse=True)
async def setup_test_database():
    # Disable rate limiter globally during test suite to prevent 429 false positives
    limiter.enabled = False

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    async with TestingSessionLocal() as session:
        await init_db(session)

    yield

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await test_engine.dispose()


@pytest_asyncio.fixture
async def db_session():
    async with TestingSessionLocal() as session:
        yield session


@pytest_asyncio.fixture
async def client():
    async def override_get_db():
        async with TestingSessionLocal() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def create_user_helper(db_session):
    async def _create(username: str, email: str, role_name: str = "user"):
        role = await db_session.scalar(
            __import__("sqlalchemy").select(Role).where(Role.name == role_name)
        )
        user = User(
            username=username,
            email=email,
            password_hash=hash_password("Password123"),
            is_active=True,
            role_id=role.id,
        )
        db_session.add(user)
        await db_session.commit()
        await db_session.refresh(user)
        token = create_access_token(user.id)
        return user, token

    return _create
