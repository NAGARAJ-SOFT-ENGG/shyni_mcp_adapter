"""
Availability tool module.

Handles cab availability inquiries with external dispatch API.
"""

import logging
from typing import Any, Dict

import httpx
from fastapi import HTTPException, status

from app.config import settings

logger = logging.getLogger(__name__)


async def get_cab_availability(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Get cab availability from TDConAir API.
    
    Queries the TDConAir vehicle availability endpoint.
    
    Args:
        payload: Request payload containing:
            - operator_mobile: (Optional) Operator mobile number. Defaults to empty string if not provided
            
    Returns:
        Dict with raw availability data from TDConAir API
        
    Raises:
        HTTPException: If API request fails or configuration is missing
    """
    # Validate payload
    if not isinstance(payload, dict):
        logger.error(f"[AVAILABILITY] Invalid payload type: {type(payload)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Payload must be a dictionary"
        )
    
    # Get operator_mobile from payload or default to empty string
    operator_mobile = payload.get("operator_mobile", "")
    
    if operator_mobile:
        logger.info(f"[AVAILABILITY] Fetching cabs with operator_mobile: {operator_mobile}")
    else:
        logger.info("[AVAILABILITY] Fetching cabs with empty operator_mobile")
    
    try:
        # Make request to TDConAir API
        async with httpx.AsyncClient(timeout=60) as client:
            url = settings.AVAILABILITY_API_URL
            params = {
                "operator_mobile": operator_mobile
            }
            
            logger.debug(f"[AVAILABILITY] Request → {url} | Params: {params}")
            
            response = await client.get(url, params=params)
            
            # Log response status
            logger.info(f"[AVAILABILITY] Response Status: {response.status_code}")
            
            if response.status_code != 200:
                logger.error(f"[AVAILABILITY] API Error: {response.text[:500]}")
                raise HTTPException(
                    status_code=response.status_code,
                    detail=f"Availability API returned {response.status_code}"
                )
            
            response.raise_for_status()
            
            raw_response = response.json()
            logger.info(f"[AVAILABILITY] ✓ Response received with {len(raw_response.get('current', []))} current cabs")
            
            # Return raw response as-is
            return raw_response
            
    except HTTPException:
        raise
    except httpx.TimeoutException as e:
        logger.error(f"[AVAILABILITY] API timeout: {e}")
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="Availability API request timed out. Please try again later."
        )
    except httpx.HTTPError as e:
        logger.error(f"[AVAILABILITY] HTTP Error: {e}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Availability API error: {str(e)}"
        )
    except Exception as e:
        logger.error(f"[AVAILABILITY] Unexpected error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Availability service error: {str(e)}"
        )
