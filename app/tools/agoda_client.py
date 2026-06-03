"""
Agoda API Client Module

Handles authentication, requests, and low-level API interactions with
Agoda JSON Search/Booking API.

Supports both real API calls and mock responses for development.
Mock/Real switching is controlled via IS_MOCK_AGODA_API environment variable.
"""

import logging
import json
import asyncio
from typing import Any, Dict, Optional, List
from datetime import datetime, timedelta
import hashlib
import hmac
import uuid

import httpx
from fastapi import HTTPException, status

from app.config import settings

logger = logging.getLogger(__name__)

# Agoda API Base URL
AGODA_API_BASE = settings.AGODA_API_BASE or "https://api.agoda.com"

# Timeout settings
REQUEST_TIMEOUT = 30
RETRY_ATTEMPTS = 2
RETRY_DELAY = 1


class AgodaAPIClient:
    """
    Agoda JSON Search/Booking API Client.
    
    Handles all communication with Agoda API.
    Supports mock responses for development when IS_MOCK_AGODA_API=true.
    
    Provides methods for:
    - Hotel search
    - Precheck booking availability
    - Hotel booking
    - Booking confirmation
    """
    
    def __init__(self, api_key: Optional[str] = None, api_secret: Optional[str] = None):
        """
        Initialize Agoda API Client.
        
        Args:
            api_key: Agoda API key (from environment if not provided)
            api_secret: Agoda API secret (from environment if not provided)
        """
        self.api_key = api_key or settings.AGODA_API_KEY
        self.api_secret = api_secret or settings.AGODA_API_SECRET
        self.base_url = AGODA_API_BASE
        self.use_mock = settings.IS_MOCK_AGODA_API
        
        if self.use_mock:
            logger.info("[AGODA] Using MOCK API responses")
        else:
            if not self.api_key or not self.api_secret:
                logger.warning("[AGODA] Real API selected but credentials not configured")
                logger.info("[AGODA] Falling back to mock mode")
                self.use_mock = True
    
    def _get_headers(self) -> Dict[str, str]:
        """Get request headers for Agoda API."""
        return {
            "Content-Type": "application/json",
            "X-API-Key": self.api_key or "mock",
        }
    
    async def _make_request(
        self,
        endpoint: str,
        payload: Dict[str, Any],
        retry: int = 0
    ) -> Dict[str, Any]:
        """
        Make authenticated request to Agoda API.
        
        Args:
            endpoint: API endpoint path
            payload: Request payload
            retry: Current retry attempt number
            
        Returns:
            API response as dictionary
            
        Raises:
            HTTPException: If request fails after retries
        """
        if self.use_mock:
            logger.info(f"[AGODA] Mock request to {endpoint}")
            return self._mock_request(endpoint, payload)
        
        try:
            url = f"{self.base_url}{endpoint}"
            async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
                response = await client.post(
                    url,
                    json=payload,
                    headers=self._get_headers()
                )
                
                if response.status_code == 200:
                    return response.json()
                elif response.status_code >= 500 and retry < RETRY_ATTEMPTS:
                    logger.warning(f"[AGODA] Server error, retrying... (attempt {retry + 1})")
                    await asyncio.sleep(RETRY_DELAY)
                    return await self._make_request(endpoint, payload, retry + 1)
                else:
                    error_data = response.json() if response.text else {}
                    logger.error(f"[AGODA] API Error: {response.status_code}")
                    raise HTTPException(
                        status_code=response.status_code,
                        detail=error_data.get("message", "Agoda API error")
                    )
                    
        except httpx.RequestError as e:
            logger.error(f"[AGODA] Request failed: {str(e)}")
            if retry < RETRY_ATTEMPTS:
                await asyncio.sleep(RETRY_DELAY)
                return await self._make_request(endpoint, payload, retry + 1)
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Agoda API unavailable"
            )
    
    def _mock_request(self, endpoint: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate mock Agoda API responses.
        
        Args:
            endpoint: API endpoint being called
            payload: Request payload
            
        Returns:
            Mock response matching Agoda API format
        """
        if "search" in endpoint.lower():
            return self._mock_search_response(payload)
        elif "precheck" in endpoint.lower():
            return self._mock_precheck_response(payload)
        elif "book" in endpoint.lower():
            return self._mock_booking_response(payload)
        else:
            return {"status": 200, "message": "Mock response"}
    
    def _mock_search_response(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate mock hotel search response with Madurai hotels.
        
        Returns hotels near Madurai with realistic pricing and amenities.
        """
        criteria = payload.get("criteria", {})
        search_id = int(datetime.now().timestamp() * 1000000)
        
        # Mock Madurai hotels database
        madurai_hotels = [
            {
                "propertyId": 12157,
                "propertyName": "Medhufushi Island Resort",
                "translatedPropertyName": "Medhufushi Island Resort",
                "address": "Near Madurai, Tamil Nadu",
                "rating": 4.5,
                "roomId": 3134583,
                "blockId": "MDZlNDc0NTUtMTU2My05MmY3LWQwNjUtYzM3MWY3YjkyZDBjOjMzMg==",
                "roomName": "Beach Villa",
                "remainingRooms": 38,
                "freeWifi": False,
                "freeBreakfast": True,
                "freeCancellation": True,
                "price": {
                    "currency": "INR",
                    "exclusive": 6500,
                    "inclusive": 7896,
                    "tax": 1140,
                    "fees": 256
                }
            },
            {
                "propertyId": 12158,
                "propertyName": "Madurai Palace Hotel",
                "translatedPropertyName": "Madurai Palace Hotel",
                "address": "Meenakshi Temple Road, Madurai",
                "rating": 4.2,
                "roomId": 3134584,
                "blockId": "MDZlNDc0NTUtMTU2My05MmY3LWQwNjUtYzM3MWY3YjkyZDBjOjMzMw==",
                "roomName": "Deluxe Room",
                "remainingRooms": 25,
                "freeWifi": True,
                "freeBreakfast": True,
                "freeCancellation": False,
                "price": {
                    "currency": "INR",
                    "exclusive": 5500,
                    "inclusive": 6848,
                    "tax": 970,
                    "fees": 378
                }
            },
            {
                "propertyId": 12159,
                "propertyName": "Taj Garden Hotel",
                "translatedPropertyName": "Taj Garden Hotel",
                "address": "Azhagar Koil Road, Madurai",
                "rating": 4.0,
                "roomId": 3134585,
                "blockId": "MDZlNDc0NTUtMTU2My05MmY3LWQwNjUtYzM3MWY3YjkyZDBjOjMzNA==",
                "roomName": "Standard Room",
                "remainingRooms": 45,
                "freeWifi": True,
                "freeBreakfast": False,
                "freeCancellation": True,
                "price": {
                    "currency": "INR",
                    "exclusive": 4500,
                    "inclusive": 5810,
                    "tax": 828,
                    "fees": 482
                }
            },
            {
                "propertyId": 12160,
                "propertyName": "Madurai Grand Resort",
                "translatedPropertyName": "Madurai Grand Resort",
                "address": "Bypass Road, Madurai",
                "rating": 4.6,
                "roomId": 3134586,
                "blockId": "MDZlNDc0NTUtMTU2My05MmY3LWQwNjUtYzM3MWY3YjkyZDBjOjMzNQ==",
                "roomName": "Premium Suite",
                "remainingRooms": 15,
                "freeWifi": True,
                "freeBreakfast": True,
                "freeCancellation": True,
                "price": {
                    "currency": "INR",
                    "exclusive": 9800,
                    "inclusive": 12450,
                    "tax": 1778,
                    "fees": 872
                }
            },
            {
                "propertyId": 12161,
                "propertyName": "Madurai Budget Inn",
                "translatedPropertyName": "Madurai Budget Inn",
                "address": "Central Market, Madurai",
                "rating": 3.8,
                "roomId": 3134587,
                "blockId": "MDZlNDc0NTUtMTU2My05MmY3LWQwNjUtYzM3MWY3YjkyZDBjOjMzNg==",
                "roomName": "Basic Room",
                "remainingRooms": 60,
                "freeWifi": False,
                "freeBreakfast": False,
                "freeCancellation": True,
                "price": {
                    "currency": "INR",
                    "exclusive": 3000,
                    "inclusive": 3735,
                    "tax": 533,
                    "fees": 202
                }
            }
        ]
        
        rooms = []
        for hotel in madurai_hotels:
            room = {
                "roomId": hotel["roomId"],
                "blockId": hotel["blockId"],
                "roomName": hotel["roomName"],
                "parentRoomName": hotel["roomName"],
                "translatedRoomName": hotel["roomName"],
                "blockIdBackup": str(uuid.uuid4()),
                "parentRoomId": hotel["roomId"],
                "ratePlanId": 617128 + madurai_hotels.index(hotel),
                "freeWifi": hotel["freeWifi"],
                "remainingRooms": hotel["remainingRooms"],
                "normalBedding": 2,
                "extraBeds": 0,
                "freeBreakfast": hotel["freeBreakfast"],
                "freeCancellation": hotel["freeCancellation"],
                "totalPayment": {
                    "exclusive": hotel["price"]["exclusive"],
                    "inclusive": hotel["price"]["inclusive"],
                    "tax": hotel["price"]["tax"],
                    "fees": hotel["price"]["fees"],
                    "taxDueSupplier": 0
                },
                "roomTypeNotGuaranteed": False,
                "paymentModel": "Merchant",
                "rate": hotel["price"],
                "perRoomPerNightRate": hotel["price"],
                "dailyRate": [
                    {
                        "date": criteria.get("checkIn", "2024-05-30"),
                        "exclusive": hotel["price"]["exclusive"],
                        "inclusive": hotel["price"]["inclusive"],
                        "tax": hotel["price"]["tax"],
                        "fees": hotel["price"]["fees"],
                        "method": "PN"
                    }
                ],
                "promotionDetail": {
                    "promotionId": 196413638 + madurai_hotels.index(hotel),
                    "codeEligible": False,
                    "description": f"Limited Time Offer on {hotel['roomName']}",
                    "savingAmount": hotel["price"]["exclusive"] * 0.15
                },
                "surcharges": [
                    {
                        "id": 278,
                        "method": "PB",
                        "charge": "Mandatory",
                        "margin": "n",
                        "name": "Local Tax",
                        "rate": {
                            "currency": "USD",
                            "exclusive": 2.0,
                            "inclusive": 2.5,
                            "tax": 0.4,
                            "fees": 0.1
                        }
                    }
                ],
                "taxBreakdown": [
                    {
                        "id": "1",
                        "typeValue": "Tax",
                        "taxDescription": "Sales tax",
                        "translatedTaxDescription": "Sales tax",
                        "method": "PRPN",
                        "currency": "USD",
                        "base": "N",
                        "taxable": "N",
                        "percent": 16,
                        "amount": hotel["price"]["tax"]
                    }
                ],
                "cancellationPolicy": {
                    "code": "1D1N_1N",
                    "cancellationText": "Free cancellation until check-in date",
                    "translatedCancellationText": "Free cancellation until check-in date",
                    "parameter": [
                        {"days": 1, "charge": "N", "value": 0}
                    ]
                },
                "benefits": [
                    {"id": 1, "benefitName": "Breakfast", "translatedBenefitName": "Breakfast"},
                    {"id": 95, "benefitName": "Free WiFi", "translatedBenefitName": "Free WiFi"},
                    {"id": 34, "benefitName": "Express check-in", "translatedBenefitName": "Express check-in"}
                ]
            }
            rooms.append(room)
        
        return {
            "searchId": search_id,
            "properties": [
                {
                    "propertyId": hotel["propertyId"],
                    "propertyName": hotel["propertyName"],
                    "translatedPropertyName": hotel["translatedPropertyName"],
                    "propertyUtcOffset": "+05:30",
                    "address": hotel["address"],
                    "rating": hotel["rating"],
                    "rooms": [rooms[madurai_hotels.index(hotel)]]
                }
                for hotel in madurai_hotels
            ]
        }
    
    def _mock_precheck_response(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Generate mock precheck response."""
        return {
            "status": 200,
            "errorList": []
        }
    
    def _mock_booking_response(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Generate mock booking response."""
        booking_id = int(datetime.now().timestamp() * 100) % 100000000
        itinerary_id = booking_id + 10000000
        
        return {
            "status": "200",
            "bookingDetails": [
                {
                    "id": booking_id,
                    "itineraryID": itinerary_id,
                    "selfService": f"https://www.agoda.com/account/editbooking.html?bookingId={booking_id}",
                    "processing": False
                }
            ]
        }
    
    async def search_hotels(self, criteria: Dict[str, Any]) -> Dict[str, Any]:
        """
        Search for hotels using Agoda API.
        
        Args:
            criteria: Search criteria containing:
                - propertyIds (optional): List of property IDs
                - checkIn: Check-in date (YYYY-MM-DD)
                - checkOut: Check-out date (YYYY-MM-DD)
                - rooms: Number of rooms
                - adults: Number of adults
                - children: Number of children
                - language: Language code (e.g., "en-us")
                - currency: Currency code (e.g., "INR")
                - userCountry: User's country code
        
        Returns:
            Search response with available hotels and rooms
        """
        payload = {
            "waitTime": 60,
            "criteria": criteria,
            "features": {
                "ratesPerProperty": 25,
                "extra": [
                    "content",
                    "surchargeDetail",
                    "CancellationDetail",
                    "BenefitDetail",
                    "dailyRate",
                    "taxDetail",
                    "rateDetail",
                    "promotionDetail"
                ]
            }
        }
        
        return await self._make_request("/demand/v2/search", payload)
    
    async def precheck_booking(self, precheck_details: Dict[str, Any]) -> Dict[str, Any]:
        """
        Precheck booking availability and rates.
        
        Args:
            precheck_details: Precheck details containing search info and room selection
        
        Returns:
            Precheck response indicating availability
        """
        payload = {
            "precheckDetails": precheck_details
        }
        
        return await self._make_request("/demand/v2/precheck", payload)
    
    async def book_hotel(self, booking_details: Dict[str, Any], customer_detail: Dict[str, Any], payment_details: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create hotel booking via Agoda.
        
        Args:
            booking_details: Booking details with property and room info
            customer_detail: Customer information
            payment_details: Payment information
        
        Returns:
            Booking response with confirmation details
        """
        payload = {
            "waitTime": 120,
            "bookingDetails": booking_details,
            "customerDetail": customer_detail,
            "paymentDetails": payment_details
        }
        
        return await self._make_request("/demand/v2/book", payload)


# Global client instance
_agoda_client: Optional[AgodaAPIClient] = None


def get_agoda_client() -> AgodaAPIClient:
    """Get or create singleton Agoda API client."""
    global _agoda_client
    if _agoda_client is None:
        _agoda_client = AgodaAPIClient()
    return _agoda_client
