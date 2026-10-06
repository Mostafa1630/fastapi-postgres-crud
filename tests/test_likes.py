import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_post_and_comment_likes_flow(client: AsyncClient, create_user_helper):
    user1, token1 = await create_user_helper("liker1", "liker1@example.com", "user")
    user2, token2 = await create_user_helper("liker2", "liker2@example.com", "user")

    h1 = {"Authorization": f"Bearer {token1}"}
    h2 = {"Authorization": f"Bearer {token2}"}

    # Create post
    p_res = await client.post(
        "/posts/",
        headers=h1,
        json={"title": "Likeable Post", "content": "Content to like"},
    )
    post_id = p_res.json()["data"]["id"]

    # 1. User 1 likes post
    like1 = await client.post(f"/posts/{post_id}/like", headers=h1)
    assert like1.status_code == 200
    assert like1.json()["data"]["liked"] is True
    assert like1.json()["data"]["likes_count"] == 1

    # 2. User 1 likes post again (idempotent duplicate)
    like1_dup = await client.post(f"/posts/{post_id}/like", headers=h1)
    assert like1_dup.status_code == 200
    assert like1_dup.json()["data"]["likes_count"] == 1

    # 3. User 2 likes post
    like2 = await client.post(f"/posts/{post_id}/like", headers=h2)
    assert like2.status_code == 200
    assert like2.json()["data"]["likes_count"] == 2

    # 4. GET /posts/{id} with User 1 auth -> liked_by_me is True
    post_get1 = await client.get(f"/posts/{post_id}", headers=h1)
    assert post_get1.status_code == 200
    data1 = post_get1.json()["data"]
    assert data1["likes_count"] == 2
    assert data1["liked_by_me"] is True

    # 5. GET /posts/{id} unauthenticated -> liked_by_me is False
    post_get_anon = await client.get(f"/posts/{post_id}")
    assert post_get_anon.status_code == 200
    assert post_get_anon.json()["data"]["liked_by_me"] is False

    # 6. GET /posts/{id}/likes paginated
    likes_list = await client.get(f"/posts/{post_id}/likes")
    assert likes_list.status_code == 200
    assert len(likes_list.json()["data"]) == 2

    # 7. User 1 unlikes post
    unlike1 = await client.delete(f"/posts/{post_id}/like", headers=h1)
    assert unlike1.status_code == 200
    assert unlike1.json()["data"]["liked"] is False
    assert unlike1.json()["data"]["likes_count"] == 1

    # 8. User 1 unlikes post again (idempotent)
    unlike1_dup = await client.delete(f"/posts/{post_id}/like", headers=h1)
    assert unlike1_dup.status_code == 200
    assert unlike1_dup.json()["data"]["likes_count"] == 1

    # 9. Comment likes
    c_res = await client.post(
        f"/posts/{post_id}/comments",
        headers=h1,
        json={"content": "Likeable comment"},
    )
    comment_id = c_res.json()["data"]["id"]

    # Like comment
    c_like = await client.post(f"/comments/{comment_id}/like", headers=h2)
    assert c_like.status_code == 200
    assert c_like.json()["data"]["liked"] is True
    assert c_like.json()["data"]["likes_count"] == 1

    # Comment likes list
    c_likes_list = await client.get(f"/comments/{comment_id}/likes")
    assert c_likes_list.status_code == 200
    assert len(c_likes_list.json()["data"]) == 1

    # Unlike comment
    c_unlike = await client.delete(f"/comments/{comment_id}/like", headers=h2)
    assert c_unlike.status_code == 200
    assert c_unlike.json()["data"]["liked"] is False
    assert c_unlike.json()["data"]["likes_count"] == 0
