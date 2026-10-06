from datetime import datetime, timedelta, timezone
from sqlalchemy import delete, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload
from fastapi import HTTPException, status

from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    hash_token,
    verify_password_constant_time,
)
from app.models.rbac import Role
from app.models.user import RefreshToken, User
from app.schemas.auth import TokenResponse, UserLogin, UserRegister


async def register_user(db: AsyncSession, data: UserRegister) -> User:
    # Reject duplicate email or username (case-insensitive)
    existing_user = await db.scalar(
        select(User).where(
            or_(
                func.lower(User.username) == data.username.lower(),
                func.lower(User.email) == data.email.lower(),
            )
        )
    )
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username or email already registered",
        )

    # Assign default role 'user'
    user_role = await db.scalar(select(Role).where(Role.name == "user"))
    if not user_role:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Default role 'user' is not configured",
        )

    new_user = User(
        username=data.username,
        email=data.email,
        password_hash=hash_password(data.password),
        is_active=True,
        role_id=user_role.id,
    )
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)

    # Reload with role and permissions
    result = await db.execute(
        select(User)
        .where(User.id == new_user.id)
        .options(joinedload(User.role).selectinload(Role.permissions))
    )
    return result.scalar_one()


async def login_user(db: AsyncSession, data: UserLogin) -> TokenResponse:
    # Generic error message to prevent user enumeration
    generic_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    # Query user case-insensitively by username or email
    result = await db.execute(
        select(User)
        .where(
            or_(
                func.lower(User.username) == data.username.lower(),
                func.lower(User.email) == data.username.lower(),
            )
        )
        .options(joinedload(User.role))
    )
    user = result.scalar_one_or_none()

    # Check lockout
    now_utc = datetime.now(timezone.utc)
    if user and user.locked_until:
        if user.locked_until > now_utc:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Account temporarily locked due to multiple failed login attempts. Please try again later.",
            )
        else:
            # Lockout expired, reset
            user.locked_until = None
            user.failed_login_attempts = 0
            await db.commit()

    # Constant-time password check with dummy hashing when user does not exist
    is_valid = verify_password_constant_time(
        data.password, user.password_hash if user else None
    )

    if not user or not is_valid:
        if user:
            user.failed_login_attempts += 1
            if user.failed_login_attempts >= 5:
                user.locked_until = now_utc + timedelta(minutes=15)
            await db.commit()
        raise generic_error

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Inactive user account",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Reset failed attempts
    user.failed_login_attempts = 0
    user.locked_until = None

    # Issue access and refresh tokens
    access_token = create_access_token(user.id)
    refresh_token, jti, expires_at = create_refresh_token(user.id)

    db_token = RefreshToken(
        jti=jti,
        user_id=user.id,
        token_hash=hash_token(refresh_token),
        expires_at=expires_at,
    )
    db.add(db_token)
    await db.commit()

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
    )


async def rotate_refresh_token(db: AsyncSession, raw_refresh_token: str) -> TokenResponse:
    payload = decode_token(raw_refresh_token, expected_type="refresh")
    user_id_str = payload.get("sub")
    jti = payload.get("jti")
    if not user_id_str or not jti:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token claims",
        )

    user_id = int(user_id_str)
    token_h = hash_token(raw_refresh_token)

    result = await db.execute(
        select(RefreshToken).where(
            RefreshToken.jti == jti,
            RefreshToken.user_id == user_id,
        )
    )
    db_token = result.scalar_one_or_none()

    if not db_token or db_token.token_hash != token_h:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
        )

    now_utc = datetime.now(timezone.utc)

    # REUSE DETECTION: if token was already revoked, someone is replaying a stolen/old token!
    if db_token.revoked_at is not None:
        # Revoke ALL tokens for this compromised user
        await db.execute(
            update(RefreshToken)
            .where(
                RefreshToken.user_id == user_id,
                RefreshToken.revoked_at.is_(None),
            )
            .values(revoked_at=now_utc)
        )
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Revoked refresh token reuse detected. All active sessions have been invalidated.",
        )

    if db_token.expires_at < now_utc:
        db_token.revoked_at = now_utc
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token expired",
        )

    # Revoke current token (rotation)
    db_token.revoked_at = now_utc

    # Create new pair
    new_access_token = create_access_token(user_id)
    new_refresh_token, new_jti, new_expires_at = create_refresh_token(user_id)

    new_db_token = RefreshToken(
        jti=new_jti,
        user_id=user_id,
        token_hash=hash_token(new_refresh_token),
        expires_at=new_expires_at,
    )
    db.add(new_db_token)
    await db.commit()

    return TokenResponse(
        access_token=new_access_token,
        refresh_token=new_refresh_token,
    )


async def revoke_refresh_token(db: AsyncSession, raw_refresh_token: str) -> None:
    try:
        payload = decode_token(raw_refresh_token, expected_type="refresh")
        jti = payload.get("jti")
        token_h = hash_token(raw_refresh_token)
        if jti:
            await db.execute(
                update(RefreshToken)
                .where(
                    RefreshToken.jti == jti,
                    RefreshToken.token_hash == token_h,
                    RefreshToken.revoked_at.is_(None),
                )
                .values(revoked_at=datetime.now(timezone.utc))
            )
            await db.commit()
    except Exception:  # nosec B110
        # Idempotent logout: even if token is invalid/expired, don't fail
        pass


async def revoke_all_user_tokens(db: AsyncSession, user_id: int) -> None:
    await db.execute(
        update(RefreshToken)
        .where(
            RefreshToken.user_id == user_id,
            RefreshToken.revoked_at.is_(None),
        )
        .values(revoked_at=datetime.now(timezone.utc))
    )
    await db.commit()
