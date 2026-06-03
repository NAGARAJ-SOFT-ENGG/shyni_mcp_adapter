"""
JSON Schema validation utility module.

Provides functions for validating requests and responses against defined schemas.
Integrates jsonschema validation with error handling and error code mapping.
"""

import logging
from typing import Any, Dict, Optional, Tuple

from jsonschema import Draft7Validator, ValidationError

from app.schema import get_schema

logger = logging.getLogger(__name__)


class SchemaValidationError(Exception):
    """Custom exception for schema validation errors."""
    
    def __init__(self, error_code: str, message: str, status_code: int = 400):
        """Initialize validation error.
        
        Args:
            error_code: Error code from schema
            message: Error message
            status_code: HTTP status code
        """
        self.error_code = error_code
        self.message = message
        self.status_code = status_code
        super().__init__(message)


def get_error_code_and_status(
    schema: Dict[str, Any],
    error_code: str,
    default_status: int = 400
) -> Tuple[str, int]:
    """Get error code and HTTP status from schema definition.
    
    Args:
        schema: Schema dictionary
        error_code: Error code to look up
        default_status: Default status if not found in schema
        
    Returns:
        Tuple of (error_code, status_code)
    """
    if "errorCodes" in schema and error_code in schema["errorCodes"]:
        status_code = schema["errorCodes"][error_code]
        return error_code, status_code
    
    return error_code, default_status


def validate_request(
    tool_name: str,
    payload: Dict[str, Any]
) -> Tuple[bool, Optional[SchemaValidationError]]:
    """Validate a request payload against tool-specific schema.
    
    Args:
        tool_name: Name of the tool (booking, availability, fare)
        payload: Request payload to validate
        
    Returns:
        Tuple of (is_valid, error or None)
        
    Raises:
        SchemaValidationError: If validation fails
    """
    logger.info(f"[VALIDATION] Validating {tool_name} request")
    
    # Map tool names to schema names
    schema_map = {
        "get_cab_availability": "availability_schema",
        "get_estimated_fare": "fare_schema",
        "book_outstation_drop": "booking_schema",
        "search_hotels": "booking_search_schema",
        "get_hotel_details": "hotel_details_schema",
        "confirm_booking": "booking_confirm_schema",
    }
    
    # Special case for generic tool call
    if tool_name == "tool_call":
        schema_name = "tool_call_schema"
    else:
        schema_name = schema_map.get(tool_name)
    
    if not schema_name:
        logger.warning(f"[VALIDATION] No schema defined for tool: {tool_name}")
        return True, None
    
    try:
        schema = get_schema(schema_name)
        
        # Get request schema definition
        if "definitions" in schema and "request" in schema["definitions"]:
            request_schema = schema["definitions"]["request"]
        else:
            request_schema = schema
        
        # For tool-specific schemas, strip the 'tool' field from payload
        # Only the generic tool_call_schema expects the 'tool' field
        validation_payload = payload.copy()
        if tool_name != "tool_call" and "tool" in validation_payload:
            validation_payload.pop("tool")
        
        # Create validator
        validator = Draft7Validator(request_schema)
        
        # Validate
        errors = list(validator.iter_errors(validation_payload))
        
        if errors:
            error = errors[0]  # Get first error
            logger.error(f"[VALIDATION] Request validation failed: {error.message}")
            
            # Map validation error to error code
            if "required" in str(error.validator):
                error_code = "MISSING_REQUIRED_FIELD"
            elif "pattern" in str(error.validator):
                error_code = "INVALID_FORMAT"
            elif "enum" in str(error.validator):
                error_code = "INVALID_VALUE"
            elif "const" in str(error.validator):
                error_code = "CONFIRMATION_REQUIRED"
            elif "type" in str(error.validator):
                error_code = "INVALID_PAYLOAD"
            else:
                error_code = "INVALID_REQUEST"
            
            error_code, status_code = get_error_code_and_status(
                schema, error_code, default_status=400
            )
            
            validation_error = SchemaValidationError(
                error_code=error_code,
                message=f"{error_code}: {error.message}",
                status_code=status_code
            )
            return False, validation_error
        
        logger.info(f"[VALIDATION] ✓ {tool_name} request validated successfully")
        return True, None
        
    except KeyError as e:
        logger.warning(f"[VALIDATION] Schema not found: {e}")
        return True, None
    except Exception as e:
        logger.error(f"[VALIDATION] Validation error: {e}", exc_info=True)
        validation_error = SchemaValidationError(
            error_code="VALIDATION_ERROR",
            message=f"Validation error: {str(e)}",
            status_code=500
        )
        return False, validation_error


def validate_response(
    tool_name: str,
    response: Dict[str, Any]
) -> Tuple[bool, Optional[SchemaValidationError]]:
    """Validate a response payload against tool-specific schema.
    
    Args:
        tool_name: Name of the tool (booking, availability, fare)
        response: Response payload to validate
        
    Returns:
        Tuple of (is_valid, error or None)
    """
    logger.info(f"[VALIDATION] Validating {tool_name} response")
    
    # Map tool names to schema names
    schema_map = {
        "get_cab_availability": "availability_schema",
        "get_estimated_fare": "fare_schema",
        "book_outstation_drop": "booking_schema",
    }
    
    schema_name = schema_map.get(tool_name)
    
    if not schema_name:
        logger.warning(f"[VALIDATION] No schema defined for tool: {tool_name}")
        return True, None
    
    try:
        schema = get_schema(schema_name)
        
        # Get response schema definition
        if "definitions" in schema and "response" in schema["definitions"]:
            response_schema = schema["definitions"]["response"]
        else:
            response_schema = schema
        
        # Create validator
        validator = Draft7Validator(response_schema)
        
        # Validate
        errors = list(validator.iter_errors(response))
        
        if errors:
            error = errors[0]
            logger.error(f"[VALIDATION] Response validation failed: {error.message}")
            
            error_code = "INVALID_RESPONSE_FORMAT"
            error_code, status_code = get_error_code_and_status(
                schema, error_code, default_status=500
            )
            
            validation_error = SchemaValidationError(
                error_code=error_code,
                message=f"{error_code}: {error.message}",
                status_code=status_code
            )
            return False, validation_error
        
        logger.info(f"[VALIDATION] ✓ {tool_name} response validated successfully")
        return True, None
        
    except KeyError as e:
        logger.warning(f"[VALIDATION] Schema not found: {e}")
        return True, None
    except Exception as e:
        logger.error(f"[VALIDATION] Response validation error: {e}", exc_info=True)
        validation_error = SchemaValidationError(
            error_code="RESPONSE_VALIDATION_ERROR",
            message=f"Response validation error: {str(e)}",
            status_code=500
        )
        return False, validation_error
