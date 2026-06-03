"""
Hotel search tool module.

Handles hotel search queries using Google Maps API.
"""

import json
import logging
import math
from typing import Any, Dict

import httpx
from fastapi import HTTPException, status

from app.config import settings

logger = logging.getLogger(__name__)

# Google Maps API endpoints
PLACES_API_URL = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"
PLACE_DETAILS_API_URL = "https://maps.googleapis.com/maps/api/place/details/json"


def calculate_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate distance between two coordinates using Haversine formula.
    
    Args:
        lat1, lon1: First coordinate (latitude, longitude)
        lat2, lon2: Second coordinate (latitude, longitude)
        
    Returns:
        Distance in kilometers
    """
    R = 6371  # Earth's radius in kilometers
    
    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    delta_lat = math.radians(lat2 - lat1)
    delta_lon = math.radians(lon2 - lon1)
    
    a = math.sin(delta_lat / 2) ** 2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon / 2) ** 2
    c = 2 * math.asin(math.sqrt(a))
    
    return R * c


def get_estimated_daily_rate(price_level: int) -> Dict[str, Any]:
    """Get estimated daily hotel rate based on price level.
    
    Args:
        price_level: Google price level (1-4)
        
    Returns:
        Dict with min, max, currency, and display format
    """
    # Estimated rates in INR (Indian Rupees) - adjust as needed for your region
    rate_mapping = {
        1: {"min": 500, "max": 1000},      # Budget
        2: {"min": 1000, "max": 2500},    # Moderate
        3: {"min": 2500, "max": 5000},    # Expensive
        4: {"min": 5000, "max": 15000}    # Very Expensive
    }
    
    if price_level not in rate_mapping:
        return None
    
    rates = rate_mapping[price_level]
    return {
        "currency": "INR",
        "min": rates["min"],
        "max": rates["max"],
        "display": f"₹{rates['min']} to ₹{rates['max']} per day"
    }


async def search_hotels(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Search for hotels near given coordinates using Google Maps API.
    
    Queries Google Places API for hotels within specified radius.
    
    Args:
        payload: Request payload containing:
            - latitude: Search location latitude (required)
            - longitude: Search location longitude (required)
            - radius_km: Search radius in kilometers (optional, default: 10)
            
    Returns:
        Dict with hotel data including names, distances, ratings, prices
        
    Raises:
        HTTPException: If API request fails or required fields are missing
    """
    # Validate payload
    if not isinstance(payload, dict):
        logger.error(f"[HOTELS] Invalid payload type: {type(payload)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Payload must be a dictionary"
        )
    
    # Validate API key
    if not settings.GOOGLE_MAPS_API_KEY:
        logger.error("[HOTELS] Google Maps API key not configured")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Google Maps API key is not configured"
        )
    
    # Extract coordinates
    latitude = payload.get("latitude")
    longitude = payload.get("longitude")
    radius_km = payload.get("radius_km", 10)
    
    # Validate required fields
    if latitude is None or longitude is None:
        logger.error("[HOTELS] Missing latitude or longitude")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="latitude and longitude are required"
        )
    
    # Validate coordinate ranges
    if not (-90 <= latitude <= 90):
        logger.error(f"[HOTELS] Invalid latitude: {latitude}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Latitude must be between -90 and 90"
        )
    
    if not (-180 <= longitude <= 180):
        logger.error(f"[HOTELS] Invalid longitude: {longitude}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Longitude must be between -180 and 180"
        )
    
    logger.info(f"[HOTELS] Searching hotels at {latitude}, {longitude} (radius: {radius_km}km)")
    
    try:
        # Convert radius from km to meters
        radius_meters = radius_km * 1000
        
        # Make request to Google Places API
        async with httpx.AsyncClient(timeout=30) as client:
            params = {
                "location": f"{latitude},{longitude}",
                "radius": radius_meters,
                "type": "lodging",
                "key": settings.GOOGLE_MAPS_API_KEY
            }
            
            logger.debug(f"[HOTELS] Request → {PLACES_API_URL}")
            
            response = await client.get(PLACES_API_URL, params=params)
            
            logger.info(f"[HOTELS] Response Status: {response.status_code}")
            
            if response.status_code != 200:
                logger.error(f"[HOTELS] API Error: {response.text[:500]}")
                raise HTTPException(
                    status_code=response.status_code,
                    detail=f"Google Maps API returned {response.status_code}"
                )
            
            response.raise_for_status()
            
            api_response = response.json()
            
            # Print full API response for debugging
            logger.info("[HOTELS] ========== GOOGLE PLACES API (NEARBY SEARCH) RESPONSE ==========")
            logger.info(f"[HOTELS] Full Response:\n{json.dumps(api_response, indent=2)}")
            logger.info("[HOTELS] ================================================================")
            
            # Check for API errors
            if api_response.get("status") != "OK":
                status_msg = api_response.get("status", "UNKNOWN")
                logger.warning(f"[HOTELS] Google API Status: {status_msg}")
                if status_msg == "ZERO_RESULTS":
                    return {
                        "hotels": [],
                        "search_center": {
                            "latitude": latitude,
                            "longitude": longitude,
                            "radius_km": radius_km
                        },
                        "total_results": 0,
                        "error": False,
                        "message": "No hotels found in the specified radius"
                    }
            
            # Process results
            hotels = []
            results = api_response.get("results", [])
            
            for place in results:
                try:
                    # Log raw Google API response for each hotel
                    logger.info("[HOTELS] ========== GOOGLE PLACES API INDIVIDUAL RESULT ==========")
                    logger.info(f"[HOTELS] Raw Response:\n{json.dumps(place, indent=2)}")
                    
                    # Calculate distance from search center
                    place_lat = place.get("geometry", {}).get("location", {}).get("lat")
                    place_lon = place.get("geometry", {}).get("location", {}).get("lng")
                    
                    if place_lat and place_lon:
                        distance = calculate_distance(latitude, longitude, place_lat, place_lon)
                    else:
                        distance = None
                    
                    # Extract price level (convert to rent range estimate)
                    price_level = place.get("price_level")
                    price_range = {
                        1: "$",
                        2: "$$",
                        3: "$$$",
                        4: "$$$$"
                    }.get(price_level)
                    
                    # Get estimated daily rate based on price level
                    daily_rate = get_estimated_daily_rate(price_level) if price_level else None
                    
                    # Get phone number - prefer international format
                    phone = place.get("international_phone_number") or place.get("formatted_phone_number")
                    
                    # Check if hotel is open now
                    is_open = place.get("opening_hours", {}).get("open_now", False)
                    
                    hotel_data = {
                        "name": place.get("name"),
                        "distance_km": round(distance, 2) if distance else None,
                        "rating": place.get("rating"),
                        "review_count": place.get("user_ratings_total"),
                        "is_open": is_open,
                        "daily_rate_range": daily_rate,
                        "latitude": place_lat,
                        "longitude": place_lon,
                        "address": place.get("vicinity"),
                        "phone": phone,
                        "website": place.get("website")
                    }
                    
                    hotels.append(hotel_data)
                    
                except Exception as e:
                    logger.warning(f"[HOTELS] Error processing hotel result: {e}")
                    continue
            
            logger.info("[HOTELS] ================================================================")
            
            # Sort by distance
            hotels.sort(key=lambda h: h.get("distance_km") or float('inf'))
            
            logger.info(f"[HOTELS] ✓ Found {len(hotels)} hotels")
            logger.info("[HOTELS] ================================================================")
            
            return {
                "hotels": hotels,
                "search_center": {
                    "latitude": latitude,
                    "longitude": longitude,
                    "radius_km": radius_km
                },
                "total_results": len(hotels),
                "error": False,
                "message": f"Found {len(hotels)} hotels"
            }
            
    except HTTPException:
        raise
    except httpx.TimeoutException as e:
        logger.error(f"[HOTELS] API timeout: {e}")
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="Google Maps API request timed out. Please try again later."
        )
    except httpx.HTTPError as e:
        logger.error(f"[HOTELS] HTTP Error: {e}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Google Maps API error: {str(e)}"
        )
    except Exception as e:
        logger.error(f"[HOTELS] Unexpected error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Hotel search failed: {str(e)}"
        )
