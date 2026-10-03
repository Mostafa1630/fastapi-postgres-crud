# Pydantic 
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class PostCreate(BaseModel):
    author: str = Field(min_length=1, max_length=100)
    title: str = Field(min_length=1, max_length=200)
    content: str = Field(min_length=1)


class PostUpdate(BaseModel):
    author: str | None = Field(default=None, max_length=100)
    title: str | None = Field(default=None, max_length=200)
    content: str | None = None


class PostRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    author: str
    title: str
    content: str
    created_at: datetime
    updated_at: datetime