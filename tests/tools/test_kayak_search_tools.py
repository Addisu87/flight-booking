import pytest
from datetime import date
from app.models.flight_models import FlightSearchRequest
from app.tools.kayak_tool import kayak_search_tool


def test_one_way_flight_url(sample_search_request):
    """Test URL generation for one-way flight"""
    url = kayak_search_tool(sample_search_request)  # Remove .func
    
    expected_url = "https://www.kayak.com/flights/ADD-DXB/2025-11-21?sort=bestflight_a&currency=USD"
    assert url == expected_url
    assert "ADD-DXB" in url
    assert "2025-11-21" in url
    assert "sort=bestflight_a" in url
    assert "currency=USD" in url


def test_round_trip_flight_url(round_trip_request):
    """Test URL generation for round-trip flight"""
    url = kayak_search_tool(round_trip_request)  # Remove .func
    
    expected_url = "https://www.kayak.com/flights/SFO-JFK/2024-12-15/2024-12-20?sort=bestflight_a&currency=USD"
    assert url == expected_url
    assert "SFO-JFK" in url
    assert "2024-12-15" in url
    assert "2024-12-20" in url


def test_airport_code_validation():
    """Test that airport codes are properly formatted"""
    search_request = FlightSearchRequest(
        origin="LAX",
        destination="ORD",
        departure_date=date(2024, 10, 1),
        passengers=1,
        flight_class="economy"
    )
    
    url = kayak_search_tool(search_request)  # Remove .func
    
    assert "LAX-ORD" in url
    assert url.startswith("https://www.kayak.com/flights/")


def test_url_structure():
    """Test the overall URL structure"""
    search_request = FlightSearchRequest(
        origin="LHR",
        destination="CDG",
        departure_date=date(2024, 9, 10),
        passengers=1,
        flight_class="economy"
    )
    
    url = kayak_search_tool(search_request)  # Remove .func
    
    # Check URL components
    parts = url.split('/')
    assert parts[2] == "www.kayak.com"
    assert parts[3] == "flights"
    assert "LHR-CDG" in parts[4]
    assert "2024-09-10" in parts[5]
    assert "sort=bestflight_a" in url
    assert "currency=USD" in url


def test_special_characters_handling():
    """Test that special characters in dates are handled properly"""
    search_request = FlightSearchRequest(
        origin="DFW",
        destination="MIA", 
        departure_date=date(2024, 12, 25),  # Christmas day
        passengers=1,
        flight_class="economy"
    )
    
    url = kayak_search_tool(search_request)  # Remove .func
    
    # Should properly format the date without issues
    assert "2024-12-25" in url
    assert "DFW-MIA" in url


def test_multiple_passengers():
    """Test URL with multiple passengers"""
    search_request = FlightSearchRequest(
        origin="SEA",
        destination="DEN",
        departure_date=date(2024, 8, 15),
        passengers=4,  # Family of 4
        flight_class="economy"
    )
    
    url = kayak_search_tool(search_request)  # Remove .func
    
    # Note: Kayak URL doesn't include passenger count in the path
    # This is handled by Kayak's internal logic
    assert "SEA-DEN" in url
    assert "2024-08-15" in url


def test_same_airport():
    """Test with same origin and destination (should still work)"""
    search_request = FlightSearchRequest(
        origin="JFK",
        destination="JFK",
        departure_date=date(2024, 7, 1),
        passengers=1,
        flight_class="economy"
    )
    
    url = kayak_search_tool(search_request)  # Remove .func
    assert "JFK-JFK" in url


def test_international_airports():
    """Test with various international airport codes"""
    test_cases = [
        ("DXB", "AUH"),  # Dubai to Abu Dhabi
        ("SIN", "KUL"),  # Singapore to Kuala Lumpur
        ("FRA", "MUC"),  # Frankfurt to Munich
        ("YYZ", "YVR"),  # Toronto to Vancouver
    ]
    
    for origin, destination in test_cases:
        search_request = FlightSearchRequest(
            origin=origin,
            destination=destination,
            departure_date=date(2024, 6, 15),
            passengers=1,
            flight_class="economy"
        )
        
        url = kayak_search_tool(search_request)  # Remove .func
        assert f"{origin}-{destination}" in url


def test_tool_decorator_functionality():
    """Test that the function works correctly without @Tool decorator"""
    from unittest.mock import patch
    
    # Mock logfire to avoid side effects
    with patch('app.tools.kayak_tool.logfire'):
        search_request = FlightSearchRequest(
            origin="BOS",
            destination="DCA",
            departure_date=date(2024, 5, 20),
            passengers=1,
            flight_class="economy"
        )
        
        url = kayak_search_tool(search_request)  # Remove .func
        
        assert isinstance(url, str)
        assert url.startswith("https://")
        assert "BOS-DCA" in url