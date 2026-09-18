"""
Shared response schemas used across the API.
"""

from pydantic import BaseModel
from typing import Any, Optional, Generic, TypeVar, List
from datetime import datetime

T = TypeVar("T")


class SuccessResponse(BaseModel):
    """Standard success response wrapper."""

    status: str = "success"
    data: Any = None
    message: Optional[str] = None


class PaginationMeta(BaseModel):
    """Pagination metadata."""

    page: int
    per_page: int
    total: int
    total_pages: int


class PaginatedResponse(BaseModel):
    """Paginated response wrapper."""

    status: str = "success"
    data: Any = None
    pagination: PaginationMeta


class HealthResponse(BaseModel):
    """Health check response."""

    status: str
    version: str
    services: dict[str, str]
