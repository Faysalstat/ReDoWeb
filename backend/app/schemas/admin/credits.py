from pydantic import BaseModel, Field, field_validator


class AdminIssueAdjustmentRequest(BaseModel):
    amount: int
    note: str = Field(min_length=1)
    related_project_id: str | None = None

    @field_validator("amount")
    @classmethod
    def amount_must_be_nonzero(cls, value: int) -> int:
        if value == 0:
            raise ValueError("amount must be nonzero")
        return value

    @field_validator("note")
    @classmethod
    def note_must_not_be_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("note must not be blank")
        return value


class AdminAdjustmentResponse(BaseModel):
    wallet_balance: int
    transaction_id: str
    purchase_id: str
