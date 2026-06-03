"""
Booking tool module.

Handles cab booking requests with external dispatch API.
Includes confirmation validation as a critical gate.
"""

import json
import logging
from datetime import datetime
from typing import Any, Dict, Optional

import httpx
from fastapi import HTTPException, status

from app.config import settings

logger = logging.getLogger(__name__)


async def book_outstation_drop(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Create a booking with Lageego API.
    
    Creates a booking request. Requires confirmation flag to be True before proceeding.
    
    Args:
        payload: Request payload containing:
            - ridereq_for: Rider request identifier
            - ride_occname: Occurrence name
            - ride_pickupgps: Pickup GPS coordinates
            - ride_startloc: Start location
            - ride_destination: Destination
            - ride_datetime: Ride date and time
            - ride_vehicle_type: Type of vehicle
            - ride_passengerscount: Number of passengers
            - ride_contact: Contact number
            - ride_operatormobile: (Optional) Operator mobile number. Defaults to empty string if not provided
            - ride_customermobile: Customer mobile number
            - ride_generatedtime: Generated timestamp
            - confirmed: Confirmation flag (MUST be True)
            
    Returns:
        Dict with normalized booking data
        
    Raises:
        HTTPException: If confirmation is not True (403 Forbidden)
        ValueError: If required fields are missing
        httpx.HTTPError: If API request fails
    """
    logger.info(f"[BOOKING] Processing booking request")
    logger.info(f"[BOOKING] Incoming Payload:\n{json.dumps(payload, indent=2, default=str)}")
    
    # Validate payload is a dict
    if not isinstance(payload, dict):
        logger.error(f"[BOOKING] Invalid payload type: {type(payload)}")
        raise ValueError("Payload must be a dictionary")
    
    # CONFIRMATION GATE - VERY IMPORTANT
    confirmed = payload.get("confirmed", False)
    if confirmed is not True:
        logger.warning(f"[BOOKING] REJECTED - Booking not confirmed (confirmed={confirmed})")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Booking must be confirmed before proceeding"
        )
    
    logger.info("[BOOKING] ✓ Confirmation validated")
    
    # Get current timestamp for ride_generatedtime in 'YYYY-MM-DD HH:MM:SS' format
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Extract required fields for Lageego API
    required_fields = [
        "ridereq_for", "ride_pickupgps", "ride_startloc",
        "ride_destination", "ride_datetime", "ride_vehicle_type",
        "ride_passengerscount", "ride_contact",
        "ride_customermobile"
    ]
    
    missing_fields = [field for field in required_fields if not payload.get(field)]
    if missing_fields:
        logger.error(f"[BOOKING] Missing required fields: {missing_fields}")
        raise ValueError(f"Required fields missing: {', '.join(missing_fields)}")
    
    logger.info(f"[BOOKING] Creating booking: {payload.get('ride_startloc')} → {payload.get('ride_destination')}")
    
    try:
        # Format ride_datetime to 'YYYY-MM-DD HH:MM:SS' format
        ride_datetime_str = payload.get("ride_datetime")
        if ride_datetime_str:
            try:
                # Handle ISO format (2026-05-28T14:30:00) → (2026-05-28 14:30:00)
                if "T" in ride_datetime_str:
                    dt = datetime.fromisoformat(ride_datetime_str)
                    ride_datetime_formatted = dt.strftime("%Y-%m-%d %H:%M:%S")
                else:
                    # Already in correct format
                    ride_datetime_formatted = ride_datetime_str
                logger.info(f"[BOOKING] ride_datetime converted: {ride_datetime_str} → {ride_datetime_formatted}")
            except Exception as e:
                logger.warning(f"[BOOKING] Could not parse ride_datetime: {e}, using as-is")
                ride_datetime_formatted = ride_datetime_str
        else:
            ride_datetime_formatted = None
        
        # Format ride_generatedtime to 'YYYY-MM-DD HH:MM:SS' format if provided
        ride_generatedtime_str = payload.get("ride_generatedtime")
        if ride_generatedtime_str:
            try:
                # Handle ISO format (2026-05-27T13:15:08.568570) → (2026-05-27 13:15:08)
                if "T" in ride_generatedtime_str:
                    dt = datetime.fromisoformat(ride_generatedtime_str)
                    ride_generatedtime_formatted = dt.strftime("%Y-%m-%d %H:%M:%S")
                else:
                    # Already in correct format
                    ride_generatedtime_formatted = ride_generatedtime_str
                logger.info(f"[BOOKING] ride_generatedtime formatted: {ride_generatedtime_str} → {ride_generatedtime_formatted}")
            except Exception as e:
                logger.warning(f"[BOOKING] Could not parse ride_generatedtime: {e}, using current time")
                ride_generatedtime_formatted = current_time
        else:
            ride_generatedtime_formatted = current_time  # Use current time if not provided
        
        # Make booking request to Lageego API
        async with httpx.AsyncClient(timeout=60) as client:
            url = settings.BOOKING_API_URL
            
            # Prepare request body with exact field names
            booking_data = {
                "ridereq_for": payload.get("ridereq_for"),
                "ride_occname": payload.get("ride_occname", "LAGEEGO"),  # Default to "LAGEEGO"
                "ride_pickupgps": payload.get("ride_pickupgps"),
                "ride_startloc": payload.get("ride_startloc"),
                "ride_destination": payload.get("ride_destination"),
                "ride_datetime": ride_datetime_formatted,  # Format: 'YYYY-MM-DD HH:MM:SS'
                "ride_vehicle_type": payload.get("ride_vehicle_type"),
                "ride_passengerscount": payload.get("ride_passengerscount"),
                "ride_contact": payload.get("ride_contact"),
                "ride_operatormobile": payload.get("ride_operatormobile", ""),  # Default to empty string if not provided
                "ride_customermobile": payload.get("ride_customermobile"),
                "ride_generatedtime": ride_generatedtime_formatted  # Format: 'YYYY-MM-DD HH:MM:SS'
            }
            
            logger.debug(f"[BOOKING] Request → {url}")
            logger.info(f"[BOOKING] API Request Payload:\n{json.dumps(booking_data, indent=2, default=str)}")
            
            response = await client.post(url, json=booking_data)
            
            # Log response status and content for debugging
            logger.info(f"[BOOKING] Response Status: {response.status_code}")
            
            try:
                response_content = response.json()
                logger.info(f"[BOOKING] API Response:\n{json.dumps(response_content, indent=2, default=str)}")
            except:
                response_content = response.text
                logger.info(f"[BOOKING] API Response (text): {response_content[:500]}")
            
            if response.status_code != 200:
                try:
                    error_detail = response.text if isinstance(response_content, str) else json.dumps(response_content, indent=2, default=str)
                    logger.error(f"[BOOKING] API Error:\n{error_detail[:500]}")
                except:
                    logger.error(f"[BOOKING] Could not parse error response")
            
            response.raise_for_status()
            
            raw_response = response_content if isinstance(response_content, dict) else response.json()
            logger.info(f"[BOOKING] ✓ Response received successfully")
            
            # Validate ridereq_id for success (API returns ridereq_id as booking ID)
            ridereq_id = raw_response.get('ridereq_id')
            if not ridereq_id:
                logger.error(f"[BOOKING] No ridereq_id in response: {raw_response}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Booking creation failed: API did not return ridereq_id"
                )
            
            logger.info(f"[BOOKING] ✓ Booking confirmed | Ridereq ID: {ridereq_id}")
            
            # Format response with standardized structure
            formatted_response = {
                "status": "success",
                "message": raw_response.get("message", "Booking created successfully"),
                "booking_id": ridereq_id,
                "ridereq_id": ridereq_id,
                "ride_from": payload.get("ride_startloc"),
                "ride_to": payload.get("ride_destination"),
                "vehicle_type": payload.get("ride_vehicle_type"),
                "datetime": ride_datetime_formatted,
                "passengers": payload.get("ride_passengerscount"),
                "contact": payload.get("ride_contact")
            }
            
            logger.info(f"[BOOKING] ✓ Formatted Response:\n{json.dumps(formatted_response, indent=2, default=str)}")
            
            return formatted_response
            
    except HTTPException:
        raise
    except httpx.TimeoutException as e:
        logger.error(f"[BOOKING] API timeout: {e}")
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="Booking API request timed out. Please try again later."
        )
    except httpx.HTTPError as e:
        logger.error(f"[BOOKING] HTTP Error: {e}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Booking API error: {str(e)}"
        )
    except ValueError as e:
        logger.error(f"[BOOKING] Validation error: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid booking data: {str(e)}"
        )
    except Exception as e:
        logger.error(f"[BOOKING] Unexpected error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Booking service error: {str(e)}"
        )
