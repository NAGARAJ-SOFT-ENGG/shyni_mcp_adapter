"""
Schema package for JSON validation.

Loads and provides access to all JSON schemas for request/response validation.
"""

import json
import logging
from pathlib import Path
from typing import Dict, Any

logger = logging.getLogger(__name__)

SCHEMA_DIR = Path(__file__).parent

# Schema registry
_SCHEMAS: Dict[str, Dict[str, Any]] = {}


def load_schemas() -> Dict[str, Dict[str, Any]]:
    """Load all JSON schemas from the schema directory.
    
    Returns:
        Dictionary mapping schema names to their definitions
    """
    global _SCHEMAS
    
    if _SCHEMAS:
        return _SCHEMAS
    
    schema_files = [
        "tool_call_schema.json",
        "availability_schema.json",
        "fare_schema.json",
        "booking_schema.json",
        "booking_search_schema.json",
        "hotel_details_schema.json",
        "booking_confirm_schema.json",
    ]
    
    for schema_file in schema_files:
        schema_path = SCHEMA_DIR / schema_file
        try:
            with open(schema_path, "r") as f:
                schema_name = schema_file.replace(".json", "")
                _SCHEMAS[schema_name] = json.load(f)
                logger.info(f"✓ Loaded schema: {schema_name}")
        except FileNotFoundError:
            logger.warning(f"Schema file not found: {schema_path}")
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in schema {schema_path}: {e}")
    
    return _SCHEMAS


def get_schema(schema_name: str) -> Dict[str, Any]:
    """Get a specific schema by name.
    
    Args:
        schema_name: Name of the schema (without .json extension)
        
    Returns:
        Schema definition dictionary
        
    Raises:
        KeyError: If schema not found
    """
    schemas = load_schemas()
    if schema_name not in schemas:
        raise KeyError(f"Schema '{schema_name}' not found. Available: {list(schemas.keys())}")
    return schemas[schema_name]


def list_schemas() -> list:
    """List all available schema names.
    
    Returns:
        List of schema names
    """
    schemas = load_schemas()
    return list(schemas.keys())
