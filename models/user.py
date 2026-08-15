from pydantic import BaseModel, EmailStr, Field
from datetime import datetime, timezone

class User(BaseModel):
    id: int | None = Field(default=None, description="The unique identifier of the user.")
    email: EmailStr = Field(..., description="The email address of the user.")
    display_name: str = Field(..., description="The display name of the user.")
    created_at: datetime | None = Field(default=None, description="The timestamp when the user was created.")

    