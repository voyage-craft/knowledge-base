from pydantic import BaseModel, constr

class LoginRequest(BaseModel):
    username: constr(min_length=1, max_length=100)
    password: constr(min_length=6, max_length=128)

class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int

class RefreshRequest(BaseModel):
    refresh_token: str

class UserResponse(BaseModel):
    id: int
    username: str
    email: str
    is_admin: bool
