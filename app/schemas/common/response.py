from typing import Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class PaginationMeta(BaseModel):
    total: int
    page: int
    limit: int
    total_pages: int
    has_next: bool
    has_prev: bool


class APIResponse(BaseModel, Generic[T]):
    success: bool = True
    status_code: int = 200
    message: str = "Success"
    data: T | None = None


class PaginatedResponse(BaseModel, Generic[T]):
    success: bool = True
    status_code: int = 200
    message: str = "Success"
    data: list[T]
    pagination: PaginationMeta