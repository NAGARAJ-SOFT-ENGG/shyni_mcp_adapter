"""
Booking.com Response Transformer Module

Normalizes raw Booking.com API responses into clean, AI-friendly formats.
Hides Booking.com complexity and creates consistent data structures for the LLM.

This layer ensures:
- No raw Booking.com payloads exposed
- Consistent schema across different API endpoints
- Clean, semantic field names
- Filtered unnecessary nested structures
"""

import logging
from typing import Any, Dict, List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class BookingTransformer:
    """Transform Booking.com API responses to AI-friendly formats."""
    
    @staticmethod
    def normalize_hotel_search(api_response: Dict[str, Any]) -> Dict[str, Any]:
        """
        Transform search results into AI-friendly hotel list.
        
        Extracts only essential information and removes noise from raw API response.
        
        Args:
            api_response: Raw response from /accommodations/search endpoint
            
        Returns:
            Normalized hotel list with schema:
            {
                "hotels": [
                    {
                        "hotel_id": string,
                        "name": string,
                        "price_per_night": number,
                        "currency": string,
                        "review_score": number (0-5),
                        "address": string,
                        "thumbnail": string
                    }
                ],
                "total": number
            }
        """
        hotels = []
        
        accommodations = api_response.get("accommodations", [])
        logger.info(f"[BOOKING-TRANSFORMER] Normalizing {len(accommodations)} hotels")
        
        for acc in accommodations:
            try:
                # Extract core hotel info
                hotel_id = str(acc.get("id", ""))
                name = acc.get("name", "Unknown Hotel")
                
                # Get pricing info
                price_info = acc.get("price", {})
                price_per_night = price_info.get("total", 0) / (price_info.get("nights", 1) or 1)
                currency = price_info.get("currency", "USD")
                
                # Get rating
                review_score = None
                review_data = acc.get("review", {})
                if review_data:
                    review_score = review_data.get("review_score")
                
                # Build normalized hotel object
                hotel = {
                    "hotel_id": hotel_id,
                    "name": name,
                    "price_per_night": round(price_per_night, 2),
                    "currency": currency,
                }
                
                # Add optional fields if available
                if review_score is not None:
                    hotel["review_score"] = min(5.0, review_score / 2)  # Convert 10-scale to 5-scale if needed
                
                if acc.get("address"):
                    hotel["address"] = acc.get("address")
                
                if acc.get("thumbnail"):
                    hotel["thumbnail"] = acc.get("thumbnail")
                
                hotels.append(hotel)
                
            except Exception as e:
                logger.warning(f"[BOOKING-TRANSFORMER] Error normalizing hotel: {e}")
                continue
        
        return {
            "hotels": hotels,
            "total": len(hotels)
        }
    
    @staticmethod
    def normalize_room_availability(
        availability_response: Dict[str, Any],
        details_response: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Transform availability and details into AI-friendly room options.
        
        Merges room availability with hotel details for complete context.
        
        Args:
            availability_response: Response from /accommodations/availability
            details_response: Response from /accommodations/details (optional)
            
        Returns:
            Normalized format:
            {
                "hotel": {
                    "hotel_id": string,
                    "name": string,
                    "address": string,
                    "review_score": number,
                    "checkin_time": string (HH:MM),
                    "checkout_time": string (HH:MM)
                },
                "rooms": [
                    {
                        "room_id": string,
                        "room_name": string,
                        "price": number,
                        "currency": string,
                        "breakfast_included": boolean,
                        "free_cancellation": boolean,
                        "cancellation_deadline": string (ISO date or null)
                    }
                ]
            }
        """
        logger.info("[BOOKING-TRANSFORMER] Normalizing room availability and details")
        
        # Extract hotel info
        hotel_info = availability_response.get("hotel", {})
        hotel_id = hotel_info.get("id", "")
        
        hotel_obj = {
            "hotel_id": str(hotel_id),
            "name": hotel_info.get("name", "Unknown Hotel"),
        }
        
        # Add details if provided
        if details_response:
            details = details_response.get("hotel", {})
            if details.get("address"):
                hotel_obj["address"] = details.get("address")
            if details.get("review_score"):
                hotel_obj["review_score"] = min(5.0, details.get("review_score") / 2)
            
            # Extract check-in/out times from policies
            policies = details.get("policies", {})
            if policies.get("checkin_time"):
                hotel_obj["checkin_time"] = policies.get("checkin_time")
            if policies.get("checkout_time"):
                hotel_obj["checkout_time"] = policies.get("checkout_time")
        
        # Process room products
        rooms = []
        products = availability_response.get("products", [])
        
        for product in products:
            try:
                room_id = str(product.get("id", ""))
                
                # Extract cancellation policy
                free_cancellation = False
                cancellation_deadline = None
                
                cancellation_policy = product.get("cancellation_policy", {})
                if cancellation_policy.get("type") == "free":
                    free_cancellation = True
                    if cancellation_policy.get("deadline"):
                        cancellation_deadline = cancellation_policy.get("deadline")
                
                # Extract meal plan
                meal_plan = product.get("meal_plan", {})
                breakfast_included = meal_plan.get("breakfast", False)
                
                # Build room object
                room = {
                    "room_id": room_id,
                    "room_name": product.get("name", "Room"),
                    "price": product.get("price", {}).get("total", 0),
                    "currency": product.get("price", {}).get("currency", "USD"),
                    "breakfast_included": breakfast_included,
                    "free_cancellation": free_cancellation,
                }
                
                if cancellation_deadline:
                    room["cancellation_deadline"] = cancellation_deadline
                
                rooms.append(room)
                
            except Exception as e:
                logger.warning(f"[BOOKING-TRANSFORMER] Error normalizing room: {e}")
                continue
        
        return {
            "hotel": hotel_obj,
            "rooms": rooms
        }
    
    @staticmethod
    def normalize_booking_confirmation(
        create_response: Dict[str, Any],
        preview_response: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Transform booking creation response into AI-friendly confirmation.
        
        Simplifies booking confirmation and hides order_token.
        
        Args:
            create_response: Response from /orders/create
            preview_response: Response from /orders/preview (for additional context)
            
        Returns:
            Normalized format:
            {
                "booking_reference": string,
                "status": "confirmed",
                "hotel_name": string,
                "room_name": string,
                "final_price": number,
                "currency": string,
                "checkin": string (ISO date),
                "checkout": string (ISO date),
                "guest_name": string
            }
        """
        logger.info("[BOOKING-TRANSFORMER] Normalizing booking confirmation")
        
        confirmation = {
            "booking_reference": create_response.get("booking_reference", ""),
            "status": "confirmed"
        }
        
        # Add booking details if available
        booking = create_response.get("booking", {})
        if booking.get("hotel_name"):
            confirmation["hotel_name"] = booking.get("hotel_name")
        
        if booking.get("room_name"):
            confirmation["room_name"] = booking.get("room_name")
        
        # Price info
        price_info = booking.get("price", {})
        if price_info.get("total"):
            confirmation["final_price"] = price_info.get("total")
        if price_info.get("currency"):
            confirmation["currency"] = price_info.get("currency")
        
        # Dates
        if booking.get("checkin"):
            confirmation["checkin"] = booking.get("checkin")
        if booking.get("checkout"):
            confirmation["checkout"] = booking.get("checkout")
        
        if booking.get("guest_name"):
            confirmation["guest_name"] = booking.get("guest_name")
        
        return confirmation
    
    @staticmethod
    def handle_inventory_error(error_response: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle inventory error responses gracefully.
        
        When inventory changes between preview and create, return user-friendly message.
        
        Args:
            error_response: Error response from /orders/create
            
        Returns:
            Normalized error format for LLM
        """
        logger.warning(f"[BOOKING-TRANSFORMER] Handling inventory error")
        
        return {
            "status": "inventory_changed",
            "error": "The room you selected is no longer available or pricing has changed.",
            "message": "Please search again and select a different room.",
            "recoverable": True
        }

    @staticmethod
    def transform_agoda_search(
        agoda_response: Dict[str, Any],
        budget_max: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Transform Agoda search response into AI-friendly hotel list.
        
        Extracts only essential information from Agoda's complex response format.
        
        Args:
            agoda_response: Raw response from Agoda /demand/v2/search endpoint
            budget_max: Optional maximum budget per night to filter results
            
        Returns:
            Normalized hotel list with schema:
            {
                "hotels": [
                    {
                        "hotel_id": string,
                        "name": string,
                        "price_per_night": number,
                        "currency": string,
                        "review_score": number (0-5),
                        "address": string,
                        "free_wifi": boolean,
                        "free_breakfast": boolean,
                        "free_cancellation": boolean
                    }
                ],
                "total": number,
                "source": "agoda",
                "available": boolean,
                "search_id": string
            }
        """
        hotels = []
        search_id = agoda_response.get("searchId", "")
        
        properties = agoda_response.get("properties", [])
        logger.info(f"[BOOKING-TRANSFORMER] Transforming {len(properties)} Agoda properties")
        
        for property_data in properties:
            try:
                property_id = property_data.get("propertyId", "")
                property_name = property_data.get("propertyName", "Unknown Hotel")
                address = property_data.get("address", "")
                rating = property_data.get("rating", 0)
                
                # Extract room information
                rooms = property_data.get("rooms", [])
                
                if not rooms:
                    logger.debug(f"[BOOKING-TRANSFORMER] Property {property_id} has no rooms")
                    continue
                
                # Use the first room as representative
                room = rooms[0]
                
                # Extract price information
                rate_info = room.get("rate", {})
                price_per_night = rate_info.get("inclusive", 0)
                currency = rate_info.get("currency", "USD")
                
                # Apply budget filter if specified
                if budget_max and price_per_night > budget_max:
                    logger.debug(f"[BOOKING-TRANSFORMER] Filtering out {property_name} (${price_per_night} > ${budget_max})")
                    continue
                
                # Extract amenities
                free_wifi = room.get("freeWifi", False)
                free_breakfast = room.get("freeBreakfast", False)
                free_cancellation = room.get("freeCancellation", False)
                
                # Build normalized hotel object
                hotel = {
                    "hotel_id": str(property_id),
                    "name": property_name,
                    "price_per_night": round(price_per_night, 2),
                    "currency": currency,
                    "review_score": rating,
                    "address": address,
                    "free_wifi": free_wifi,
                    "free_breakfast": free_breakfast,
                    "free_cancellation": free_cancellation
                }
                
                hotels.append(hotel)
                
            except Exception as e:
                logger.warning(f"[BOOKING-TRANSFORMER] Error transforming Agoda property: {e}")
                continue
        
        return {
            "hotels": hotels,
            "total": len(hotels),
            "source": "agoda",
            "available": len(hotels) > 0,
            "search_id": search_id
        }
