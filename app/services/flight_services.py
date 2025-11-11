import logfire
from pydantic_ai.usage import RunUsage, UsageLimits
from app.tools.kayak_tool import kayak_search_tool
from app.tools.apify_browser import apify_browser_tool
from app.agents.flight_extraction_agent import flight_extraction_agent
from app.agents.flight_search_agent import flight_search_agent, FlightDeps
from app.models.flight_models import FlightSearchRequest, NoFlightFound

flight_usage_limits = UsageLimits(
    request_limit=5, output_tokens_limit=500, total_tokens_limit=1000
)


async def search_flights(req: FlightSearchRequest, usage: RunUsage | None = None):
    """Search flights pipeline: URL → Scrape → Extract → Analyze"""
    with logfire.span("search_flights", origin=req.origin, destination=req.destination):
        # 1. Build URL and scrape
        page = apify_browser_tool(kayak_search_tool(req))
        if not page or "error" in page.lower():
            return _no_flights(req, "Unable to fetch results")

        # 2. Extract flights
        extracted = await flight_extraction_agent.run(
            page, usage=usage, usage_limits=flight_usage_limits
        )
        if not extracted.output:
            return _no_flights(req, "No flights found")

        # 3. Analyze flights
        result = await flight_search_agent.run(
            f"Analyze flights {req.origin}→{req.destination}",
            deps=FlightDeps(search_request=req, available_flights=extracted.output),
            usage=usage,
        )
        return result.output


def _no_flights(req: FlightSearchRequest, message: str) -> NoFlightFound:
    """Helper for no flight results."""
    return NoFlightFound(
        search_request=req,
        message=message,
        suggestions=["Try different dates", "Check airport codes", "Try again later"]
    )