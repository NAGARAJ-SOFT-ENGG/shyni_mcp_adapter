"""
Tool router module.

Dynamically routes tool calls to appropriate handlers based on tool name.
Implements tool registry pattern for scalable architecture.

Flow:
  tool_call JSON → /api/tool-call → VALIDATION → execute_tool → TOOL_MAP → real function
"""

import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, status

from app.middleware.validator import validate_request, SchemaValidationError
from app.tools.registry import TOOL_MAP

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["Tools"])


def infer_tool_from_payload(payload: Dict[str, Any]) -> Optional[str]:
    """Intelligently infer tool type from request payload structure.
    
    Analyzes payload fields to determine which tool is being called when
    the 'tool' field is not explicitly provided.
    
    Detection rules (in priority order):
    1. Hotel Search: location + checkin + checkout + adults
    2. Hotel Booking Precheck: searchId + propertyId + roomId
    3. Hotel Booking: bookingToken + propertyId + roomId
    4. Cab Availability: pickup + drop
    5. Fare Estimation: pickup + drop + passengers
    6. Outstation Booking: pickup + drop + bookingId
    
    Args:
        payload: Request payload to analyze
        
    Returns:
        Tool name if inferred, None otherwise
    """
    payload_keys = set(payload.keys())
    
    # Hotel Search: location + checkin + checkout + adults
    if {"location", "checkin", "checkout", "adults"}.issubset(payload_keys):
        logger.info("→ Inferred tool: search_hotels (from location, checkin, checkout, adults)")
        return "search_hotels"
    
    # Hotel Booking Precheck: searchId + propertyId + roomId
    if {"searchId", "propertyId", "roomId"}.issubset(payload_keys) and "bookingToken" not in payload_keys:
        logger.info("→ Inferred tool: precheck_booking (from searchId, propertyId, roomId)")
        return "precheck_booking"
    
    # Hotel Booking: bookingToken + propertyId + roomId
    if {"bookingToken", "propertyId", "roomId"}.issubset(payload_keys):
        logger.info("→ Inferred tool: book_hotel (from bookingToken, propertyId, roomId)")
        return "book_hotel"
    
    # Outstation Booking: pickup + drop + bookingId
    if {"pickup", "drop", "bookingId"}.issubset(payload_keys):
        logger.info("→ Inferred tool: book_outstation_drop (from pickup, drop, bookingId)")
        return "book_outstation_drop"
    
    # Fare Estimation: pickup + drop + passengers
    if {"pickup", "drop", "passengers"}.issubset(payload_keys):
        logger.info("→ Inferred tool: get_estimated_fare (from pickup, drop, passengers)")
        return "get_estimated_fare"
    
    # Cab Availability: pickup + drop
    if {"pickup", "drop"}.issubset(payload_keys):
        logger.info("→ Inferred tool: get_cab_availability (from pickup, drop)")
        return "get_cab_availability"
    
    return None


async def execute_tool(tool_name: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """Execute a registered tool by name.
    
    Core switchboard that routes to appropriate tool handler based on registry.
    Includes request validation against JSON schemas before execution.
    
    Flow:
      1. Validate request payload against schema
      2. Check if tool exists in TOOL_MAP
      3. Call tool with payload
      4. Return result or raise error
    
    Args:
        tool_name: Name of the tool to execute
        payload: Tool-specific payload data
        
    Returns:
        Dict with tool execution result
        
    Raises:
        HTTPException: If validation fails, tool not found, or execution fails
        SchemaValidationError: If request doesn't match schema
    """
    logger.info(f"→ Tool requested: {tool_name}")
    
    # VALIDATION LAYER: Validate request against schema
    try:
        is_valid, validation_error = validate_request(tool_name, payload)
        if not is_valid:
            logger.warning(f"[VALIDATION] Request validation failed for {tool_name}: {validation_error.error_code}")
            raise HTTPException(
                status_code=validation_error.status_code,
                detail={
                    "error": True,
                    "error_code": validation_error.error_code,
                    "message": validation_error.message
                }
            )
    except SchemaValidationError as e:
        logger.error(f"[VALIDATION] Schema validation error: {e.error_code}")
        raise HTTPException(
            status_code=e.status_code,
            detail={
                "error": True,
                "error_code": e.error_code,
                "message": e.message
            }
        )
    
    # Check if tool exists
    if tool_name not in TOOL_MAP:
        logger.error(f"✗ Tool not found: {tool_name}")
        available_tools = list(TOOL_MAP.keys())
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": True,
                "error_code": "TOOL_NOT_FOUND",
                "message": f"Tool '{tool_name}' not found. Available: {available_tools}"
            }
        )
    
    try:
        logger.info(f"→ Executing tool: {tool_name}")
        tool_handler = TOOL_MAP[tool_name]
        result = await tool_handler(payload)
        logger.info(f"✓ Tool {tool_name} executed successfully")
        return result
        
    except HTTPException as e:
        # Re-raise HTTP exceptions (e.g., confirmation failure)
        logger.error(f"✗ HTTP Exception in {tool_name}: {e.detail}")
        raise
    except Exception as e:
        logger.error(f"✗ Error executing {tool_name}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": True,
                "error_code": "EXECUTION_ERROR",
                "message": f"Error executing tool '{tool_name}': {str(e)}"
            }
        )


@router.post("/tool-call")
async def tool_call(request_body: Dict[str, Any]) -> Dict[str, Any]:
    """Execute an MCP tool call.
    
    Receives tool invocation requests with payload and routes
    to appropriate tool handler. Validates requests against JSON schemas.
    
    Supports two modes:
    1. Explicit: Include "tool" field in request
    2. Auto-detect: Omit "tool" field and let system infer from payload structure
    
    Request Flow (Explicit):
    ```
    {
      "tool": "search_hotels",
      "location": "Madurai",
      "checkin": "2026-06-15",
      ...
    }
    ↓
    /api/tool-call endpoint
    ↓
    Use tool field directly
    ↓
    Execute
    ```
    
    Request Flow (Auto-detect):
    ```
    {
      "location": "Madurai",
      "checkin": "2026-06-15",
      "checkout": "2026-06-20",
      "adults": 2,
      "rooms": 1
    }
    ↓
    /api/tool-call endpoint
    ↓
    Analyze payload structure → infer tool: search_hotels
    ↓
    Execute
    ```
    
    Args:
        request_body: Tool call request containing:
            - tool: Name of the tool to execute (OPTIONAL)
            - Other fields: Tool-specific parameters
            
    Returns:
        Dict with tool execution result directly from the tool handler.
            
    Raises:
        HTTPException: If tool cannot be determined, validation fails, tool not found, or execution fails
    """
    tool_name = request_body.get("tool")
    
    # Try to infer tool if not explicitly provided
    if not tool_name:
        tool_name = infer_tool_from_payload(request_body)
        
        if not tool_name:
            logger.error("✗ Cannot determine tool from request payload")
            logger.debug(f"→ Payload keys: {list(request_body.keys())}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": True,
                    "error_code": "CANNOT_INFER_TOOL",
                    "message": "Cannot determine tool from request payload. Either provide 'tool' field or ensure payload matches a known tool signature.",
                    "payload_keys": list(request_body.keys()),
                    "hint": "For hotel search use: location, checkin, checkout, adults"
                }
            )
        logger.info(f"→ Tool auto-detected from payload: {tool_name}")
    else:
        logger.debug(f"→ Tool explicitly specified: {tool_name}")
    
    logger.debug(f"→ Payload keys: {list(request_body.keys())}")
    
    # Execute the tool (includes validation layer)
    result = await execute_tool(tool_name, request_body)
    
    logger.info(f"✓ Tool call complete: {tool_name}")
    
    return result


def register_tool(tool_name: str, handler) -> None:
    """Register a new tool handler dynamically.
    
    Allows adding tools at runtime for extensibility.
    
    Args:
        tool_name: Name to register the tool under
        handler: Async callable that handles the tool execution
    """
    if tool_name in TOOL_MAP:
        logger.warning(f"⚠ Overwriting existing tool: {tool_name}")
    TOOL_MAP[tool_name] = handler
    logger.info(f"✓ Tool registered: {tool_name}")


def get_available_tools() -> Dict[str, str]:
    """Get list of available tools with descriptions.
    
    Returns:
        Dict mapping tool names to their docstrings
    """
    return {
        tool_name: (handler.__doc__ or "No description").split('\n')[0]
        for tool_name, handler in TOOL_MAP.items()
    }
