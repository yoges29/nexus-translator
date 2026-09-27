from typing import Any

from fastapi import HTTPException, status


class AppError(Exception):
    def __init__(self, message: str, status_code: int = status.HTTP_400_BAD_REQUEST) -> None:
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class ProviderError(AppError):
    def __init__(self, message: str = "Translation service is temporarily unavailable. Please try again.") -> None:
        super().__init__(message, status_code=status.HTTP_503_SERVICE_UNAVAILABLE)


def error_payload(message: str, code: str | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {"detail": message}
    if code:
        payload["code"] = code
    return payload


def raise_http_error(exc: AppError) -> None:
    raise HTTPException(status_code=exc.status_code, detail=exc.message)
