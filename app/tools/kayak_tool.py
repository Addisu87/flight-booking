import logfire
from pydantic_ai.tools import Tool
from app.models.flight_models import FlightSearchRequest


@Tool
def kayak_search_tool(search_request: FlightSearchRequest) -> str:
    base_url = f"https://www.kayak.com/flights/{search_request.origin}-{search_request.destination}/{search_request.departure_date}"
    
    if search_request.return_date:
        base_url += f"/{search_request.return_date}"
    
    base_url += "?sort=bestflight_a&currency=USD"
    
    logfire.debug(
        "Generated Kayak URL", 
        url=base_url, 
        origin=search_request.origin,
        destination=search_request.destination,
        departure_date=str(search_request.departure_date),
    )
    
    return base_url