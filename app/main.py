from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api import posts
from app.db.session import engine


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await engine.dispose()


app = FastAPI(title="Blog API", lifespan=lifespan)
app.include_router(posts.router)


@app.get("/")
async def root():
    return {"message": "Hello, World!"}