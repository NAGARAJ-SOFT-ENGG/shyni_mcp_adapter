"""
Confirmation middleware module.

Validates confirmation status before processing booking requests.
"""

import logging
from typing import Any, Dict

from fastapi import HTTPException, status

logger = logging.getLogger(__name__)


def validate_confirmation(payload: Dict[str, Any]) -> None:
    """Validate that booking request is confirmed.
    
    Raises HTTPException if confirmed is not True.
    
    Args:
        payload: Request payload dictionary
        
    Raises:
        HTTPException: If confirmed is not True (403 Forbidden)
    """
    confirmed = payload.get("confirmed", False)
    
    logger.debug(f"Validating confirmation: {confirmed}")
    
    if confirmed is not True:
        logger.warning(
            f"Booking request rejected: confirmation not provided. Payload: {payload}"
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Booking must be confirmed before proceeding"
        )
    
    logger.info("Booking confirmation validated successfully")
