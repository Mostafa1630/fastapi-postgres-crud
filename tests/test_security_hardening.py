import pytest
from httpx import AsyncClient

from app.core.limiter import limiter


@pytest.mark.asyncio
async def test_security_headers_present(client: AsyncClient):
    response = await client.get("/")
    assert response.status_code == 200
    headers = response.headers

    assert headers.get("x-content-type-options") == "nosniff"
    assert headers.get("x-frame-options") == "DENY"
    assert headers.get("referrer-policy") == "strict-origin-when-cross-origin"
    assert headers.get("content-security-policy") == "default-src 'self'"


@pytest.mark.asyncio
async def test_mass_assignment_extra_fields_forbidden(client: AsyncClient):
    # Attempt to inject arbitrary fields like 'role' or 'is_admin'
    response = await client.post(
        "/auth/register",
        json={
            "username": "hacker1",
            "email": "hacker1@example.com",
            "password": "Password123",
            "role": "admin",
            "is_admin": True,
        },
    )
    assert response.status_code == 422
    assert "extra" in response.text.lower()


@pytest.mark.asyncio
async def test_payload_size_limit(client: AsyncClient):
    # Send headers with oversized Content-Length
    huge_length = str(3 * 1024 * 1024)  # 3MB > 2MB limit
    response = await client.post(
        "/auth/login",
        headers={"Content-Length": huge_length},
        content=b"{}",
    )
    assert response.status_code == 413
    assert "too large" in response.json()["message"].lower()


@pytest.mark.asyncio
async def test_xss_sanitization(client: AsyncClient, create_user_helper):
    user, token = await create_user_helper("xssuser", "xss@example.com", "user")
    headers = {"Authorization": f"Bearer {token}"}

    xss_payload = "<script>alert('xss')</script>Hello & welcome"
    res = await client.post(
        "/posts/",
        headers=headers,
        json={"title": xss_payload, "content": "Safe content"},
    )
    assert res.status_code == 201
    created_post = res.json()["data"]
    # Verify that <script> is escaped to &lt;script&gt;
    assert "<script>" not in created_post["title"]
    assert "&lt;script&gt;" in created_post["title"]


@pytest.mark.asyncio
async def test_account_temporary_lockout_after_failed_attempts(client: AsyncClient):
    await client.post(
        "/auth/register",
        json={"username": "lockoutuser", "email": "lockout@example.com", "password": "Password123"},
    )

    # Fail login 5 times
    for _ in range(5):
        fail_res = await client.post(
            "/auth/login",
            json={"username": "lockoutuser", "password": "WrongPassword1"},
        )
        assert fail_res.status_code == 401

    # 6th attempt should be blocked with 429 lockout
    locked_res = await client.post(
        "/auth/login",
        json={"username": "lockoutuser", "password": "WrongPassword1"},
    )
    assert locked_res.status_code == 429
    assert "locked" in locked_res.json()["message"].lower()


@pytest.mark.asyncio
async def test_slowapi_rate_limiting(client: AsyncClient):
    # Explicitly enable limiter for this specific test
    limiter.enabled = True
    try:
        # Endpoint /auth/login has 5/minute limit
        responses = []
        for i in range(7):
            res = await client.post(
                "/auth/login",
                json={"username": f"ratetest{i}", "password": "Password123"},
            )
            responses.append(res.status_code)

        # At least one of the requests should hit 429
        assert 429 in responses
    finally:
        limiter.enabled = False
