"""Application exceptions for services and API layers."""


class AppError(Exception):
    status_code: int = 500
    detail: str | dict = "Internal server error"

    def __init__(self, detail: str | dict | None = None) -> None:
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


class TooManyAttemptsError(AppError):
    status_code = 429
    detail = "Too many attempts. Please try again later."


class DailyLimitExceededError(AppError):
    status_code = 429

    def __init__(self, message: str, remaining: int = 0) -> None:
        super().__init__({"message": message, "remaining": remaining})


class VoiceTranscriptionError(AppError):
    status_code = 502
    detail = "Could not transcribe the audio. Please try again."


class VoiceSynthesisError(AppError):
    status_code = 502
    detail = "Could not generate speech. Please try again."


class AudioTooLargeError(AppError):
    status_code = 400
    detail = "Audio upload exceeds the maximum allowed size"


class UnsupportedVoiceLanguageError(AppError):
    status_code = 400
    detail = "Speech synthesis is not available for this language yet"
