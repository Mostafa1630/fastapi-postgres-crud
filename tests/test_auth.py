import jwt
import pytest
from httpx import AsyncClient

from app.core.config import settings


@pytest.mark.asyncio
async def test_register_success(client: AsyncClient):
    response = await client.post(
        "/auth/register",
        json={
            "username": "newuser1",
            "email": "newuser1@example.com",
            "password": "Password123",
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["success"] is True
    assert data["data"]["username"] == "newuser1"
    assert data["data"]["email"] == "newuser1@example.com"
    assert "password" not in data["data"]
    assert "password_hash" not in data["data"]
    assert data["data"]["role"] == "user"


@pytest.mark.asyncio
async def test_register_password_complexity(client: AsyncClient):
    # Too short
    res1 = await client.post(
        "/auth/register",
        json={"username": "userfail1", "email": "fail1@example.com", "password": "Pass1"},
    )
    assert res1.status_code == 422

    # No uppercase
    res2 = await client.post(
        "/auth/register",
        json={"username": "userfail2", "email": "fail2@example.com", "password": "password123"},
    )
    assert res2.status_code == 422

    # No digits
    res3 = await client.post(
        "/auth/register",
        json={"username": "userfail3", "email": "fail3@example.com", "password": "PasswordOnly"},
    )
    assert res3.status_code == 422


@pytest.mark.asyncio
async def test_register_duplicate_case_insensitive(client: AsyncClient):
    await client.post(
        "/auth/register",
        json={"username": "uniqueuser", "email": "unique@example.com", "password": "Password123"},
    )

    # Duplicate username in uppercase
    dup_name = await client.post(
        "/auth/register",
        json={"username": "UNIQUEUSER", "email": "different@example.com", "password": "Password123"},
    )
    assert dup_name.status_code == 400

    # Duplicate email in uppercase
    dup_email = await client.post(
        "/auth/register",
        json={"username": "anotherone", "email": "UNIQUE@EXAMPLE.COM", "password": "Password123"},
    )
    assert dup_email.status_code == 400


@pytest.mark.asyncio
async def test_login_success(client: AsyncClient):
    await client.post(
        "/auth/register",
        json={"username": "logintest", "email": "login@example.com", "password": "Password123"},
    )

    response = await client.post(
        "/auth/login",
        json={"username": "logintest", "password": "Password123"},
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_login_wrong_password(client: AsyncClient):
    await client.post(
        "/auth/register",
        json={"username": "wrongpass", "email": "wrongpass@example.com", "password": "Password123"},
    )

    response = await client.post(
        "/auth/login",
        json={"username": "wrongpass", "password": "WrongPassword999"},
    )
    assert response.status_code == 401
    assert "Invalid credentials" in response.json()["message"]


@pytest.mark.asyncio
async def test_login_nonexistent_user(client: AsyncClient):
    response = await client.post(
        "/auth/login",
        json={"username": "does_not_exist_user", "password": "Password123"},
    )
    assert response.status_code == 401
    assert "Invalid credentials" in response.json()["message"]


@pytest.mark.asyncio
async def test_refresh_token_rotation_and_reuse_detection(client: AsyncClient):
    await client.post(
        "/auth/register",
        json={"username": "rotatetest", "email": "rotate@example.com", "password": "Password123"},
    )
    login_res = await client.post(
        "/auth/login",
        json={"username": "rotatetest", "password": "Password123"},
    )
    tokens = login_res.json()["data"]
    refresh1 = tokens["refresh_token"]

    # 1. First refresh -> should rotate
    refresh_res1 = await client.post(
        "/auth/refresh",
        json={"refresh_token": refresh1},
    )
    assert refresh_res1.status_code == 200
    new_tokens = refresh_res1.json()["data"]
    refresh2 = new_tokens["refresh_token"]
    assert refresh2 != refresh1

    # 2. Reusing refresh1 (which has been revoked) -> ATTACK DETECTION!
    reuse_res = await client.post(
        "/auth/refresh",
        json={"refresh_token": refresh1},
    )
    assert reuse_res.status_code == 401
    assert "reuse detected" in reuse_res.json()["message"].lower()

    # 3. refresh2 should also be invalidated now because of automatic family revocation!
    refresh_res2 = await client.post(
        "/auth/refresh",
        json={"refresh_token": refresh2},
    )
    assert refresh_res2.status_code == 401


@pytest.mark.asyncio
async def test_logout_and_logout_all(client: AsyncClient):
    await client.post(
        "/auth/register",
        json={"username": "logoutuser", "email": "logout@example.com", "password": "Password123"},
    )
    login_res = await client.post(
        "/auth/login",
        json={"username": "logoutuser", "password": "Password123"},
    )
    tokens = login_res.json()["data"]
    access = tokens["access_token"]
    refresh = tokens["refresh_token"]

    # Single logout
    logout_res = await client.post("/auth/logout", json={"refresh_token": refresh})
    assert logout_res.status_code == 200

    # Refresh should now fail
    ref_res = await client.post("/auth/refresh", json={"refresh_token": refresh})
    assert ref_res.status_code == 401

    # Login again
    login_res2 = await client.post(
        "/auth/login",
        json={"username": "logoutuser", "password": "Password123"},
    )
    tokens2 = login_res2.json()["data"]
    access2 = tokens2["access_token"]

    # Logout all
    logout_all_res = await client.post(
        "/auth/logout-all",
        headers={"Authorization": f"Bearer {access2}"},
    )
    assert logout_all_res.status_code == 200


@pytest.mark.asyncio
async def test_get_me(client: AsyncClient):
    await client.post(
        "/auth/register",
        json={"username": "metest", "email": "me@example.com", "password": "Password123"},
    )
    login_res = await client.post(
        "/auth/login",
        json={"username": "metest", "password": "Password123"},
    )
    access = login_res.json()["data"]["access_token"]

    me_res = await client.get("/auth/me", headers={"Authorization": f"Bearer {access}"})
    assert me_res.status_code == 200
    user_info = me_res.json()["data"]
    assert user_info["username"] == "metest"
    assert user_info["role"] == "user"
    assert "post:create" in user_info["permissions"]


@pytest.mark.asyncio
async def test_tampered_and_invalid_token(client: AsyncClient):
    # Missing auth
    res_no_auth = await client.get("/auth/me")
    assert res_no_auth.status_code == 401

    # Tampered token
    res_tampered = await client.get(
        "/auth/me",
        headers={"Authorization": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.tampered.signature"},
    )
    assert res_tampered.status_code == 401

    # Wrong token type (refresh used as access)
    refresh_jwt = jwt.encode(
        {"sub": "1", "exp": 9999999999, "iat": 1000, "jti": "abc", "type": "refresh"},
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM,
    )
    res_wrong_type = await client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {refresh_jwt}"},
    )
    assert res_wrong_type.status_code == 401
