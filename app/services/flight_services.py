import asyncio
import time
from typing import List, Optional, Tuple
from pydantic_ai.usage import RunUsage
import logfire

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
from app.tools.browserbase_tool import browserbase_tool
from app.tools.kayak_tool import kayak_search_tool
from app.utils.config import settings


@logfire.instrument("search_flights", extract_args=True)
async def search_flights(
    search_request: FlightSearchRequest,
    usage: Optional[RunUsage] = None
) -> FlightSearchResult | NoFlightFound:
    search_start = time.time()
    current_usage = usage or RunUsage()
    
    try:
        result_data = await _execute_flight_search_pipeline(search_request, current_usage, search_start)
        
        logfire.info(
            "Flight search completed",
            search_duration=time.time() - search_start,
            result_type=type(result_data).__name__,
            total_usage=current_usage.total_usage
        )
        
        return result_data
        
    except Exception as e:
        return _handle_search_error(e, search_request, search_start, current_usage)


async def _execute_flight_search_pipeline(
    search_request: FlightSearchRequest, 
    usage: RunUsage, 
    search_start: float
) -> FlightSearchResult | NoFlightFound:
    """Execute the complete flight search pipeline."""
    # Generate Kayak URL and fetch page content
    page_content = await _fetch_flight_search_page(search_request)
    if isinstance(page_content, NoFlightFound):
        return page_content
    
    # Extract flights from page content
    available_flights = await _extract_flights_from_content(page_content, usage)
    if not available_flights:
        return _create_no_flights_found_response(search_request)
    
    # Analyze and find best flights
    return await _analyze_and_select_flights(search_request, available_flights, usage, search_start)


async def _fetch_flight_search_page(search_request: FlightSearchRequest) -> str | NoFlightFound:
    """Generate Kayak URL and fetch page content using Browserbase."""
    with logfire.span("generate_kayak_url"):
        kayak_url = kayak_search_tool(search_request)
        logfire.debug("Generated Kayak URL", url=kayak_url)
    
    with logfire.span("browserbase_navigation"):
        page_content = browserbase_tool(
            kayak_url, 
            wait_for_selector='[data-testid="flight-card"]'
        )
        
        if page_content.startswith("Error"):
            logfire.error("Browserbase failed", error=page_content)
            return NoFlightFound(
                search_request=search_request,
                message="Failed to load flight search results.",
                suggestions=["Try again in a few minutes", "Check your internet connection"]
            )
    
    return page_content


async def _extract_flights_from_content(page_content: str, usage: RunUsage) -> List[FlightDetails]:
    """Extract flight details from page content using the extraction agent."""
    with logfire.span("flight_extraction"):
        extraction_result = await flight_extraction_agent.run(
            page_content, 
            usage=usage
        )
        available_flights = extraction_result.data
        
        logfire.info(
            "Flight extraction completed",
            flights_found=len(available_flights),
            extraction_duration=extraction_result.usage.total_duration
        )
    
    return available_flights


def _create_no_flights_found_response(search_request: FlightSearchRequest) -> NoFlightFound:
    """Create a NoFlightFound response with helpful suggestions."""
    logfire.info("No flights extracted from page content")
    return NoFlightFound(
        search_request=search_request,
        message="No flights found for your search criteria.",
        suggestions=[
            "Try different dates",
            "Check airport codes",
            "Consider nearby airports"
        ]
    )


async def _analyze_and_select_flights(
    search_request: FlightSearchRequest, 
    available_flights: List[FlightDetails], 
    usage: RunUsage,
    search_start: float
) -> FlightSearchResult | NoFlightFound:
    """Analyze available flights and select the best options."""
    with logfire.span("flight_search_analysis"):
        deps = FlightDeps(
            search_request=search_request,
            available_flights=available_flights
        )
        
        search_result = await flight_search_agent.run(
            f"Find the best flights matching this exact criteria: {search_request}",
            deps=deps,
            usage=usage
        )
        
        result_data = search_result.data
        
        # Add search duration to result if it's a successful search
        if isinstance(result_data, FlightSearchResult):
            result_data.search_duration = time.time() - search_start
    
    return result_data


def _handle_search_error(
    error: Exception, 
    search_request: FlightSearchRequest, 
    search_start: float,
    usage: RunUsage
) -> NoFlightFound:
    """Handle search errors and return appropriate response."""
    logfire.error(
        "Flight search failed",
        error=str(error),
        search_request=search_request.dict(),
        duration=time.time() - search_start
    )
    return NoFlightFound(
        search_request=search_request,
        message="An error occurred during flight search.",
        suggestions=["Please try again", "Contact support if issue persists"]
    )


@logfire.instrument("batch_search_flights", extract_args=True)
async def batch_search_flights(
    search_requests: List[FlightSearchRequest],
    usage: Optional[RunUsage] = None
) -> List[FlightSearchResult | NoFlightFound]:
    """
    Perform multiple flight searches in parallel.
    
    Args:
        search_requests: List of flight search requests
        usage: Optional usage tracker
    
    Returns:
        List of search results for each request
    """
    current_usage = usage or RunUsage()
    
    tasks = [
        search_flights(request, current_usage) 
        for request in search_requests
    ]
    
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # Convert exceptions to NoFlightFound
    processed_results = []
    for result in results:
        if isinstance(result, Exception):
            processed_results.append(NoFlightFound(
                search_request=FlightSearchRequest(origin="", destination="", departure_date=None),
                message=f"Search failed: {str(result)}",
                suggestions=["Please try again"]
            ))
        else:
            processed_results.append(result)
    
    logfire.info(
        "Batch flight search completed",
        total_searches=len(search_requests),
        successful_searches=len([r for r in processed_results if not isinstance(r, NoFlightFound)]),
        total_usage=current_usage.total_usage
    )
    
    return processed_results


@logfire.instrument("validate_flight_availability", extract_args=True)
async def validate_flight_availability(
    flight: FlightDetails,
    usage: Optional[RunUsage] = None
) -> bool:
    """
    Validate if a specific flight is still available by checking the booking page.
    
    Args:
        flight: Flight details to validate
        usage: Optional usage tracker
    
    Returns:
        True if flight is available, False otherwise
    """
    current_usage = usage or RunUsage()
    
    if not flight.booking_url:
        logfire.warning("No booking URL available for validation", flight_number=flight.flight_number)
        return False
    
    try:
        with logfire.span("flight_availability_check"):
            page_content = browserbase_tool(
                flight.booking_url,
                wait_for_selector='[data-testid="book-button"], .book-now, .reserve'
            )
            
            # Simple check for availability indicators
            is_available = any(indicator in page_content.lower() for indicator in [
                'book now', 'reserve', 'available', 'select', 'continue'
            ])
            
            logfire.debug(
                "Flight availability check completed",
                flight_number=flight.flight_number,
                is_available=is_available
            )
            
            return is_available
            
    except Exception as e:
        logfire.error(
            "Flight availability check failed",
            flight_number=flight.flight_number,
            error=str(e)
        )
        return False


def create_usage_tracker() -> RunUsage:
    """Create a new usage tracker instance."""
    return RunUsage()


def get_usage_stats(usage: RunUsage) -> dict:
    """Get usage statistics from RunUsage object."""
    return {
        "total_requests": usage.total_usage.request_count,
        "total_tokens": usage.total_usage.total_tokens,
        "total_duration": usage.total_usage.total_duration,
    }


# Utility functions for flight data processing
def filter_flights_by_price(
    flights: List[FlightDetails], 
    max_price: float
) -> List[FlightDetails]:
    """Filter flights by maximum price."""
    return [f for f in flights if f.price <= max_price]


def filter_flights_by_stops(
    flights: List[FlightDetails], 
    max_stops: int
) -> List[FlightDetails]:
    """Filter flights by maximum number of stops."""
    return [f for f in flights if f.stops <= max_stops]


def sort_flights_by_price(flights: List[FlightDetails]) -> List[FlightDetails]:
    """Sort flights by price (ascending)."""
    return sorted(flights, key=lambda x: x.price)


def sort_flights_by_duration(flights: List[FlightDetails]) -> List[FlightDetails]:
    """Sort flights by duration (ascending)."""
    def parse_duration(duration_str: str) -> int:
        try:
            hours = 0
            minutes = 0
            if 'h' in duration_str:
                hours = int(duration_str.split('h')[0].strip())
            if 'm' in duration_str:
                min_part = duration_str.split('h')[1] if 'h' in duration_str else duration_str
                minutes = int(min_part.split('m')[0].strip())
            return hours * 60 + minutes
        except:
            return 0
    
    return sorted(flights, key=lambda x: parse_duration(x.duration))


def get_airline_options(flights: List[FlightDetails]) -> List[str]:
    """Get unique airline names from flight list."""
    return list(set(flight.airline for flight in flights))


def get_price_range(flights: List[FlightDetails]) -> Tuple[float, float]:
    """Get minimum and maximum price from flight list."""
    if not flights:
        return 0.0, 0.0
    prices = [flight.price for flight in flights]
    return min(prices), max(prices)