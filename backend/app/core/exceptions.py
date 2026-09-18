"""
Custom exception classes and error handling.
"""

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional, Any


class AppError(Exception):
    """Base application error."""

    def __init__(
        self,
        message: str,
        code: str = "INTERNAL_ERROR",
        status_code: int = 500,
        details: Optional[dict] = None,
    ):
        self.message = message
        self.code = code
        self.status_code = status_code
        self.details = details or {}
        super().__init__(self.message)


class NotFoundError(AppError):
    """Resource not found."""

    def __init__(self, resource: str, resource_id: str):
        super().__init__(
            message=f"{resource} not found: {resource_id}",
            code="NOT_FOUND",
            status_code=404,
            details={"resource": resource, "resource_id": resource_id},
        )


class ValidationError(AppError):
    """Validation error."""

    def __init__(self, message: str, details: Optional[dict] = None):
        super().__init__(
            message=message,
            code="VALIDATION_ERROR",
            status_code=422,
            details=details or {},
        )


class UnauthorizedError(AppError):
    """Unauthorized access."""

    def __init__(self, message: str = "Unauthorized"):
        super().__init__(
            message=message,
            code="UNAUTHORIZED",
            status_code=401,
        )


class ForbiddenError(AppError):
    """Forbidden action."""

    def __init__(self, message: str = "Forbidden"):
        super().__init__(
            message=message,
            code="FORBIDDEN",
            status_code=403,
        )


class WorkflowError(AppError):
    """Workflow-specific error."""

    def __init__(self, message: str, details: Optional[dict] = None):
        super().__init__(
            message=message,
            code="WORKFLOW_ERROR",
            status_code=400,
            details=details or {},
        )


class ToolExecutionError(AppError):
    """Tool execution error."""

    def __init__(self, tool: str, action: str, message: str):
        super().__init__(
            message=f"Tool execution failed: {tool}.{action} - {message}",
            code="TOOL_EXECUTION_ERROR",
            status_code=500,
            details={"tool": tool, "action": action},
        )


class LLMError(AppError):
    """LLM provider error."""

    def __init__(self, message: str = "LLM service unavailable"):
        super().__init__(
            message=message,
            code="LLM_ERROR",
            status_code=503,
        )


class ErrorResponse(BaseModel):
    """Standard error response schema."""

    status: str = "error"
    error: dict


async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    """Handle application errors and return consistent JSON responses."""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "status": "error",
            "error": {
                "code": exc.code,
                "message": exc.message,
                "details": exc.details,
            },
        },
    )


async def generic_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle unexpected errors."""
    return JSONResponse(
        status_code=500,
        content={
            "status": "error",
            "error": {
                "code": "INTERNAL_ERROR",
                "message": "An unexpected error occurred",
                "details": {},
            },
        },
    )
