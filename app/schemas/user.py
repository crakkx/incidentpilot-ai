from datetime import datetime
from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserCreateRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6, max_length=200)
    role: str = Field(default="viewer", pattern="^(viewer|operator|admin)$")


class UserRoleUpdateRequest(BaseModel):
    role: str = Field(pattern="^(viewer|operator|admin)$")


class UserStatusUpdateRequest(BaseModel):
    is_active: bool


class UserReadResponse(BaseModel):
    id: str
    email: str
    role: str
    is_active: bool
    has_api_key: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
