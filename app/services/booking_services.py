import random
import string
import logfire
from datetime import datetime
from typing import List, Optional

from pydantic_ai.usage import RunUsage, UsageLimits
from app.agents.seat_selection_agent import seat_selection_agent
from app.models.flight_models import FlightDetails, FlightSearchRequest, SeatPreference
from app.services.flight_services import search_flights
from app.utils.usage_utils import get_usage_stats

# Global usage limits for seat selection
booking_usage_limits = UsageLimits(
    request_limit=10, output_tokens_limit=500, total_tokens_limit=1000
)


async def select_seat(seat_input: str, usage: RunUsage) -> SeatPreference:
    """Select seat with single attempt."""
    result = await seat_selection_agent.run(
        seat_input,
        usage=usage,
        usage_limits=booking_usage_limits,
    )
    
    if isinstance(result.output, SeatPreference):
        return result.output
    
    logfire.warning("Seat selection failed", reason=getattr(result.data, 'reason', 'Unknown'))
    raise ValueError("Failed to select seat")


def create_booking(flight: FlightDetails, seat: SeatPreference) -> dict:
    """Create booking confirmation."""
    confirmation = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
    
    return {
        "confirmation_number": confirmation,
        "flight_number": flight.flight_number,
        "airline": flight.airline,
        "price": flight.price,
        "seat": str(seat),
        "route": f"{flight.origin} → {flight.destination}",
        "departure_time": flight.departure_time,
        "status": "confirmed",
        "timestamp": datetime.now().isoformat(),
        "seat_type": seat.seat_type.value,
        "has_extra_legroom": seat.has_extra_legroom,
    }


async def complete_booking_workflow(
    search_request: FlightSearchRequest,
    available_flights: Optional[List[FlightDetails]] = None,
    seat_preference_prompt: Optional[str] = None,
    usage: Optional[RunUsage] = None,
) -> dict:
    """Complete booking workflow."""
    current_usage = usage or RunUsage()

    try:
        if available_flights is None:
            search_result = await search_flights(search_request, current_usage)
            available_flights = getattr(search_result, 'flights', [])
        
        if not available_flights:
            return {
                "status": "error",
                "reason": "No flights available",
                "usage_stats": get_usage_stats(current_usage),
                "timestamp": datetime.now().isoformat(),
            }

        flight = available_flights[0]
        seat = await select_seat(seat_preference_prompt, current_usage) if seat_preference_prompt else None
        booking = create_booking(flight, seat) if seat else create_booking(flight, SeatPreference(row=1, seat="A"))

        return {
            **booking,
            "status": "success",
            "search_criteria": search_request.model_dump(),
            "usage_stats": get_usage_stats(current_usage),
        }

    except Exception as e:
        logfire.error("Booking workflow error", error=str(e))
        return {
            "status": "error",
            "reason": str(e),
            "usage_stats": get_usage_stats(current_usage),
            "timestamp": datetime.now().isoformat(),
        }