import pytest
from datetime import date
from unittest.mock import patch
from app.models.flight_models import FlightSearchRequest
import logfire


@pytest.fixture
def sample_search_request():
    """Fixture for a sample flight search request"""
    return FlightSearchRequest(
        origin="ADD",
        destination="DXB",
        departure_date=date(2025, 11, 21),
        passengers=1,
        flight_class="economy",
    )


@pytest.fixture
def round_trip_request():
    """Fixture for a round-trip flight search request"""
    return FlightSearchRequest(
        origin="SFO",
        destination="JFK",
        departure_date=date(2024, 12, 15),
        return_date=date(2024, 12, 20),
        passengers=2,
        flight_class="business",
    )


@pytest.fixture
def mock_settings():
    """Mock settings with APIFY_API_TOKEN"""
    with patch("app.tools.apify_browser.settings") as mock_settings:
        mock_settings.APIFY_API_TOKEN = "test-token-123"
        yield mock_settings


@pytest.fixture(autouse=True)
def configure_logfire():
    """Configure Logfire for tests"""
    logfire.configure(send_to_logfire=False, console=False)
