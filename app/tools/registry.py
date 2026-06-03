"""
Tool Registry Module

Core mapping of tool names to their handler functions.
This is the brain switchboard that routes tool_call JSON to real functions.

Tools:
- get_cab_availability: Cab availability lookup (Outstation)
- book_outstation_drop: Book outstation cab
- get_estimated_fare: Fare estimation
- search_hotels: Hotel search (Agoda primary, Google Maps fallback)
- precheck_booking: Verify hotel availability before booking
- book_hotel: Create hotel reservation via Agoda
"""

from typing import Dict, Callable, Any


# Tool registry will be populated below
TOOL_MAP: Dict[str, Callable] = {}


def register_tool(tool_name: str, handler: Callable) -> None:
    """Register a new tool handler.
    
    Args:
        tool_name: Name to register the tool under
        handler: Async callable that handles the tool execution
    """
    TOOL_MAP[tool_name] = handler


# Import existing tools
from app.tools.availability import get_cab_availability
from app.tools.booking import book_outstation_drop
from app.tools.fare import get_estimated_fare

# Import new Agoda tools (primary)
from app.tools.agoda_search import search_hotels
from app.tools.agoda_booking import precheck_booking, book_hotel

# Register all available tools
TOOL_MAP = {
    # Existing cab booking tools
    "get_cab_availability": get_cab_availability,
    "book_outstation_drop": book_outstation_drop,
    "get_estimated_fare": get_estimated_fare,
    
    # Hotel tools (Agoda primary with Google Maps fallback)
    "search_hotels": search_hotels,
    "precheck_booking": precheck_booking,
    "book_hotel": book_hotel,
}

