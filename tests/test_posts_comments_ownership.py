import pytest
from httpx import AsyncClient

from app.core.config import settings


@pytest.mark.asyncio
async def test_posts_and_comments_ownership_rules(client: AsyncClient, create_user_helper):
    # Setup users
    user1, token1 = await create_user_helper("author1", "author1@example.com", "user")
    user2, token2 = await create_user_helper("author2", "author2@example.com", "user")
    mod, token_mod = await create_user_helper("moderator1", "mod1@example.com", "moderator")

    h1 = {"Authorization": f"Bearer {token1}"}
    h2 = {"Authorization": f"Bearer {token2}"}
    h_mod = {"Authorization": f"Bearer {token_mod}"}

    # 1. User 1 creates a post
    post_res = await client.post(
        "/posts/",
        headers=h1,
        json={"title": "Original Post", "content": "Content written by Author 1"},
    )
    assert post_res.status_code == 201
    post_id = post_res.json()["data"]["id"]

    # 2. User 1 updates their own post (allowed)
    update_res1 = await client.patch(
        f"/posts/{post_id}",
        headers=h1,
        json={"title": "Updated by Owner"},
    )
    assert update_res1.status_code == 200
    assert update_res1.json()["data"]["title"] == "Updated by Owner"

    # 3. User 2 attempts to update User 1's post -> 403 Forbidden (IDOR prevention)
    update_res2 = await client.patch(
        f"/posts/{post_id}",
        headers=h2,
        json={"title": "Hacked Title"},
    )
    assert update_res2.status_code == 403

    # 4. User 2 attempts to delete User 1's post -> 403 Forbidden
    del_res2 = await client.delete(f"/posts/{post_id}", headers=h2)
    assert del_res2.status_code == 403

    # 5. User 1 creates a comment
    com_res = await client.post(
        f"/posts/{post_id}/comments",
        headers=h1,
        json={"content": "My first comment"},
    )
    assert com_res.status_code == 201
    com_id = com_res.json()["data"]["id"]

    # 6. User 2 attempts to update User 1's comment -> 403 Forbidden
    com_up2 = await client.patch(
        f"/comments/{com_id}",
        headers=h2,
        json={"content": "Tampered comment"},
    )
    assert com_up2.status_code == 403

    # 7. User 2 attempts to delete User 1's comment -> 403 Forbidden
    com_del2 = await client.delete(f"/comments/{com_id}", headers=h2)
    assert com_del2.status_code == 403

    # 8. Moderator deletes User 1's comment (allowed by comment:delete:any)
    mod_com_del = await client.delete(f"/comments/{com_id}", headers=h_mod)
    assert mod_com_del.status_code == 200

    # 9. Moderator updates or deletes User 1's post (allowed by post:delete:any)
    mod_post_del = await client.delete(f"/posts/{post_id}", headers=h_mod)
    assert mod_post_del.status_code == 200
