# API Security & RBAC Specification

This document details all API endpoints, their authentication requirements, and the RBAC (Role-Based Access Control) permissions and ownership policies applied.

## Roles Hierarchy
- **Admin**: Full system management, user status, role assignment, and unrestricted CRUD on posts and comments.
- **Moderator**: Content moderation across the platform. Can create, edit, or delete any post and comment.
- **User**: Standard registered user. Can create posts, comments, likes, and update/delete their own posts and comments.
- **Anonymous**: Can read public posts, comments, and like counts.

---

## Endpoint Permission Matrix

| Method | Endpoint | Description | Auth Required | Required Role / Permission | Ownership Rule |
| :--- | :--- | :--- | :---: | :--- | :--- |
| **POST** | `/auth/register` | Register new user account | ❌ No | None (Default role: `user`) | N/A |
| **POST** | `/auth/login` | Login and receive access & refresh tokens | ❌ No | None | N/A |
| **POST** | `/auth/refresh` | Refresh access token with rotation | ❌ No | Valid non-revoked refresh token | N/A |
| **POST** | `/auth/logout` | Revoke current refresh token | ❌ No | Valid refresh token in body | N/A |
| **POST** | `/auth/logout-all` | Revoke all active sessions for current user | ✅ Yes | Any active authenticated user | Scoped to current user |
| **GET** | `/auth/me` | Retrieve current authenticated user profile | ✅ Yes | Any active authenticated user | Current user profile |
| **GET** | `/posts/` | List posts with pagination | ❌ No | None (Optional auth for `liked_by_me`) | Public |
| **GET** | `/posts/{post_id}` | Read single post | ❌ No | None (Optional auth for `liked_by_me`) | Public |
| **POST** | `/posts/` | Create a new post | ✅ Yes | `post:create` | Owner set to current user |
| **PATCH**| `/posts/{post_id}` | Update post content or title | ✅ Yes | `post:update:own` OR `post:update:any` | Owner if `:own`, any if `:any` |
| **DELETE**| `/posts/{post_id}`| Delete a post | ✅ Yes | `post:delete:own` OR `post:delete:any` | Owner if `:own`, any if `:any` |
| **POST** | `/posts/{post_id}/like` | Like a post (idempotent) | ✅ Yes | `like:create` | User ID attached to like |
| **DELETE**| `/posts/{post_id}/like` | Unlike a post (idempotent) | ✅ Yes | `like:create` | Scoped to current user |
| **GET** | `/posts/{post_id}/likes`| List users who liked the post | ❌ No | None | Public |
| **GET** | `/posts/{post_id}/comments` | List comments for a post | ❌ No | None (Optional auth for `liked_by_me`) | Public |
| **POST** | `/posts/{post_id}/comments` | Add comment to a post | ✅ Yes | `comment:create` | Owner set to current user |
| **PATCH**| `/comments/{comment_id}` | Update comment content | ✅ Yes | `comment:update:own` OR `comment:update:any` | Owner if `:own`, any if `:any` |
| **DELETE**| `/comments/{comment_id}` | Delete a comment | ✅ Yes | `comment:delete:own` OR `comment:delete:any` | Owner if `:own`, any if `:any` |
| **POST** | `/comments/{comment_id}/like` | Like a comment (idempotent) | ✅ Yes | `like:create` | User ID attached to like |
| **DELETE**| `/comments/{comment_id}/like` | Unlike a comment (idempotent) | ✅ Yes | `like:create` | Scoped to current user |
| **GET** | `/comments/{comment_id}/likes`| List users who liked the comment | ❌ No | None | Public |
| **GET** | `/admin/users` | List all users (paginated) | ✅ Yes | `user:manage` (Admin) | Administrative |
| **PATCH**| `/admin/users/{user_id}/role` | Assign role to a user | ✅ Yes | `role:manage` (Admin) | Administrative |
| **PATCH**| `/admin/users/{user_id}/status` | Activate / deactivate a user | ✅ Yes | `user:manage` (Admin) | Administrative |

---

## Security Defenses Implemented

1. **Authentication & Password Hashing**:
   - `argon2-cffi` with high memory & time cost.
   - Constant-time verification using dummy hash when user is not found (eliminates timing enumeration).
   - Temporary lockout after 5 consecutive failed logins for 15 minutes.
2. **JWT & Refresh Token Rotation**:
   - Short-lived access token (15 mins), long-lived refresh token (7 days).
   - Refresh tokens stored as SHA-256 hashes in `refresh_tokens`.
   - **Reuse detection**: Re-using an already revoked refresh token triggers immediate revocation of ALL active sessions for that user.
3. **IDOR & Mass Assignment**:
   - All write/delete operations verify resource ownership or elevated permission (`:any`).
   - Pydantic models configured with `extra="forbid"` to disallow injecting unexpected or privileged parameters (e.g., `role`).
4. **Injection & XSS**:
   - 100% parameterized queries via SQLAlchemy 2.0 ORM.
   - Input HTML escaping for user text (`title`, `content`).
5. **Rate Limiting & Middlewares**:
   - Slowapi rate limiting (strict 5 req/min on `/auth/login`, `/auth/register`, `/auth/refresh`).
   - Security headers: `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: strict-origin-when-cross-origin`, `Strict-Transport-Security`, `Content-Security-Policy`.
   - Request body size limiter (max 2MB) preventing memory exhaustion DoS.
   - CORS explicit origin allowlist without wildcard credentials.
