from datetime import datetime
from pydantic import BaseModel, ConfigDict


class LikeUserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: int
    username: str
    created_at: datetime


class LikeToggleResponse(BaseModel):
    liked: bool
    likes_count: int
    message: str
