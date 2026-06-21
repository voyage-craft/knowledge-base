from pydantic import BaseModel, ConfigDict, constr, field_validator
from typing import Optional
from datetime import datetime


class AdminUserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    email: str
    is_active: bool
    is_admin: bool
    created_at: datetime
    updated_at: datetime


class AdminCreateUserRequest(BaseModel):
    username: constr(min_length=1, max_length=100)
    email: constr(min_length=3, max_length=255)
    password: constr(min_length=6, max_length=128)
    is_admin: bool = False


class AdminUpdateUserRequest(BaseModel):
    is_active: Optional[bool] = None
    is_admin: Optional[bool] = None
    email: Optional[constr(min_length=3, max_length=255)] = None


class AdminResetPasswordRequest(BaseModel):
    new_password: constr(min_length=6, max_length=128)
