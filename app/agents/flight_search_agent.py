from typing import List
from dataclasses import dataclass
from pydantic_ai import Agent, RunContext, ModelRetry

from app.models.flight_models import (
    FlightDetails,
    FlightSearchResult,
    NoFlightFound,
    FlightSearchRequest,
)

# from pydantic_ai.usage import UsageLimits
from app.tools.kayak_tool import kayak_search_tool
from app.tools.apify_browser import apify_browser_tool
from app.core.llm import llm_model
import logfire

# FLIGHT_SEARCH_USAGE_LIMITS = UsageLimits(
#     request_limit=5, output_tokens_limit=1000, total_tokens_limit=2000
# )

# ✅ Usage limits for extraction
# EXTRACTION_USAGE_LIMITS = UsageLimits(
#     request_limit=3, output_tokens_limit=2000, total_tokens_limit=3000
# )


@dataclass
class FlightDeps:
    """Dependencies for flight search - only the search request."""

    search_request: FlightSearchRequest


# Main Flight Search Agent - orchestrates the entire pipeline
flight_search_agent = Agent[FlightDeps, FlightSearchResult | NoFlightFound](
    llm_model,
    retries=2,
    system_prompt="""
    You are an intelligent flight search analyst. Your workflow:
    1. **ALWAYS** call `search_kayak_flights` tool first
    2. **CHECK** if the returned list is empty `[]`
    3. **IF EMPTY**: Immediately call `create_no_flights_response` tool and return its result
    4. **IF NOT EMPTY**: Analyze flights and return a `FlightSearchResult` object
    
    **NEVER** return plain text like "No flights found". 
    **NEVER** fabricate flight data.
    
    Your two valid return types are:
    - FlightSearchResult (when flights exist)
    - NoFlightFound (when empty, created via tool)
    """,
)

# Dedicated agent for extracting structured flights from HTML
flight_extraction_agent = Agent[None, List[FlightDetails]](
    llm_model,
    system_prompt="""
    Extract flight details from Kayak HTML content.
    Look for: airline, flight number, price, duration, stops, origin/destination codes,
    departure/arrival times, and booking URLs.
    
    Return a list of FlightDetails objects. If no flights found, return empty list.
    Be precise with airport codes and times.
    """,
)


@flight_search_agent.tool
async def create_no_flights_response(
    ctx: RunContext[FlightDeps], reason: str
) -> NoFlightFound:
    """
    Create a NoFlightFound response when no flights are available.
    **ALWAYS use this tool when search_kayak_flights returns an empty list.**
    """
    return NoFlightFound(
        search_request=ctx.deps.search_request,
        message=reason,
        suggestions=["Try different dates", "Check airport codes", "Try again later"],
    )


@flight_search_agent.tool
async def search_kayak_flights(ctx: RunContext[FlightDeps]) -> List[FlightDetails]:
    """
    Search Kayak for flights. Returns empty list [] if none found.
    **NEVER** return an error string - always return a list.
    """
    req = ctx.deps.search_request

    with logfire.span("search_kayak_pipeline"):
        url = kayak_search_tool(req)
        logfire.info("Generated Kayak URL", url=url)

        html_content = await apify_browser_tool(url)

        if html_content:
            logfire.info("HTML content length", length=len(html_content))

            # Look for common error/no results patterns
            if (
                "no flights" in html_content.lower()
                or "no results" in html_content.lower()
            ):
                logfire.warning("No flights pattern detected in HTML")
                return []

            # Save problematic HTML for inspection
            if len(html_content) < 10000:
                with open(
                    f"debug_scrape_{req.origin}_{req.destination}.html", "w"
                ) as f:
                    f.write(html_content)

        try:
            extraction_result = await flight_extraction_agent.run(
                f"Extract flights from HTML:\n\n{html_content[:15000]}",
                # usage=ctx.usage,
                # usage_limits=EXTRACTION_USAGE_LIMITS,
            )

            flights = extraction_result.data
            if not isinstance(flights, list):
                logfire.warning(
                    "Extraction returned non-list", result_type=type(flights)
                )
                return []

            return flights

        except Exception as e:
            logfire.error("Extraction failed", error=str(e), exc_info=True)
            return []  # ✅ Safe fallback


@flight_search_agent.output_validator
async def validate_flight_search(
    ctx: RunContext[FlightDeps], result: FlightSearchResult | NoFlightFound
) -> FlightSearchResult | NoFlightFound:
    """Validate that search results match user's request."""

    # ✅ Check if it's a string (should never happen, but be safe)
    if isinstance(result, str):
        logfire.error("Agent returned string instead of object", result=result)
        raise ModelRetry(
            f"Agent returned plain text: '{result}'. "
            f"You must return either FlightSearchResult or NoFlightFound object. "
            f"Use the create_no_flights_response tool when no flights are found."
        )

    if isinstance(result, NoFlightFound):
        logfire.info("No flights found", request=ctx.deps.search_request.model_dump())
        return result

    # Validate flight criteria match
    req = ctx.deps.search_request
    invalid = [
        (i, f.flight_number)
        for i, f in enumerate(result.flights)
        if f.origin.upper() != req.origin.upper()
        or f.destination.upper() != req.destination.upper()
        or f.date != req.departure_date
    ]

    if invalid:
        logfire.warning("Invalid flights detected", invalid_flights=invalid)
        raise ModelRetry(
            f"Found {len(invalid)} flights that don't match criteria: {invalid}"
        )

    # Calculate analytics
    result.calculate_analytics()

    logfire.info(
        "Flight search completed",
        total_flights=len(result.flights),
        cheapest_price=result.cheapest_price,
    )
    return result
