"""
Middleware module for request validation and processing.
"""

from app.middleware.confirmation import validate_confirmation

__all__ = ["validate_confirmation"]
