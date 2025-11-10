import asyncio
import time
from typing import List, Tuple
import logfire
from pydantic_ai.usage import RunUsage, UsageLimits

from app.agents.flight_agent import (
    flight_extraction_agent,
    flight_search_agent,
    FlightDeps
)
from app.models.flight_models import (
    FlightDetails,
    FlightSearchRequest,
    FlightSearchResult,
    NoFlightFound
)
from app.tools.apify_browser import apify_browser_tool
from app.tools.kayak_tool import kayak_search_tool
from app.utils.usage_utils import get_usage_stats


flight_usage_limits = UsageLimits(request_limit=5, output_tokens_limit=500, total_tokens_limit=1000)

# --------------------------------------------------------------------
# ✅ PUBLIC: Search a single flight request
# --------------------------------------------------------------------

@logfire.instrument("search_flights", extract_args=True)
async def search_flights(
    search_request: FlightSearchRequest,
    usage: RunUsage | None = None
) -> FlightSearchResult | NoFlightFound:
    start = time.time()
    usage = usage or RunUsage()

    try:
        result = await _run_pipeline(search_request, usage, start)

        usage_stats = get_usage_stats(usage)
        logfire.info(
            "Flight search completed",
            duration=time.time() - start,
            type=type(result).__name__,
            **usage_stats
        )
        return result

    except Exception as e:
        logfire.error(
            "Flight search error",
            error=str(e),
            duration=time.time() - start
        )
        return NoFlightFound(
            search_request=search_request,
            message="An unexpected error occurred.",
            suggestions=["Try again", "Contact support if it continues"]
        )


# --------------------------------------------------------------------
# ✅ INTERNAL: Entire Pipeline (URL → Extract → Analyze)
# --------------------------------------------------------------------

async def _run_pipeline(
    search_request: FlightSearchRequest,
    usage: RunUsage,
    start: float
) -> FlightSearchResult | NoFlightFound:

    page = await _fetch_page(search_request)
    if isinstance(page, NoFlightFound):
        return page

    flights = await _extract_flights(page, usage)
    if not flights:
        logfire.info("No flights extracted")
        return NoFlightFound(
            search_request=search_request,
            message="No flights found.",
            suggestions=["Try different dates", "Check airport codes", "Consider nearby airports"]
        )

    return await _analyze_flights(search_request, flights, usage, start)

# --------------------------------------------------------------------
# ✅ INTERNAL: Fetch Kayak Page
# --------------------------------------------------------------------

async def _fetch_page(req: FlightSearchRequest) -> str | NoFlightFound:
    with logfire.span("kayak_url"):
        url = kayak_search_tool(req)
        print(f"🔍 DEBUG: Generated Kayak URL: {url}")
        logfire.debug("Generated Kayak URL", url=url)

    with logfire.span("browserbase_fetch"):
        print(f"🔍 DEBUG: Calling apify_browser_tool with URL: {url}")
        content = apify_browser_tool(url)
        print(f"🔍 DEBUG: apify_browser_tool returned: {content[:200]}...")

        if content.startswith("Error") or content.startswith("Apify"):
            error_msg = f"Apify failed: {content}"
            print(f"❌ DEBUG: {error_msg}")
            return NoFlightFound(
                search_request=req,
                message="Failed to load flight results.",
                suggestions=["Try again later", "Check your connection"],
                alternative_dates=[]
            )

    print(f"✅ DEBUG: Successfully fetched page content, length: {len(content)}")
    return content


# --------------------------------------------------------------------
# ✅ INTERNAL: Extract Flights from Page
# --------------------------------------------------------------------

async def _extract_flights(content: str, usage: RunUsage) -> List[FlightDetails]:
    with logfire.span("extract_flights"):
        result = await flight_extraction_agent.run(content, usage=usage, usage_limits=flight_usage_limits)
        flights = result.output

        # FIX: Use correct duration attribute
        duration = getattr(result.usage, 'total_duration', 0)
        
        logfire.info(
            "Extraction complete",
            found=len(flights),
            extraction_time=duration
        )

        return flights


# --------------------------------------------------------------------
# ✅ INTERNAL: Analyze & Select Best Flights
# --------------------------------------------------------------------

async def _analyze_flights(
    req: FlightSearchRequest,
    flights: List[FlightDetails],
    usage: RunUsage,
    start: float
) -> FlightSearchResult | NoFlightFound:

    with logfire.span("analyze_flights"):
        deps = FlightDeps(search_request=req, available_flights=flights)

        # ✅ Agent handles everything now
        result = await flight_search_agent.run(
            f"Find the best flights for: {req}",
            deps=deps,
            usage=usage,
            usage_limits=flight_usage_limits
        )

        output = result.output

        # ✅ Attach duration
        if isinstance(output, FlightSearchResult):
            output.search_duration = time.time() - start

        return output

# --------------------------------------------------------------------
# ✅ PUBLIC: Batch Search
# --------------------------------------------------------------------

@logfire.instrument("batch_search_flights", extract_args=True)
async def batch_search_flights(
    search_requests: List[FlightSearchRequest],
    usage: RunUsage | None = None
) -> List[FlightSearchResult | NoFlightFound]:
    usage = usage or RunUsage()

    tasks = [search_flights(req, usage) for req in search_requests]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    fixed = []
    for r in results:
        if isinstance(r, Exception):
            fixed.append(
                NoFlightFound(
                    search_request=FlightSearchRequest(origin="", destination="", departure_date=None),
                    message=f"Search failed: {r}",
                    suggestions=["Try again"]
                )
            )
        else:
            fixed.append(r)

    return fixed


# --------------------------------------------------------------------
# ✅ PUBLIC: Validate Flight Availability
# --------------------------------------------------------------------

@logfire.instrument("validate_flight_availability", extract_args=True)
async def validate_flight_availability(
    flight: FlightDetails,
    usage: RunUsage | None = None
) -> bool:
    usage = usage or RunUsage()

    if not getattr(flight, "booking_url", None):
        logfire.warning("Missing booking URL", flight=flight.flight_number)
        return False

    try:
        with logfire.span("availability_check"):
            content = apify_browser_tool(
                flight.booking_url,
                wait_for_selector='[data-testid="book-button"], .book-now, .reserve'
            )

            available = any(
                marker in content.lower()
                for marker in ["book now", "reserve", "available", "select", "continue"]
            )

            logfire.debug("Availability check", flight=flight.flight_number, available=available)
            return available

    except Exception as e:
        logfire.error("Availability check failed", error=str(e))
        return False

# --------------------------------------------------------------------
# ✅ PUBLIC: Utility Helpers (minimal)
# --------------------------------------------------------------------

def filter_flights_by_price(flights: List[FlightDetails], max_price: float) -> List[FlightDetails]:
    return [f for f in flights if f.price <= max_price]

def filter_flights_by_stops(flights: List[FlightDetails], max_stops: int) -> List[FlightDetails]:
    return [f for f in flights if f.stops <= max_stops]

def sort_flights_by_price(flights: List[FlightDetails]) -> List[FlightDetails]:
    return sorted(flights, key=lambda f: f.price)

def sort_flights_by_duration(flights: List[FlightDetails]) -> List[FlightDetails]:
    def to_minutes(d: str):
        try:
            h, m = 0, 0
            if "h" in d: h = int(d.split("h")[0])
            if "m" in d: m = int(d.split("h")[-1].replace("m", ""))
            return h * 60 + m
        except:
            return 0

    return sorted(flights, key=lambda f: to_minutes(f.duration))

def get_airline_options(flights: List[FlightDetails]) -> List[str]:
    return list({f.airline for f in flights})

def get_price_range(flights: List[FlightDetails]) -> Tuple[float, float]:
    if not flights:
        return 0.0, 0.0
    prices = [f.price for f in flights]
    return min(prices), max(prices)