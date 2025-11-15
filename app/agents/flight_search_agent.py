from typing import List
from dataclasses import dataclass
from pydantic_ai import Agent, RunContext, ModelRetry

from app.models.flight_models import (
    FlightDetails,
    FlightSearchResult,
    NoFlightFound,
    FlightSearchRequest,
)
from app.tools.kayak_tool import kayak_search_tool
from app.tools.apify_browser import apify_browser_tool
# from app.tools.browserbase_tool import browserbase_tool
from app.utils.config import settings
from app.core.llm import llm_model
import logfire


@dataclass
class FlightDeps:
    search_request: FlightSearchRequest
    available_flights: List[FlightDetails]


# Flight Search Agent
flight_search_agent = Agent[FlightDeps, FlightSearchResult | NoFlightFound](
    llm_model,
    retries=settings.MAXIMUM_RETRIES,
    system_prompt="""
    You are an intelligent flight search analyst. Your role is to:
    1. Find the BEST flights matching the user's exact criteria
    2. Provide a comprehensive analysis of options
    3. Consider price, duration, stops, and timing
    4. Highlight the best value option
    5. Provide clear, actionable summary
    
    Always prioritize flights that exactly match the search criteria.
    If no flights match, provide helpful suggestions and alternatives.
    """,
    tools=[kayak_search_tool, apify_browser_tool],
)

@flight_search_agent.tool
async def get_available_flights(ctx: RunContext[FlightDeps]) -> List[FlightDetails]:
    """Get the list of available flights that were previously extracted."""
    logfire.debug("Retrieving available flights", count=len(ctx.deps.available_flights))
    return ctx.deps.available_flights


@flight_search_agent.output_validator
async def validate_flight_search(
    ctx: RunContext[FlightDeps], result: FlightSearchResult | NoFlightFound
) -> FlightSearchResult | NoFlightFound:
    """Validate that the search results match the user's request."""
    if isinstance(result, NoFlightFound):
        logfire.info(
            "No flights found for request", request=ctx.deps.search_request.model_dump()
        )

        return result

    # Validate that flights match the search criteria
    invalid_flights = []
    for i, flight in enumerate(result.flights):
        if (
            flight.origin.upper() != ctx.deps.search_request.origin.upper()
            or flight.destination.upper() != ctx.deps.search_request.destination.upper()
            or flight.date != ctx.deps.search_request.departure_date
        ):
            invalid_flights.append((i, flight.flight_number))

    if invalid_flights:
        logfire.warning(
            "Invalid flights in results",
            invalid_count=len(invalid_flights),
            invalid_flights=invalid_flights,
        )
        raise ModelRetry(
            f"Found {len(invalid_flights)} flights in result don't match search criteria."
        )

    # Calculate analytics for the result
    result.calculate_analytics()

    logfire.info(
        "Flight search completed successfully",
        total_flight=len(result.flights),
        cheapest_price=result.cheapest_flight,
    )

    return result
