"""
Search Hotels Tool (Agoda Primary, Google Maps Fallback)

Enhanced tool that searches hotels using Agoda when available,
falls back to Google Maps if Agoda is unavailable.

IMPORTANT: This is an AI-friendly orchestration layer.
The LLM never sees Agoda API complexity or raw payloads.
"""

import logging
import json
from typing import Any, Dict
from datetime import datetime

from fastapi import HTTPException, status

from app.tools.agoda_client import get_agoda_client
from app.tools.booking_transformers import BookingTransformer
from app.tools.hotels import search_hotels as google_search_hotels

logger = logging.getLogger(__name__)


async def search_hotels(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Search for hotels using Agoda (primary) or Google Maps (fallback).
    
    This is the primary hotel search tool exposed to the LLM.
    
    Input schema:
    {
        "location": "Madurai",           # Required: City name or address
        "checkin": "2026-06-15",         # Required: ISO date format
        "checkout": "2026-06-20",        # Required: ISO date format
        "adults": 2,                     # Required: Number of adults
        "rooms": 1,                      # Optional: Number of rooms (default: 1)
        "children": 0,                   # Optional: Number of children (default: 0)
        "childrenAges": [],              # Optional: Ages of children
        "budget_max": 10000              # Optional: Max price per night in INR
    }
    
    Output: Normalized AI-friendly hotel list (same whether from Agoda or Google)
    {
        "hotels": [
            {
                "hotel_id": string,
                "name": string,
                "price_per_night": number,
                "currency": "INR",
                "review_score": number,
                "address": string,
                "thumbnail": string,
                "free_wifi": boolean,
                "free_breakfast": boolean,
                "free_cancellation": boolean
            }
        ],
        "total": number,
        "source": "agoda" | "google_maps",
        "available": true,
        "search_id": string (from Agoda if applicable)
    }
    
    Args:
        payload: Search request with required fields above
        
    Returns:
        Normalized hotel list from primary or fallback source
        
    Raises:
        HTTPException: If both Agoda and Google Maps fail
    """
    
    # Validate payload
    if not isinstance(payload, dict):
        logger.error("[SEARCH-HOTELS] Invalid payload type")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Payload must be a dictionary"
        )
    
    # Validate required fields
    required_fields = ["location", "checkin", "checkout", "adults"]
    missing = [f for f in required_fields if f not in payload]
    
    if missing:
        logger.error(f"[SEARCH-HOTELS] Missing required fields: {missing}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Missing required fields: {', '.join(missing)}"
        )
    
    location = payload.get("location")
    checkin = payload.get("checkin")
    checkout = payload.get("checkout")
    adults = payload.get("adults")
    rooms = payload.get("rooms", 1)
    children = payload.get("children", 0)
    children_ages = payload.get("childrenAges", [])
    budget_max = payload.get("budget_max")
    
    logger.info(f"[SEARCH-HOTELS] Searching hotels: {location}, {checkin}-{checkout}, {adults} adults")
    
    # Try Agoda first (primary source)
    try:
        logger.info("[SEARCH-HOTELS] Attempting Agoda search (primary)...")
        agoda_client = get_agoda_client()
        
        # Build Agoda search criteria
        criteria = {
            "checkIn": checkin,
            "checkOut": checkout,
            "rooms": rooms,
            "adults": adults,
            "children": children,
            "language": "en-us",
            "currency": "INR",
            "userCountry": "US"
        }
        
        if children > 0 and children_ages:
            criteria["childrenAges"] = children_ages
        
        # Perform Agoda search
        agoda_response = await agoda_client.search_hotels(criteria)
        
        # Transform Agoda response to normalized format
        transformer = BookingTransformer()
        normalized_hotels = transformer.transform_agoda_search(agoda_response, budget_max)
        
        logger.info(f"[SEARCH-HOTELS] Agoda search succeeded: {len(normalized_hotels.get('hotels', []))} hotels found")
        
        return normalized_hotels
        
    except HTTPException:
        raise
    except Exception as e:
        logger.warning(f"[SEARCH-HOTELS] Agoda search failed: {str(e)}")
        logger.info("[SEARCH-HOTELS] Falling back to Google Maps...")
    
    # Fallback to Google Maps
    try:
        logger.info("[SEARCH-HOTELS] Attempting Google Maps fallback...")
        google_result = await google_search_hotels(payload)
        
        if google_result and google_result.get("available"):
            logger.info(f"[SEARCH-HOTELS] Google Maps search succeeded: {len(google_result.get('hotels', []))} hotels found")
            return google_result
        else:
            logger.error("[SEARCH-HOTELS] Google Maps search returned no results")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No hotels found in the specified location and dates"
            )
            
    except Exception as e:
        logger.error(f"[SEARCH-HOTELS] Both Agoda and Google Maps failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Hotel search service unavailable. Please try again later."
        )
