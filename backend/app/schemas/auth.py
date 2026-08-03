from pydantic import BaseModel


class GoogleLoginRequest(BaseModel):
    id_token: str


class UserOut(BaseModel):
    id: str
    email: str
    is_admin: bool


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut
