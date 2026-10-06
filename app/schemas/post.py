# Pydantic
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class PostCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=200)
    content: str = Field(min_length=1)
    author: str | None = Field(default=None, max_length=100)


class PostUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(default=None, max_length=200)
    content: str | None = None
    author: str | None = Field(default=None, max_length=100)


class PostRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    author: str
    user_id: int | None = None
    title: str
    content: str
    created_at: datetime
    updated_at: datetime
    likes_count: int = 0
    liked_by_me: bool = False