from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class Note(BaseModel):
    id: str
    title: str
    body: str
    created_at: datetime
    updated_at: Optional[datetime] = None


class CreateNoteRequest(BaseModel):
    title: str
    body: str


class UpdateNoteRequest(BaseModel):
    title: Optional[str] = None
    body: Optional[str] = None


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "Bearer"
    expires_in: int
    scope: str
