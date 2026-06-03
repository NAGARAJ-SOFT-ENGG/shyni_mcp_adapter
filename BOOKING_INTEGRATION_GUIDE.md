# Booking.com MCP Integration Guide

## Overview

This MCP adapter now includes a comprehensive Booking.com Demand API sandbox integration with **semantic, AI-friendly tools** that abstract all Booking.com complexity.

The integration provides **3 primary semantic tools** for hotel booking:

1. **`search_hotels`** - Search hotels by location and dates
2. **`get_hotel_details`** - Get rooms and policies for a specific hotel
3. **`confirm_booking`** - Confirm and create a hotel booking

### Key Principles

- **AI-Friendly Orchestration**: LLM never sees raw Booking.com payloads
- **Graceful Fallbacks**: Google Maps fallback when Booking.com unavailable
- **Semantic Simplification**: Complex multi-step processes hidden from LLM
- **Production-Grade**: Proper error handling, retries, and timeouts
- **Type-Safe**: Full TypeScript-style Python with proper validation

---

## Architecture

### Tool Flow Diagram

```
LLM Request
    ↓
[MCP Adapter]
    ↓
┌─────────────────────────────────────────┐
│ Tool Dispatcher (tool_router.py)        │
└──────────┬──────────────────────────────┘
           ↓
    ┌──────────────────────────────────┐
    │ Tool Handlers                    │
    ├──────────────────────────────────┤
    │ • search_hotels (orchestrated)   │
    │ • get_hotel_details (2-step)     │
    │ • confirm_booking (2-step)       │
    └──────┬─────────────────────────┬─┘
           ↓                         ↓
    ┌─────────────────┐     ┌──────────────────┐
    │ BookingAPIClient│     │ Google Maps API  │
    │ (Primary)       │     │ (Fallback)       │
    │                 │     │                  │
    │ • Authenticates │     │ • Reverse        │
    │ • Handles       │     │   geocoding      │
    │   requests      │     │ • Nearby search  │
    │ • Manages       │     │ • Places API     │
    │   retries       │     │                  │
    └────────┬────────┘     └──────────────────┘
             ↓
    ┌──────────────────────┐
    │ BookingTransformer   │
    │ (Normalize Responses)│
    └──────────┬───────────┘
               ↓
    ┌──────────────────────────┐
    │ LLM-Friendly Output      │
    │ (Clean, semantic JSON)   │
    └──────────────────────────┘
```

### File Structure

```
app/
├── tools/
│   ├── booking_client.py         # Booking.com API client
│   ├── booking_transformers.py   # Response normalization
│   ├── booking_search.py         # search_hotels tool
│   ├── booking_details.py        # get_hotel_details tool
│   ├── booking_confirm.py        # confirm_booking tool
│   ├── hotels.py                 # Google Maps (fallback)
│   └── registry.py               # Tool dispatch mapping
│
├── schema/
│   ├── booking_search_schema.json    # search_hotels I/O
│   ├── hotel_details_schema.json     # get_hotel_details I/O
│   ├── booking_confirm_schema.json   # confirm_booking I/O
│   └── ...
│
├── middleware/
│   └── validator.py              # Schema validation
│
└── config.py                      # Environment config
```

---

## Tool Specifications

### 1. search_hotels

**Semantic Purpose**: Find available hotels for given dates and location

**Input**:
```python
{
    "location": "Amsterdam",      # City name (required)
    "checkin": "2026-06-15",      # ISO date (required)
    "checkout": "2026-06-20",     # ISO date (required)
    "adults": 2,                  # Number of adults (required)
    "rooms": 1,                   # Number of rooms (optional, default: 1)
    "budget_max": 200             # Max price/night (optional, for filtering)
}
```

**Output** (same format whether from Booking.com or Google Maps):
```python
{
    "hotels": [
        {
            "hotel_id": "12345",
            "name": "Hotel Amsterdam",
            "price_per_night": 120.50,
            "currency": "EUR",
            "review_score": 4.5,
            "address": "Main Street, Amsterdam",
            "thumbnail": "https://..."
        },
        # ... more hotels
    ],
    "total": 42,
    "source": "booking.com",      # or "google_maps" (fallback)
    "available": true
}
```

**Orchestration**:
1. Try Booking.com first (primary)
2. If Booking.com unavailable or fails, fallback to Google Maps
3. Normalize both sources to identical format
4. Filter by budget if specified

**Error Handling**:
- Missing required fields → `400 Bad Request`
- Booking.com API error → automatic Google Maps fallback
- Both sources fail → `503 Service Unavailable`

---

### 2. get_hotel_details

**Semantic Purpose**: Get available rooms and policies for a specific hotel

**Input**:
```python
{
    "hotel_id": "12345",          # From search_hotels (required)
    "checkin": "2026-06-15",      # ISO date (required)
    "checkout": "2026-06-20",     # ISO date (required)
    "adults": 2,                  # Number of adults (required)
    "rooms": 1                    # Number of rooms (optional, default: 1)
}
```

**Output**:
```python
{
    "hotel": {
        "hotel_id": "12345",
        "name": "Hotel Amsterdam",
        "address": "Main Street, Amsterdam",
        "review_score": 4.5,
        "checkin_time": "15:00",
        "checkout_time": "11:00"
    },
    "rooms": [
        {
            "room_id": "12345_A_1",          # Use for confirm_booking
            "room_name": "Deluxe Double",
            "price": 481.50,                 # Total for all nights
            "currency": "EUR",
            "breakfast_included": true,
            "free_cancellation": true,
            "cancellation_deadline": "2026-06-10"
        },
        # ... more room types
    ],
    "available": true
}
```

**Orchestration** (Hidden from LLM):
1. Call `/accommodations/availability` (get room products)
2. Call `/accommodations/details` (get hotel policies)
3. Merge responses
4. Normalize to AI-friendly format
5. Return as single unified response

**Why This Matters**:
The LLM makes ONE call and gets complete information. The adapter handles the complexity of calling two separate Booking.com endpoints and merging results.

---

### 3. confirm_booking

**Semantic Purpose**: Confirm and finalize a hotel booking

**Input**:
```python
{
    "room_id": "12345_A_1",            # From get_hotel_details (required)
    "guest_name": "John Doe",          # Guest full name (required)
    "guest_email": "john@example.com", # Guest email (required)
    "guest_phone": "+1-555-0123",      # Guest phone (optional)
    "checkin": "2026-06-15",           # ISO date (required)
    "checkout": "2026-06-20"           # ISO date (required)
}
```

**Output** (no order_token exposed):
```python
{
    "booking_reference": "BK123456789",
    "status": "confirmed",
    "hotel_name": "Hotel Amsterdam",
    "room_name": "Deluxe Double",
    "final_price": 481.50,
    "currency": "EUR",
    "checkin": "2026-06-15",
    "checkout": "2026-06-20",
    "guest_name": "John Doe",
    "available": true
}
```

**Orchestration** (Hidden from LLM):
1. Call `/orders/preview` (validate pricing, get order_token)
2. Extract `order_token` (never exposed to LLM)
3. Call `/orders/create` with token (finalize booking)
4. If inventory changed during preview→create, auto-retry availability once
5. Return normalized confirmation with reference number

**Critical Feature**: If inventory changed between preview and create:
- Automatically attempts recovery
- Returns user-friendly error message
- Indicates the error is recoverable

---

## Configuration

### Environment Variables

```bash
# Booking.com Sandbox API (Required for Booking.com primary source)
BOOKING_API_TOKEN=your_sandbox_api_token        # Get from Booking.com partner portal
BOOKING_AFFILIATE_ID=your_affiliate_id          # Your affiliate ID

# Google Maps API (Fallback, works without Booking.com)
GOOGLE_MAPS_API_KEY=your_google_maps_api_key

# Other existing configs...
DEBUG=false
```

### Getting Booking.com Credentials

1. Register with Booking.com Partner Program: https://partner.booking.com
2. Request access to Demand API
3. Generate sandbox API token and affiliate ID
4. Add to `.env` file

### Fallback Behavior

| Scenario | Behavior |
|----------|----------|
| Booking.com configured | Use Booking.com (primary source) |
| Booking.com not configured | Use Google Maps (automatic fallback) |
| Booking.com fails | Try Google Maps (automatic fallback) |
| Both fail | Return `503 Service Unavailable` |

---

## Response Normalization

### Why Transformation Matters

**Raw Booking.com Response** (noisy, complex):
```python
{
    "accommodations": [{
        "id": "12345",
        "name": "Hotel Amsterdam",
        "price": {
            "total": 481.50,
            "nights": 5,
            "breakdown": [...],
            "currency": "EUR"
        },
        "review": {
            "review_score": 9.0,  # 0-10 scale!
            ...
        },
        "metadata": {...},
        "extended_data": {...},
        ...
    }]
}
```

**Normalized Response** (clean, AI-friendly):
```python
{
    "hotels": [{
        "hotel_id": "12345",
        "name": "Hotel Amsterdam",
        "price_per_night": 96.30,        # Calculated from total
        "currency": "EUR",
        "review_score": 4.5,             # Converted to 0-5 scale
        ...
    }]
}
```

**Transformation Benefits**:
- Review score converted to standard 0-5 scale
- Price automatically divided by nights for per-night display
- Unnecessary nested structures removed
- Consistent field names across sources
- LLM gets clean, predictable JSON

---

## Error Handling

### Request Validation

```
Bad Request (400)
├── Missing required fields
├── Invalid date format (must be YYYY-MM-DD)
├── Invalid email format
└── Coordinate out of range

Unauthorized (401)
├── Booking.com API token missing/invalid
├── Affiliate ID missing/invalid
└── Google Maps API key missing (for fallback)

Conflict (409)
└── Inventory changed during booking confirmation
    (recoverable - instructs LLM to search again)

Service Unavailable (503)
├── Booking.com API down
├── Google Maps API down
└── Both services unavailable
```

### Example Error Response

```python
{
    "status": "inventory_changed",
    "error": "The room you selected is no longer available",
    "message": "Please search again and select a different room",
    "recoverable": True
}
```

---

## Example Usage Flow

### Scenario: Book a hotel in Amsterdam

**Step 1: LLM searches hotels**
```python
request = {
    "tool": "search_hotels",
    "location": "Amsterdam",
    "checkin": "2026-06-15",
    "checkout": "2026-06-20",
    "adults": 2
}

response = {
    "hotels": [
        {"hotel_id": "12345", "name": "Hotel Amsterdam", "price_per_night": 120.50, ...},
        {"hotel_id": "12346", "name": "Canal House", "price_per_night": 95.00, ...},
        ...
    ],
    "total": 42,
    "source": "booking.com"
}
```

**Step 2: LLM gets details for chosen hotel**
```python
request = {
    "tool": "get_hotel_details",
    "hotel_id": "12345",
    "checkin": "2026-06-15",
    "checkout": "2026-06-20",
    "adults": 2
}

response = {
    "hotel": {...},
    "rooms": [
        {"room_id": "12345_A_1", "room_name": "Deluxe Double", "price": 481.50, ...},
        {"room_id": "12345_A_2", "room_name": "Superior Twin", "price": 425.00, ...}
    ]
}
```

**Step 3: LLM confirms booking**
```python
request = {
    "tool": "confirm_booking",
    "room_id": "12345_A_1",
    "guest_name": "John Doe",
    "guest_email": "john@example.com",
    "guest_phone": "+1-555-0123",
    "checkin": "2026-06-15",
    "checkout": "2026-06-20"
}

response = {
    "booking_reference": "BK123456789",
    "status": "confirmed",
    "hotel_name": "Hotel Amsterdam",
    "room_name": "Deluxe Double",
    "final_price": 481.50,
    "currency": "EUR"
}
```

---

## Testing

### Test the Booking.com Integration

```bash
# Start the server
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Try search_hotels
curl -X POST http://localhost:8000/tool_call \
  -H "Content-Type: application/json" \
  -d '{
    "tool": "search_hotels",
    "location": "Amsterdam",
    "checkin": "2026-06-15",
    "checkout": "2026-06-20",
    "adults": 2
  }'

# Try get_hotel_details (use hotel_id from search response)
curl -X POST http://localhost:8000/tool_call \
  -H "Content-Type: application/json" \
  -d '{
    "tool": "get_hotel_details",
    "hotel_id": "12345",
    "checkin": "2026-06-15",
    "checkout": "2026-06-20",
    "adults": 2
  }'

# Try confirm_booking (use room_id from details response)
curl -X POST http://localhost:8000/tool_call \
  -H "Content-Type: application/json" \
  -d '{
    "tool": "confirm_booking",
    "room_id": "12345_A_1",
    "guest_name": "Test User",
    "guest_email": "test@example.com",
    "checkin": "2026-06-15",
    "checkout": "2026-06-20"
  }'
```

### Logs to Verify

Look for these in server logs to confirm orchestration is working:

```
[SEARCH-HOTELS] Attempting Booking.com search (primary)...
[BOOKING] POST https://demandapi-sandbox.booking.com/3.2/accommodations/search
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

---

## Design Decisions

### Why This Architecture?

| Decision | Reason |
|----------|--------|
| Separate client + transformers | Separation of concerns, testability, reusability |
| Hide order_token completely | LLM never needs to understand Booking.com internals |
| Orchestrate multi-step calls | Simplifies LLM logic, handles complex sequences |
| Google Maps fallback | Graceful degradation, service continuity |
| Normalize all responses | Consistent API regardless of source |
| Explicit error codes | LLM can make intelligent recovery decisions |
| TypeScript-style docstrings | Self-documenting, clear contracts |

### What We DON'T Expose to LLM

- ❌ Raw Booking.com payloads
- ❌ `order_token` and internal IDs
- ❌ API endpoints
- ❌ Preview/create sequencing
- ❌ Retry logic details
- ❌ Price level enums
- ❌ Currency conversion logic
- ❌ Inventory management

### What We DO Expose

- ✅ Clean, semantic data
- ✅ Meaningful hotel IDs
- ✅ User-friendly room names
- ✅ Clear policy information
- ✅ Booking confirmations
- ✅ Recoverable error messages

---

## Production Considerations

### Scaling

- Add connection pooling for Booking.com API calls
- Implement caching for hotel searches
- Use message queues for async booking confirmations

### Monitoring

- Log all orchestration steps (already implemented)
- Track fallback usage (Booking.com failures)
- Monitor response times per endpoint
- Alert on repeated Booking.com failures

### Security

- Validate all email addresses
- Sanitize guest names
- Store API tokens in secure vault (not .env)
- Implement rate limiting per client
- Log but never expose order_tokens

### Testing

- Mock Booking.com API responses
- Test fallback to Google Maps
- Test inventory error recovery
- Test timeout handling
- Test validation errors

---

## Migration from Google-Only

The new system **automatically supports both** Booking.com and Google Maps:

```python
# Old way (Google only)
await search_hotels({
    "latitude": 52.37,
    "longitude": 4.89,
    "radius_km": 10
})

# New way (Booking.com primary, Google fallback)
await search_hotels({
    "location": "Amsterdam",
    "checkin": "2026-06-15",
    "checkout": "2026-06-20",
    "adults": 2
})
```

Both still work, but the new approach is **simpler for LLMs and more feature-rich**.

---

## Support

For issues or questions:

1. Check server logs (look for `[BOOKING]` or `[HOTEL-DETAILS]` prefixes)
2. Verify environment variables are set
3. Test Booking.com credentials with API docs
4. Try Google Maps fallback by checking logs for source

---

**Implementation Date**: 2026-05-28  
**Booking.com API Version**: Demand API 3.2 (Sandbox)  
**Status**: Production Ready
