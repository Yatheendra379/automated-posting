import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.domain import Message, parse_message


class PostingRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    message: str = Field(min_length=1, max_length=200)

    @field_validator("message")
    @classmethod
    def validate_cta(cls, value: str) -> str:
        parse_message(value)
        return value

    def to_message(self) -> Message:
        return parse_message(self.message)


class PlatformResult(BaseModel):
    platform: str
    status: Literal["success", "failed"]
    posted_url: Optional[str] = None
    public_access: bool = False
    date: Optional[datetime.date] = None
    time: Optional[datetime.time] = None
    error: Optional[str] = None


class PostingResponse(BaseModel):
    success: bool
    results: list[PlatformResult]
