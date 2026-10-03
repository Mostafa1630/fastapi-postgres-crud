import math
from typing import Any

from app.schemas.common.response import APIResponse, PaginatedResponse, PaginationMeta


def success_response(
    data: Any = None,
    message: str = "Success",
    status_code: int = 200,
) -> APIResponse:
    return APIResponse(
        success=True,
        status_code=status_code,
        message=message,
        data=data,
    )


def paginated_response(
    items: list,
    total: int,
    page: int,
    limit: int,
    message: str = "Success",
    status_code: int = 200,
) -> PaginatedResponse:
    total_pages = math.ceil(total / limit) if total else 0
    return PaginatedResponse(
        success=True,
        status_code=status_code,
        message=message,
        data=items,
        pagination=PaginationMeta(
            total=total,
            page=page,
            limit=limit,
            total_pages=total_pages,
            has_next=page < total_pages,
            has_prev=page > 1,
        ),
    )