"""
Fare estimation tool module.

Handles fare estimation inquiries with Lageego API.
"""

import json
import logging
from typing import Any, Dict

import httpx
from fastapi import HTTPException, status

from app.config import settings

logger = logging.getLogger(__name__)


async def get_estimated_fare(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Get estimated fare from Lageego API.
    
    Queries the Lageego API for estimated fare between start and destination using GET with query parameters.
    
    Args:
        payload: Request payload containing:
            - start_loc: Start location
            - destination_loc: Destination location
            
    Returns:
        Dict with raw fare estimation data from Lageego API
        
    Raises:
        HTTPException: If API request fails or required fields are missing
    """
    # Validate payload
    if not isinstance(payload, dict):
        logger.error(f"[FARE] Invalid payload type: {type(payload)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Payload must be a dictionary"
        )
    
    start_loc = payload.get("start_loc")
    destination_loc = payload.get("destination_loc")
    
    logger.info(f"[FARE] Fetching fare estimate: {start_loc} → {destination_loc}")
    
    # Validate required fields
    if not start_loc or not destination_loc:
        logger.error("[FARE] Missing start_loc or destination_loc")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="start_loc and destination_loc are required"
        )
    
    try:
        # Make request to Lageego fare API using GET with query parameters
        async with httpx.AsyncClient(timeout=60) as client:
            url = settings.FARE_API_URL
            
            # Prepare query parameters
            params = {
                "start_loc": start_loc,
                "destination_loc": destination_loc
            }
            
            logger.debug(f"[FARE] Request → {url}")
            logger.info(f"[FARE] Query Params: {params}")
            
            response = await client.get(url, params=params)
            
            # Log response status
            logger.info(f"[FARE] Response Status: {response.status_code}")
            
            if response.status_code != 200:
                logger.error(f"[FARE] API Error: {response.text[:500]}")
                raise HTTPException(
                    status_code=response.status_code,
                    detail=f"Fare API returned {response.status_code}"
                )
            
            response.raise_for_status()
            
            raw_response = response.json()
            logger.info(f"[FARE] API Response:\n{json.dumps(raw_response, indent=2, default=str)}")
            
            # Return raw response as-is
            fare_count = len(raw_response.get('fares', []))
            logger.info(f"[FARE] ✓ Fare estimates retrieved ({fare_count} vehicle options)")
            
            return raw_response
            
    except HTTPException:
        raise
    except httpx.TimeoutException as e:
        logger.error(f"[FARE] API timeout: {e}")
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="Fare API request timed out. Please try again later."
        )
    except httpx.HTTPError as e:
        logger.error(f"[FARE] HTTP Error: {e}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Fare API error: {str(e)}"
        )
    except Exception as e:
        logger.error(f"[FARE] Unexpected error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Fare service error: {str(e)}"
        )
