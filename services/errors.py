"""Application exceptions for services and API layers."""


class AppError(Exception):
    status_code: int = 500
    detail: str = "Internal server error"

    def __init__(self, detail: str | None = None) -> None:
        if detail is not None:
            self.detail = detail
        super().__init__(self.detail)


class LessonNotFoundError(AppError):
    status_code = 404
    detail = "Lesson not found"


class SessionNotFoundError(AppError):
    status_code = 404
    detail = "Session not found"


class EmptySessionError(AppError):
    status_code = 400
    detail = "No messages to save"


class LLMError(AppError):
    status_code = 502
    detail = "The AI tutor is temporarily unavailable. Please try again."


class LLMTimeoutError(LLMError):
    detail = "The AI tutor took too long to respond. Please try again."


class LLMRateLimitError(LLMError):
    detail = "Too many requests. Please wait a moment and try again."


class PasswordTooLongError(AppError):
    status_code = 400
    detail = "Password must be 72 bytes or fewer"


class DuplicateEmailError(AppError):
    status_code = 409
    detail = "A user with this email already exists"

class InvalidCredentialsError(AppError):
    status_code = 401
    detail = "Invalid email or password" 