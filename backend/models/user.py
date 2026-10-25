from pydantic import BaseModel, Field
from typing import Optional

class RegisterRequest(BaseModel):
    username: str = Field(min_length=3, max_length=50)
    password: str = Field(min_length=6)
    grade: int = 6
    language: str = "en"
    avatar: Optional[str] = None

class LoginRequest(BaseModel):
    username: str
    password: str

class UpdateProfileRequest(BaseModel):
    """
    Change grade and/or language after registration.

    Both are optional so the client can send just the one being changed.
    """
    grade: Optional[int] = None
    language: Optional[str] = None
    avatar: Optional[str] = None


class PublicUser(BaseModel):
    id: str
    username: str
    grade: int
    language: str
