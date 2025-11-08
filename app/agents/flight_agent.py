import datetime
from typing import List
from dataclasses import dataclass
from pydantic_ai import Agent, RunContext, ModelRetry

from app.models.flight_models import (
    FlightDetails, 
    FlightSearchResult, 
    NoFlightFound,
    FlightSearchRequest
)
from app.tools.kayak_tool import kayak_search_tool
from app.tools.browserbase_tool import browserbase_tool
from app.utils.config import settings
from app.core.llm import llm_model


@dataclass
class FlightDeps:
    search_request: FlightSearchRequest
    available_flights: List[FlightDetails]


# Flight Extraction Agent
flight_extraction_agent = Agent(
    llm_model,
    result_type=List[FlightDetails],
    system_prompt="""
    You are an expert at extracting flight information from web pages.
    Extract all available flight details including:
    - Airline name
    - Flight number
    - Price
    - Origin and destination airports (as 3-letter codes)
    - Departure and arrival times
    - Duration
    - Date
    - Booking URL if available
    
    Be accurate and thorough in your extraction.
    """,
)


# Flight Search Agent
flight_search_agent = Agent[FlightDeps, FlightSearchResult | NoFlightFound](
    llm_model,
    result_type=FlightSearchResult | NoFlightFound,
    retries=2,
    system_prompt="""
    You are a flight search expert. Find the best flights matching the user's criteria.
    Consider price, duration, and timing when selecting flights.
    Always return the most relevant flights first.
    Provide a clear summary of the options.
    """,
    tools=[kayak_search_tool, browserbase_tool],
)


@flight_search_agent.tool
async def get_available_flights(ctx: RunContext[FlightDeps]) -> List[FlightDetails]:
    """Get the list of available flights that were previously extracted."""
    return ctx.deps.available_flights


@flight_search_agent.result_validator
async def validate_flight_search(
    ctx: RunContext[FlightDeps], 
    result: FlightSearchResult | NoFlightFound
) -> FlightSearchResult | NoFlightFound:
    """Validate that the search results match the user's request."""
    if isinstance(result, NoFlightFound):
        return result
    
    # Validate that flights match the search criteria
    for flight in result.flights:
        if (flight.origin.upper() != ctx.deps.search_request.origin.upper() or
            flight.destination.upper() != ctx.deps.search_request.destination.upper() or
            flight.date != ctx.deps.search_request.departure_date):
            raise ModelRetry("Flights in result don't match search criteria.")
    
    return result