import asyncio
from app.db.init_db import init_db
from app.db.session import SessionLocal, engine


async def main() -> None:
    print("Starting database seed...")
    async with SessionLocal() as db:
        await init_db(db)
    await engine.dispose()
    print("Database seeding completed successfully.")


if __name__ == "__main__":
    asyncio.run(main())
