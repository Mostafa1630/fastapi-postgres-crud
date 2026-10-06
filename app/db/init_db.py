import logging
from sqlalchemy import delete, insert, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import hash_password
from app.models.rbac import Permission, Role, role_permissions
from app.models.user import User

logger = logging.getLogger(__name__)

ALL_PERMISSIONS = [
    ("post:create", "Create new blog posts"),
    ("post:update:own", "Update user's own blog posts"),
    ("post:update:any", "Update any blog post"),
    ("post:delete:own", "Delete user's own blog posts"),
    ("post:delete:any", "Delete any blog post"),
    ("comment:create", "Create new comments"),
    ("comment:update:own", "Update user's own comments"),
    ("comment:delete:own", "Delete user's own comments"),
    ("comment:delete:any", "Delete any comment"),
    ("like:create", "Like and unlike posts or comments"),
    ("user:manage", "Manage users (deactivate, list, status)"),
    ("role:manage", "Assign and change roles for users"),
]

ROLE_PERMISSIONS_MAP = {
    "user": [
        "post:create",
        "post:update:own",
        "post:delete:own",
        "comment:create",
        "comment:update:own",
        "comment:delete:own",
        "like:create",
    ],
    "moderator": [
        "post:create",
        "post:update:own",
        "post:update:any",
        "post:delete:own",
        "post:delete:any",
        "comment:create",
        "comment:update:own",
        "comment:delete:own",
        "comment:delete:any",
        "like:create",
    ],
    "admin": [perm[0] for perm in ALL_PERMISSIONS],
}


async def init_db(db: AsyncSession) -> None:
    # 1. Seed Permissions
    permissions_by_name: dict[str, Permission] = {}
    for perm_name, description in ALL_PERMISSIONS:
        result = await db.execute(select(Permission).where(Permission.name == perm_name))
        perm = result.scalar_one_or_none()
        if not perm:
            perm = Permission(name=perm_name, description=description)
            db.add(perm)
            await db.flush()
        permissions_by_name[perm_name] = perm

    # 2. Seed Roles
    roles_by_name: dict[str, Role] = {}
    for role_name in ROLE_PERMISSIONS_MAP.keys():
        result = await db.execute(select(Role).where(Role.name == role_name))
        role = result.scalar_one_or_none()
        if not role:
            role = Role(name=role_name, description=f"{role_name.capitalize()} role")
            db.add(role)
            await db.flush()
        roles_by_name[role_name] = role

    await db.flush()

    # 3. Seed Role Permissions directly in junction table
    for role_name, perm_names in ROLE_PERMISSIONS_MAP.items():
        role = roles_by_name[role_name]
        # Clear existing role permissions
        await db.execute(delete(role_permissions).where(role_permissions.c.role_id == role.id))
        for p_name in perm_names:
            perm = permissions_by_name[p_name]
            await db.execute(
                insert(role_permissions).values(role_id=role.id, permission_id=perm.id)
            )

    await db.flush()

    # 4. Seed First Admin if not exists
    admin_result = await db.execute(
        select(User).where(User.username == settings.FIRST_ADMIN_USERNAME)
    )
    admin_user = admin_result.scalar_one_or_none()
    if not admin_user:
        admin_role = roles_by_name["admin"]
        admin_user = User(
            username=settings.FIRST_ADMIN_USERNAME,
            email=settings.FIRST_ADMIN_EMAIL,
            password_hash=hash_password(settings.FIRST_ADMIN_PASSWORD),
            is_active=True,
            role_id=admin_role.id,
        )
        db.add(admin_user)
        logger.info(f"Created first admin user '{settings.FIRST_ADMIN_USERNAME}'")

    await db.commit()
