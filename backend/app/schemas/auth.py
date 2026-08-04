from pydantic import BaseModel


class UserOut(BaseModel):
    id: str
    email: str
    is_admin: bool
