"""
Agoda Hotel Booking Tool (Precheck + Booking)

Handles hotel booking workflow:
1. Precheck: Verify availability and rates before booking
2. Book: Create actual hotel reservation

IMPORTANT: Precheck is mandatory before booking to ensure rate/availability verification.
"""

import logging
import json
from typing import Any, Dict, Optional

from fastapi import HTTPException, status

from app.tools.agoda_client import get_agoda_client
from app.tools.booking_transformers import BookingTransformer

logger = logging.getLogger(__name__)


async def precheck_booking(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Precheck hotel booking availability and confirm rates.
    
    MUST be called before actual booking to validate:
    - Room availability hasn't changed
    - Rates haven't changed
    - All details are correct
    
    Input schema:
    {
        "searchId": string,                # From search response
        "propertyId": number,
        "roomId": number,
        "blockId": string,
        "offerToken": string,
        "checkIn": "2026-06-15",
        "checkOut": "2026-06-20",
        "adults": 2,
        "children": 0,
        "childrenAges": [],
        "rooms": 1,
        "currency": "INR",
        "inclusivePrice": number,
        "userCountry": "US"
    }
    
    Output: Availability status
    {
        "status": 200,
        "available": true,
        "message": "Room available and rates confirmed"
    }
    
    Args:
        payload: Precheck details
        
    Returns:
        Precheck response indicating availability
        
    Raises:
        HTTPException: If precheck fails (room not available or rate changed)
    """
    
    if not isinstance(payload, dict):
        logger.error("[PRECHECK-BOOKING] Invalid payload type")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Payload must be a dictionary"
        )
    
    # Validate required fields
    required_fields = ["searchId", "propertyId", "blockId", "checkIn", "checkOut"]
    missing = [f for f in required_fields if f not in payload]
    
    if missing:
        logger.error(f"[PRECHECK-BOOKING] Missing required fields: {missing}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Missing required fields: {', '.join(missing)}"
        )
    
    logger.info(f"[PRECHECK-BOOKING] Precheck for property {payload.get('propertyId')}")
    
    try:
        agoda_client = get_agoda_client()
        
        # Build precheck details
        precheck_details = {
            "searchId": payload.get("searchId"),
            "tag": payload.get("tag", "00000000-0000-0000-0000-000000000000"),
            "allowDuplication": False,
            "checkIn": payload.get("checkIn"),
            "checkOut": payload.get("checkOut"),
            "property": {
                "propertyId": payload.get("propertyId"),
                "rooms": [
                    {
                        "currency": payload.get("currency", "USD"),
                        "paymentModel": payload.get("paymentModel", "Merchant"),
                        "blockId": payload.get("blockId"),
                        "offerToken": payload.get("offerToken", ""),
                        "count": payload.get("rooms", 1),
                        "adults": payload.get("adults", 1),
                        "children": payload.get("children", 0),
                        "childrenAges": payload.get("childrenAges", []),
                        "rate": {
                            "inclusive": payload.get("inclusivePrice", 0)
                        },
                        "surcharges": payload.get("surcharges", [])
                    }
                ]
            },
            "language": "en-us",
            "userCountry": payload.get("userCountry", "US")
        }
        
        # Call Agoda precheck API
        precheck_response = await agoda_client.precheck_booking(precheck_details)
        
        # Check if precheck was successful
        status_code = precheck_response.get("status")
        error_list = precheck_response.get("errorList", [])
        
        if status_code == 200 and not error_list:
            logger.info(f"[PRECHECK-BOOKING] Precheck successful for property {payload.get('propertyId')}")
            return {
                "status": 200,
                "available": True,
                "message": "Room available and rates confirmed",
                "searchId": payload.get("searchId")
            }
        else:
            logger.warning(f"[PRECHECK-BOOKING] Precheck failed: {error_list}")
            error_detail = error_list[0].get("message", "Room availability changed") if error_list else "Precheck failed"
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Availability changed: {error_detail}"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[PRECHECK-BOOKING] Precheck error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Precheck service unavailable"
        )


async def book_hotel(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Create hotel booking via Agoda.
    
    IMPORTANT: Must call precheck_booking first to validate availability!
    
    Input schema:
    {
        "searchId": string,
        "propertyId": number,
        "blockId": string,
        "offerToken": string,
        "checkIn": "2026-06-15",
        "checkOut": "2026-06-20",
        "rooms": 1,
        "adults": 2,
        "children": 0,
        "childrenAges": [],
        "currency": "INR",
        "inclusivePrice": number,
        "surcharges": [],
        "guest": {
            "title": "Mr.",
            "firstName": "John",
            "lastName": "Doe",
            "email": "john@example.com",
            "phone": "+1234567890",
            "countryCode": "US"
        },
        "payment": {
            "cardType": "Visa",
            "cardNumber": "4111111111111111",
            "expiryDate": "12/25",
            "cvc": "123",
            "cardHolderName": "JOHN DOE"
        }
    }
    
    Output: Booking confirmation
    {
        "status": "confirmed",
        "bookingId": string,
        "itineraryId": string,
        "confirmation": {
            "hotel_name": string,
            "checkin": string,
            "checkout": string,
            "final_price": number,
            "currency": string
        },
        "selfServiceLink": string
    }
    
    Args:
        payload: Complete booking details
        
    Returns:
        Booking confirmation with reservation details
        
    Raises:
        HTTPException: If booking fails
    """
    
    if not isinstance(payload, dict):
        logger.error("[BOOK-HOTEL] Invalid payload type")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Payload must be a dictionary"
        )
    
    # Validate required fields
    required_sections = ["guest", "payment"]
    missing_sections = [s for s in required_sections if s not in payload or not payload.get(s)]
    
    if missing_sections:
        logger.error(f"[BOOK-HOTEL] Missing required sections: {missing_sections}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Missing required sections: {', '.join(missing_sections)}"
        )
    
    logger.info(f"[BOOK-HOTEL] Creating booking for property {payload.get('propertyId')}")
    
    try:
        agoda_client = get_agoda_client()
        
        guest = payload.get("guest", {})
        payment = payload.get("payment", {})
        
        # Build booking details
        booking_details = {
            "userCountry": payload.get("userCountry", "US"),
            "searchId": payload.get("searchId"),
            "tag": payload.get("tag", "00000000-0000-0000-0000-000000000000"),
            "allowDuplication": False,
            "checkIn": payload.get("checkIn"),
            "checkOut": payload.get("checkOut"),
            "property": {
                "propertyId": payload.get("propertyId"),
                "rooms": [
                    {
                        "blockId": payload.get("blockId"),
                        "offerToken": payload.get("offerToken", ""),
                        "rate": {
                            "inclusive": payload.get("inclusivePrice", 0)
                        },
                        "surcharges": payload.get("surcharges", []),
                        "guestDetails": [
                            {
                                "title": guest.get("title", "Mr."),
                                "firstName": guest.get("firstName", ""),
                                "lastName": guest.get("lastName", ""),
                                "countryOfResidence": guest.get("countryCode", "US"),
                                "gender": guest.get("gender", "Male"),
                                "age": guest.get("age", 30),
                                "primary": True
                            }
                        ],
                        "currency": payload.get("currency", "USD"),
                        "paymentModel": payload.get("paymentModel", "Merchant"),
                        "count": payload.get("rooms", 1),
                        "adults": payload.get("adults", 1),
                        "children": payload.get("children", 0),
                        "childrenAges": payload.get("childrenAges", []),
                        "specialRequest": payload.get("specialRequest", "")
                    }
                ]
            }
        }
        
        # Build customer details
        customer_detail = {
            "language": "en-us",
            "title": guest.get("title", "Mr."),
            "firstName": guest.get("firstName", ""),
            "lastName": guest.get("lastName", ""),
            "email": guest.get("email", ""),
            "phone": {
                "countryCode": guest.get("countryCode", "1"),
                "areaCode": guest.get("areaCode", ""),
                "number": guest.get("phone", "").replace("+", "").replace("-", "")
            },
            "newsletter": False
        }
        
        # Build payment details
        payment_details = {
            "creditCardInfo": {
                "cardType": payment.get("cardType", "Visa"),
                "number": int(payment.get("cardNumber", "0").replace(" ", "")),
                "expiryDate": payment.get("expiryDate", ""),
                "cvc": int(payment.get("cvc", "0")),
                "holderName": payment.get("cardHolderName", ""),
                "countryOfIssue": guest.get("countryCode", "US"),
                "issuingBank": payment.get("issuingBank", "")
            }
        }
        
        # Call Agoda booking API
        booking_response = await agoda_client.book_hotel(
            booking_details,
            customer_detail,
            payment_details
        )
        
        # Check if booking was successful
        status_code = booking_response.get("status")
        
        if status_code in ["200", 200]:
            booking_info = booking_response.get("bookingDetails", [{}])[0]
            booking_id = booking_info.get("id", "")
            itinerary_id = booking_info.get("itineraryID", "")
            self_service_link = booking_info.get("selfService", "")
            
            logger.info(f"[BOOK-HOTEL] Booking successful - ID: {booking_id}")
            
            return {
                "status": "confirmed",
                "bookingId": booking_id,
                "itineraryId": itinerary_id,
                "confirmation": {
                    "hotel_name": payload.get("hotelName", "Hotel"),
                    "checkin": payload.get("checkIn"),
                    "checkout": payload.get("checkOut"),
                    "final_price": payload.get("inclusivePrice", 0),
                    "currency": payload.get("currency", "USD"),
                    "guest_name": f"{guest.get('firstName', '')} {guest.get('lastName', '')}".strip()
                },
                "selfServiceLink": self_service_link
            }
        else:
            error_msg = booking_response.get("errorMessage", {}).get("message", "Booking failed")
            logger.error(f"[BOOK-HOTEL] Booking failed: {error_msg}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=error_msg
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[BOOK-HOTEL] Booking error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Booking service unavailable"
        )
