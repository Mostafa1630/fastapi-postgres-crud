import pytest
from httpx import AsyncClient

from app.core.config import settings


@pytest.mark.asyncio
async def test_admin_rbac_and_role_management(client: AsyncClient, create_user_helper):
    # Log in as admin
    admin_login = await client.post(
        "/auth/login",
        json={
            "username": settings.FIRST_ADMIN_USERNAME,
            "password": settings.FIRST_ADMIN_PASSWORD,
        },
    )
    assert admin_login.status_code == 200
    admin_token = admin_login.json()["data"]["access_token"]
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    # Regular user
    _, user_token = await create_user_helper("normaluser", "normal@example.com", "user")
    user_headers = {"Authorization": f"Bearer {user_token}"}

    # 1. Regular user forbidden from admin users list (403)
    res_forbidden = await client.get("/admin/users", headers=user_headers)
    assert res_forbidden.status_code == 403

    # 2. Admin can list users
    res_admin = await client.get("/admin/users", headers=admin_headers)
    assert res_admin.status_code == 200
    data = res_admin.json()["data"]
    assert len(data) >= 1

    # Find the normaluser id
    target_user = next((u for u in data if u["username"] == "normaluser"), None)
    assert target_user is not None
    user_id = target_user["id"]

    # 3. Regular user forbidden from changing roles
    res_change_fail = await client.patch(
        f"/admin/users/{user_id}/role",
        headers=user_headers,
        json={"role_name": "moderator"},
    )
    assert res_change_fail.status_code == 403

    # 4. Admin changes user role to moderator
    res_role_update = await client.patch(
        f"/admin/users/{user_id}/role",
        headers=admin_headers,
        json={"role_name": "moderator"},
    )
    assert res_role_update.status_code == 200
    assert res_role_update.json()["data"]["role"] == "moderator"

    # 5. Admin deactivates user
    res_deact = await client.patch(
        f"/admin/users/{user_id}/status",
        headers=admin_headers,
        json={"is_active": False},
    )
    assert res_deact.status_code == 200
    assert res_deact.json()["data"]["is_active"] is False

    # 6. Deactivated user cannot access protected endpoints
    res_deact_access = await client.get("/auth/me", headers=user_headers)
    assert res_deact_access.status_code == 401
    assert "inactive" in res_deact_access.json()["message"].lower()
