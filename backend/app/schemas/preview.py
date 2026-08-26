from pydantic import BaseModel


class PreviewTokenResponse(BaseModel):
    preview_token: str
    expires_in: int
