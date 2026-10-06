import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware

from app.api import admin, auth, comments, posts
from app.core.config import settings
from app.core.exceptions import register_exception_handlers
from app.core.limiter import limiter
from app.core.middleware import ContentSizeLimitMiddleware, SecurityHeadersMiddleware
from app.db.init_db import init_db
from app.db.session import SessionLocal, engine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("app")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize DB seed (roles, permissions, first admin)
    try:
        async with SessionLocal() as db:
            await init_db(db)
        logger.info("Application initialized successfully with RBAC seeds.")
    except Exception as e:
        logger.error(f"Error during database initialization: {e}")
    yield
    await engine.dispose()


app = FastAPI(
    title="Blog API with Auth & RBAC",
    description="Production-grade FastAPI application with JWT authentication, RBAC, likes, and security hardening.",
    version="1.0.0",
    docs_url="/docs" if settings.DOCS_ENABLED else None,
    redoc_url="/redoc" if settings.DOCS_ENABLED else None,
    openapi_url="/openapi.json" if settings.DOCS_ENABLED else None,
    lifespan=lifespan,
)

# Attach rate limiter to app state
app.state.limiter = limiter

# Register global exception handlers
register_exception_handlers(app)

# Security Middlewares (order matters: outermost to innermost)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(ContentSizeLimitMiddleware)

if settings.ALLOWED_HOSTS:
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=settings.ALLOWED_HOSTS,
    )

if settings.CORS_ORIGINS:
    # Ensure wildcard is not combined with credentials
    origins = settings.CORS_ORIGINS
    allow_creds = "*" not in origins
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=allow_creds,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["*"],
    )

# Routers
app.include_router(auth.router)
app.include_router(posts.router)
app.include_router(comments.router)
app.include_router(admin.router)


@app.get("/", tags=["health"])
async def root():
    return {
        "success": True,
        "message": "Blog API with Auth & RBAC is running",
        "environment": settings.ENVIRONMENT,
    }