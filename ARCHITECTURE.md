# MCP Architecture Documentation

## System Architecture Overview

### High-Level Flow

```
┌──────────────────────────────────────────────────────────────┐
│                    LLM (AI Agent)                            │
│                                                              │
│  "Find hotels in Amsterdam and book one for me"             │
└────────────────────┬─────────────────────────────────────────┘
                     │ Tool Request
                     ↓
        ┌──────────────────────────────────────┐
        │  Tool Router (app/routes/tool_router.py)
        │                                      │
        │  • Route tool_call to handler        │
        │  • Validate request against schema   │
        │  • Return response or error          │
        └───────────────┬──────────────────────┘
                        │
        ┌───────────────┴───────────────┐
        ↓                               ↓
    ┌────────────────────────┐  ┌──────────────────────┐
    │  Cab Tools             │  │  Hotel Tools         │
    ├────────────────────────┤  ├──────────────────────┤
    │ • get_cab_availability │  │ • search_hotels      │
    │ • book_outstation_drop │  │ • get_hotel_details  │
    │ • get_estimated_fare   │  │ • confirm_booking    │
    └────────────────────────┘  └──────────────────────┘
                                          │
                    ┌─────────────────────┴──────────────────┐
                    ↓                                        ↓
        ┌─────────────────────────────┐    ┌──────────────────────────┐
        │ Booking.com API             │    │ Google Maps API          │
        │ (Primary - Sandbox)         │    │ (Fallback)               │
        │                             │    │                          │
        │ POST /accommodations/search │    │ • Nearby Search          │
        │ POST /accommodations/...    │    │ • Place Details          │
        │ POST /orders/preview        │    │ • Geocoding              │
        │ POST /orders/create         │    │                          │
        └────────────┬────────────────┘    └──────────────────────────┘
                     │
        ┌────────────▼────────────────┐
        │  BookingTransformer         │
        │  (Response Normalization)   │
        │                             │
        │  • normalize_hotel_search() │
        │  • normalize_room_avail()   │
        │  • normalize_booking()      │
        │  • handle_inventory_error() │
        └────────────┬────────────────┘
                     │
        ┌────────────▼────────────────────┐
        │  AI-Friendly Response           │
        │  • Clean JSON                   │
        │  • Semantic fields              │
        │  • No raw payloads              │
        │  • User-friendly policies       │
        └────────────┬────────────────────┘
                     │
                     ↓
        ┌──────────────────────────────────┐
        │  Back to LLM                     │
        │  "I found 42 hotels, show me..." │
        └──────────────────────────────────┘
```

## Data Flow: Booking a Hotel

### Phase 1: Search

```
LLM: "Find hotels in Amsterdam for June 15-20, 2 adults"
     ↓
Tool: search_hotels(location="Amsterdam", checkin="2026-06-15", 
                    checkout="2026-06-20", adults=2)
     ↓
Routing: → booking_search.py
     ↓
┌────────────────────────────────────────────┐
│ search_hotels Handler                      │
│                                            │
│ 1. Try Booking.com API                     │
│    POST /accommodations/search             │
│    ↓                                       │
│    Response: {"accommodations": [...]}    │
│    ↓                                       │
│    Transform via BookingTransformer        │
│                                            │
│ 2. If failed → Try Google Maps API         │
│    GET /nearbysearch                       │
│    ↓                                       │
│    Response: {"results": [...]}            │
│    ↓                                       │
│    Transform to match Booking format       │
│                                            │
│ 3. Apply filtering (budget, etc.)         │
│ 4. Sort by distance/rating                │
└────────────────────────────────────────────┘
     ↓
Response: {
  "hotels": [
    {"hotel_id": "12345", "name": "Hotel Amsterdam", ...},
    {"hotel_id": "12346", "name": "Canal House", ...}
  ],
  "total": 42,
  "source": "booking.com"
}
     ↓
LLM: "Here are the top hotels. Which one interests you?"
```

### Phase 2: Get Details

```
LLM: "Tell me about hotel 12345 and available rooms"
     ↓
Tool: get_hotel_details(hotel_id="12345", checkin="2026-06-15",
                        checkout="2026-06-20", adults=2)
     ↓
Routing: → booking_details.py
     ↓
┌──────────────────────────────────────────────────────────┐
│ get_hotel_details Handler (Multi-Step Orchestration)     │
│                                                          │
│ STEP 1: Get Availability                                 │
│ ┌────────────────────────────────────────────────────┐  │
│ │ POST /accommodations/availability                  │  │
│ │ → Response: {products: [{id, name, price, ...}]}  │  │
│ └────────────────────────────────────────────────────┘  │
│                                                          │
│ STEP 2: Get Details                                      │
│ ┌────────────────────────────────────────────────────┐  │
│ │ POST /accommodations/details                       │  │
│ │ → Response: {hotel: {name, address, policies}} │  │
│ └────────────────────────────────────────────────────┘  │
│                                                          │
│ STEP 3: Merge & Normalize                               │
│ ┌────────────────────────────────────────────────────┐  │
│ │ Transform via BookingTransformer                   │  │
│ │ • Merge availability + details                     │  │
│ │ • Extract breakfast, cancellation info             │  │
│ │ • Convert price format                             │  │
│ │ • Normalize policies                               │  │
│ └────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────┘
     ↓
Response: {
  "hotel": {
    "hotel_id": "12345",
    "name": "Hotel Amsterdam",
    "address": "...",
    "checkin_time": "15:00",
    "checkout_time": "11:00"
  },
  "rooms": [
    {
      "room_id": "12345_A_1",
      "room_name": "Deluxe Double",
      "price": 481.50,
      "currency": "EUR",
      "breakfast_included": true,
      "free_cancellation": true,
      "cancellation_deadline": "2026-06-10"
    },
    # ... more room types
  ]
}
     ↓
LLM: "Here are the available rooms. Which would you like?"
```

### Phase 3: Confirm Booking

```
LLM: "Book the Deluxe Double room. Guest: John Doe, john@example.com"
     ↓
Tool: confirm_booking(room_id="12345_A_1", guest_name="John Doe",
                      guest_email="john@example.com", 
                      checkin="2026-06-15", checkout="2026-06-20")
     ↓
Routing: → booking_confirm.py
     ↓
┌──────────────────────────────────────────────────────────────┐
│ confirm_booking Handler (Complex Orchestration)              │
│                                                              │
│ STEP 1: Preview Order (Validation)                          │
│ ┌──────────────────────────────────────────────────────┐    │
│ │ POST /orders/preview                                 │    │
│ │ {room_id, checkin, checkout, guest_name, email}    │    │
│ │ ↓                                                    │    │
│ │ Response: {                                          │    │
│ │   order_token: "abc123xyz",  ← IMPORTANT            │    │
│ │   price: 481.50,                                     │    │
│ │   cancellation_deadline: "2026-06-10"               │    │
│ │ }                                                    │    │
│ └──────────────────────────────────────────────────────┘    │
│                                                              │
│ STEP 2: Extract Token (Internal Use Only)                  │
│ ┌──────────────────────────────────────────────────────┐    │
│ │ order_token = preview_response["order_token"]       │    │
│ │ • NEVER exposed to LLM                               │    │
│ │ • NEVER logged to output                             │    │
│ │ • ONLY used internally for create call              │    │
│ └──────────────────────────────────────────────────────┘    │
│                                                              │
│ STEP 3: Create Order (Finalize)                            │
│ ┌──────────────────────────────────────────────────────┐    │
│ │ POST /orders/create                                  │    │
│ │ {order_token: "abc123xyz"}                          │    │
│ │ ↓                                                    │    │
│ │ Response: {                                          │    │
│ │   booking_reference: "BK123456789",                 │    │
│ │   status: "confirmed",                               │    │
│ │   ...                                                │    │
│ │ }                                                    │    │
│ └──────────────────────────────────────────────────────┘    │
│                                                              │
│ STEP 4: Error Recovery (If Needed)                          │
│ ┌──────────────────────────────────────────────────────┐    │
│ │ If create fails with "inventory_changed":           │    │
│ │ • Notify LLM that room is no longer available      │    │
│ │ • Suggest searching again                           │    │
│ │ • Return recoverable error (409 Conflict)          │    │
│ └──────────────────────────────────────────────────────┘    │
│                                                              │
│ STEP 5: Normalize Response                                  │
│ ┌──────────────────────────────────────────────────────┐    │
│ │ Transform via BookingTransformer                     │    │
│ │ • Remove order_token from output                     │    │
│ │ • Clean up internal fields                           │    │
│ │ • Include only necessary info                        │    │
│ └──────────────────────────────────────────────────────┘    │
└──────────────────────────────────────────────────────────────┘
     ↓
Response: {
  "booking_reference": "BK123456789",
  "status": "confirmed",
  "hotel_name": "Hotel Amsterdam",
  "room_name": "Deluxe Double",
  "final_price": 481.50,
  "currency": "EUR",
  "checkin": "2026-06-15",
  "checkout": "2026-06-20",
  "guest_name": "John Doe"
}
     ↓
LLM: "Perfect! Your booking is confirmed. Reference: BK123456789"
```

## Request/Response Validation

### Validation Layers

```
1. JSON Schema Validation (Middleware)
   ├─ Validates against schema/booking_search_schema.json
   ├─ Validates against schema/hotel_details_schema.json
   └─ Validates against schema/booking_confirm_schema.json

2. Type Checking (Python)
   ├─ Argument type hints in docstrings
   ├─ Return type hints in docstrings
   └─ Runtime validation

3. Business Logic Validation
   ├─ Date format validation (YYYY-MM-DD)
   ├─ Email format validation
   ├─ Coordinate range validation
   ├─ Required field checking
   └─ Enum validation
```

### Error Handling Flow

```
Error Occurs
    ↓
Is it validation error?
├─ YES → 400 Bad Request
│        {"error": "missing_field", "detail": "..."}
│
└─ NO → Is it auth error?
   ├─ YES → 401 Unauthorized
   │        {"error": "invalid_credentials"}
   │
   └─ NO → Is it inventory error?
      ├─ YES → 409 Conflict
      │        {"error": "inventory_changed", "recoverable": true}
      │
      └─ NO → Is it API error?
         ├─ YES → 502 Bad Gateway
         │        {"error": "upstream_api_error"}
         │
         └─ NO → 503 Service Unavailable
                 {"error": "service_down"}
```

## File Organization

```
app/
│
├── main.py                          # FastAPI app initialization
├── config.py                        # Environment configuration
│
├── routes/
│   └── tool_router.py              # Main request handler
│
├── tools/
│   ├── registry.py                 # Tool dispatch mapping
│   │
│   ├── [Existing Tools]
│   ├── availability.py             # Cab availability
│   ├── booking.py                  # Cab booking
│   └── fare.py                     # Fare estimation
│   │
│   ├── [Hotel Tools - Google]
│   ├── hotels.py                   # Google Maps fallback
│   │
│   ├── [Hotel Tools - Booking.com]
│   ├── booking_client.py           # API client (core)
│   ├── booking_transformers.py     # Response normalization
│   ├── booking_search.py           # search_hotels tool
│   ├── booking_details.py          # get_hotel_details tool
│   └── booking_confirm.py          # confirm_booking tool
│
├── schema/
│   ├── __init__.py                 # Schema loader
│   ├── tool_call_schema.json       # Tool call validation
│   ├── availability_schema.json    # Cab availability
│   ├── fare_schema.json            # Fare estimation
│   ├── booking_schema.json         # Cab booking
│   ├── booking_search_schema.json  # Hotel search
│   ├── hotel_details_schema.json   # Hotel details
│   └── booking_confirm_schema.json # Booking confirmation
│
├── middleware/
│   ├── __init__.py
│   ├── confirmation.py             # Request confirmation
│   └── validator.py                # Schema validation
│
└── __init__.py
```

## Integration Points

### 1. Tool Router Entry Point

**File**: `app/routes/tool_router.py`

```python
@app.post("/tool_call")
async def handle_tool_call(request: dict):
    tool_name = request.get("tool")
    
    # Validate against schema
    await validator.validate_request(tool_name, request)
    
    # Get handler from registry
    handler = registry.TOOL_MAP.get(tool_name)
    
    # Execute
    result = await handler(request)
    
    return result
```

### 2. Tool Registration

**File**: `app/tools/registry.py`

```python
TOOL_MAP = {
    # Existing tools
    "get_cab_availability": get_cab_availability,
    "book_outstation_drop": book_outstation_drop,
    "get_estimated_fare": get_estimated_fare,
    
    # New hotel tools
    "search_hotels": search_hotels,
    "get_hotel_details": get_hotel_details,
    "confirm_booking": confirm_booking,
}
```

### 3. Schema Mapping

**File**: `app/middleware/validator.py`

```python
schema_map = {
    "search_hotels": "booking_search_schema",
    "get_hotel_details": "hotel_details_schema",
    "confirm_booking": "booking_confirm_schema",
}
```

## Response Transformation Pipeline

### Search Result Transformation

```
Booking.com Raw Response
│
├─ accommodations[0]
│  ├─ id: 12345
│  ├─ name: "Hotel Amsterdam"
│  ├─ price:
│  │  ├─ total: 481.50
│  │  ├─ nights: 5
│  │  └─ currency: "EUR"
│  ├─ review:
│  │  └─ review_score: 9.0  (0-10 scale)
│  └─ [many other fields...]
│
└─ (normalize via BookingTransformer)
   ↓
Normalized Response
│
└─ hotels[0]
   ├─ hotel_id: "12345"
   ├─ name: "Hotel Amsterdam"
   ├─ price_per_night: 96.30  (calculated)
   ├─ currency: "EUR"
   ├─ review_score: 4.5  (converted to 0-5 scale)
   └─ [clean fields only]
```

## Logging Instrumentation

Each tool logs orchestration steps with prefixes:

```
[SEARCH-HOTELS] Attempting Booking.com search (primary)...
[BOOKING] POST https://demandapi-sandbox.booking.com/3.2/accommodations/search
[BOOKING] Response Status: 200
[BOOKING-TRANSFORMER] Normalizing 42 hotels
[SEARCH-HOTELS] ✓ Booking.com: Found 42 hotels

[HOTEL-DETAILS] Step 1/2: Fetching availability...
[BOOKING] POST https://demandapi-sandbox.booking.com/3.2/accommodations/availability
[HOTEL-DETAILS] Step 2/2: Fetching hotel details...
[BOOKING] POST https://demandapi-sandbox.booking.com/3.2/accommodations/details
[HOTEL-DETAILS] Merging availability and details...

[CONFIRM-BOOKING] Step 1/2: Previewing order...
[BOOKING] POST https://demandapi-sandbox.booking.com/3.2/orders/preview
[CONFIRM-BOOKING] Order token received (not exposed to LLM)
[CONFIRM-BOOKING] Step 2/2: Creating booking...
[BOOKING] POST https://demandapi-sandbox.booking.com/3.2/orders/create
[CONFIRM-BOOKING] ✓ Booking confirmed: BK123456789
```

## Configuration Management

```
Environment (.env)
│
├─ BOOKING_API_TOKEN          → BookingAPIClient.__init__()
├─ BOOKING_AFFILIATE_ID       → BookingAPIClient._get_headers()
├─ GOOGLE_MAPS_API_KEY        → Google Places API
│
└─ settings (config.py)
   ├─ app/tools/booking_client.py
   ├─ app/tools/hotels.py (Google fallback)
   └─ app/middleware/validator.py
```

## Performance Characteristics

### Response Times

```
search_hotels:
  ├─ Booking.com primary: ~2-3 seconds
  ├─ Google Maps fallback: ~1-2 seconds
  └─ P99 with retries: ~5 seconds

get_hotel_details:
  ├─ Step 1 (availability): ~1-2 seconds
  ├─ Step 2 (details): ~1 second
  ├─ Merge/normalize: ~100ms
  └─ Total: ~2-3 seconds

confirm_booking:
  ├─ Preview: ~1-2 seconds
  ├─ Create: ~2-3 seconds
  ├─ Normalize: ~100ms
  └─ Total: ~3-5 seconds
```

### Scalability

- Booking.com API rate limits: ~100 req/sec
- Google Maps API rate limits: ~1000 req/sec
- Concurrent requests: Limited by connection pool
- Timeout per request: 30 seconds

---

This architecture provides a clean abstraction layer for hotel booking while maintaining full visibility and control through comprehensive logging and error handling.
