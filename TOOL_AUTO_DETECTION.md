# Tool Auto-Detection Guide

## Overview

The MCP Adapter now supports **intelligent tool detection** - you can omit the explicit `"tool"` field and the system will automatically infer which tool to call based on your payload structure.

## Two Modes of Operation

### Mode 1: Explicit Tool (Original)

Include the `"tool"` field explicitly:

```json
{
  "tool": "search_hotels",
  "location": "Madurai",
  "checkin": "2026-06-15",
  "checkout": "2026-06-20",
  "adults": 2,
  "rooms": 1
}
```

### Mode 2: Auto-Detection (New)

Omit the `"tool"` field and let the system infer it from your payload:

```json
{
  "location": "Madurai",
  "checkin": "2026-06-15",
  "checkout": "2026-06-20",
  "adults": 2,
  "rooms": 1
}
```

The system will automatically detect this as a **hotel search** request and call `search_hotels`.

## Tool Detection Rules

The system detects tools based on the required fields in your payload (evaluated in priority order):

### 1. Hotel Search: `search_hotels`
**Required Fields:** `location`, `checkin`, `checkout`, `adults`

```json
{
  "location": "Madurai",
  "checkin": "2026-06-15",
  "checkout": "2026-06-20",
  "adults": 2,
  "rooms": 1
}
```

### 2. Hotel Booking Precheck: `precheck_booking`
**Required Fields:** `searchId`, `propertyId`, `roomId` (without `bookingToken`)

```json
{
  "searchId": "search_abc123",
  "propertyId": 12345,
  "roomId": 456,
  "checkIn": "2026-06-15",
  "checkOut": "2026-06-20",
  "adults": 2
}
```

### 3. Hotel Booking: `book_hotel`
**Required Fields:** `bookingToken`, `propertyId`, `roomId`

```json
{
  "bookingToken": "token_xyz789",
  "propertyId": 12345,
  "roomId": 456,
  "guestEmail": "guest@example.com"
}
```

### 4. Outstation Cab Booking: `book_outstation_drop`
**Required Fields:** `pickup`, `drop`, `bookingId`

```json
{
  "pickup": "Chennai",
  "drop": "Bangalore",
  "bookingId": "booking_123",
  "passengers": 2
}
```

### 5. Fare Estimation: `get_estimated_fare`
**Required Fields:** `pickup`, `drop`, `passengers`

```json
{
  "pickup": "Chennai",
  "drop": "Bangalore",
  "passengers": 2,
  "date": "2026-06-15"
}
```

### 6. Cab Availability: `get_cab_availability`
**Required Fields:** `pickup`, `drop`

```json
{
  "pickup": "Chennai",
  "drop": "Bangalore",
  "date": "2026-06-15"
}
```

## Error Handling

If the system cannot infer the tool from your payload:

```json
{
  "error": true,
  "status_code": 400,
  "detail": {
    "error": true,
    "error_code": "CANNOT_INFER_TOOL",
    "message": "Cannot determine tool from request payload. Either provide 'tool' field or ensure payload matches a known tool signature.",
    "payload_keys": ["field1", "field2"],
    "hint": "For hotel search use: location, checkin, checkout, adults"
  }
}
```

**Solution:** Either:
1. Include the `"tool"` field explicitly, or
2. Ensure your payload has the required fields for a known tool (see detection rules above)

## Migration Guide

### For Existing Clients

Your existing requests with explicit `"tool"` fields continue to work unchanged:

```bash
curl -X POST http://localhost:8000/api/tool-call \
  -H "Content-Type: application/json" \
  -d '{
    "tool": "search_hotels",
    "location": "Madurai",
    "checkin": "2026-06-15",
    "checkout": "2026-06-20",
    "adults": 2
  }'
```

### For New Clients

You can now simplify your requests by omitting the `"tool"` field:

```bash
curl -X POST http://localhost:8000/api/tool-call \
  -H "Content-Type: application/json" \
  -d '{
    "location": "Madurai",
    "checkin": "2026-06-15",
    "checkout": "2026-06-20",
    "adults": 2
  }'
```

Both work identically. Choose whichever is more convenient for your use case.

## Implementation Details

### Detection Priority

The system uses a **priority-based matching** system. When multiple detection patterns could match, higher-priority patterns take precedence:

1. **Specific combinations** (e.g., `searchId + propertyId + roomId`) are checked before
2. **Overlapping patterns** (e.g., `pickup + drop`)

This ensures that:
- Fare requests (require `passengers`) don't accidentally match cab availability (which only needs `pickup` + `drop`)
- Hotel booking (requires `bookingToken`) doesn't match precheck (which only needs `searchId`, `propertyId`, `roomId`)

### Logging

When auto-detection occurs, the system logs the inferred tool:

```
→ Inferred tool: search_hotels (from location, checkin, checkout, adults)
→ Tool auto-detected from payload: search_hotels
```

## Backward Compatibility

✓ **100% backward compatible** - existing requests with explicit `"tool"` fields work unchanged.

✓ **Opt-in feature** - auto-detection is entirely optional. Use whichever mode fits your needs.

✓ **Consistent behavior** - requests with explicit vs. inferred tool names produce identical results.
