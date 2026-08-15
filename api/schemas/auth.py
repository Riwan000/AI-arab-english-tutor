from pydantic import BaseModel, EmailStr, Field, field_validator

from models.user import User

# bcrypt silently truncates past 72 bytes, so cap length here for a clean 422
# instead of relying on hash_password's PasswordTooLongError (which still fires
# for multi-byte passwords under 72 characters but over 72 bytes).
MIN_PASSWORD_LENGTH = 8
MAX_PASSWORD_LENGTH = 72
MAX_DISPLAY_NAME_LENGTH = 100


class SignupRequest(BaseModel):
    email: EmailStr = Field(..., description="The email address of the user.")
    password: str = Field(
        ...,
        min_length=MIN_PASSWORD_LENGTH,
        max_length=MAX_PASSWORD_LENGTH,
        description="The password for the user account.",
    )
    display_name: str = Field(
        ...,
        min_length=1,
        max_length=MAX_DISPLAY_NAME_LENGTH,
        description="The display name of the user.",
    )

    @field_validator("display_name")
    @classmethod
    def strip_display_name(cls, value: str) -> str:
        """Trim surrounding whitespace and reject whitespace-only names."""
        stripped = value.strip()
        if not stripped:
            raise ValueError("display_name must not be blank")
        return stripped

class LoginRequest(BaseModel):
    email: EmailStr = Field(..., description="The email address of the user.")
    password: str = Field(..., description="The password for the user account.")

class TokenResponse(BaseModel):
    access_token: str = Field(..., description="The JWT access token for authenticated requests.")
    token_type: str = Field(default="bearer", description="The type of the token, typically 'bearer'.")
    user: User