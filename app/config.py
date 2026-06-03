"""
Configuration module for MCP Adapter.

Loads environment variables and provides configuration settings
for dispatch APIs and other services.
"""

import logging
from dotenv import load_dotenv
import os

# Load environment variables from .env file
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class Settings:
    """Application settings loaded from environment variables."""

    # API Configuration
    AVAILABILITY_API_URL: str = os.getenv(
        "AVAILABILITY_API_URL",
        "https://xtlhldok3e.execute-api.ap-south-1.amazonaws.com/TDConAir/vehicle/availability"
    )
    BOOKING_API_URL: str = os.getenv(
        "BOOKING_API_URL",
        "https://vertex.lageego.com/booking/createbooking"
    )
    FARE_API_URL: str = os.getenv(
        "FARE_API_URL",
        "https://vertex.lageego.com/booking/getestimatedfare"
    )
    


    # API Keys and Credentials
    GOOGLE_MAPS_API_KEY: str = os.getenv(
        "GOOGLE_MAPS_API_KEY",
        ""
    )
    
    # Agoda API Configuration
    AGODA_API_KEY: str = os.getenv(
        "AGODA_API_KEY",
        ""
    )
    AGODA_API_SECRET: str = os.getenv(
        "AGODA_API_SECRET",
        ""
    )
    AGODA_API_BASE: str = os.getenv(
        "AGODA_API_BASE",
        "https://api.agoda.com"
    )
    
    # API Switch for Mock vs Real
    IS_MOCK_AGODA_API: bool = os.getenv(
        "IS_MOCK_AGODA_API",
        "true"
    ).lower() == "true"

    # Application Configuration
    APP_NAME: str = "MCP Adapter"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = os.getenv("DEBUG", "False").lower() == "true"

    def __init__(self):
        """Initialize settings and log configuration."""
        logger.info(f"Initializing {self.APP_NAME} v{self.APP_VERSION}")
        logger.info(f"Availability API: {self.AVAILABILITY_API_URL}")
        logger.info(f"Booking API: {self.BOOKING_API_URL}")
        logger.info(f"Fare API: {self.FARE_API_URL}")
        logger.info(f"Google Maps API: {'CONFIGURED' if self.GOOGLE_MAPS_API_KEY else 'NOT SET'}")
        logger.info(f"Agoda API: {'MOCK' if self.IS_MOCK_AGODA_API else 'REAL'} - {'CONFIGURED' if self.AGODA_API_KEY else 'NOT SET'}")



# Global settings instance
settings = Settings()
