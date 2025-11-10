import random
import string
import logfire
from datetime import datetime
from typing import List, Dict, Tuple, Optional

from pydantic_ai.usage import RunUsage, UsageLimits
from pydantic_ai.messages import ModelMessage

from app.agents.seat_selection_agent import seat_selection_agent
from app.models.flight_models import (
    FlightDetails,
    FlightSearchRequest,
    SeatPreference,
)
from app.services.flight_services import search_flights


# Global usage limits for seat selection
booking_usage_limits = UsageLimits(request_limit=10, output_tokens_limit=500, total_tokens_limit=1000)


# ------------------------------------------------------------------------------
# ✅ Seat Selection (with retry)
# ------------------------------------------------------------------------------

async def select_seat_with_retry(
    usage: Optional[RunUsage] = None,
    max_attempts: int = 3,
    seat_input: str | None = None,
    message_history: List[ModelMessage] | None = None
) -> Tuple[Optional[SeatPreference], List[ModelMessage], RunUsage]:
    with logfire.span("select_seat_with_retry"):
        history = message_history or []
        current_usage = usage or RunUsage()

        for attempt in range(1, max_attempts + 1):
            seat, history, current_usage = await _seat_selection_attempt(
                history, current_usage, seat_input if attempt == 1 else None
            )
            if seat:
                return seat, history, current_usage

        # Fallback
        fallback = SeatPreference(row=10, seat="C")
        logfire.info("Seat selection fallback used", fallback=str(fallback))
        return fallback, history, current_usage


async def _seat_selection_attempt(
    history: List[ModelMessage],
    usage: RunUsage,
    seat_string: str | None = None
) -> Tuple[Optional[SeatPreference], List[ModelMessage], RunUsage]:

    if not seat_string:
        return None, history, usage

    try:
        result = await seat_selection_agent.run(
            seat_string,
            message_history=history.copy(),
            usage=usage,
            usage_limits=booking_usage_limits,
        )

        if isinstance(result.data, dict) and 'reason' in result.data:
            logfire.warning("Seat selection failed", reason=result.data['reason'])
            return None, result.all_messages(), result.usage

        if isinstance(result.output, SeatPreference):
            return result.output, result.all_messages(), result.usage

        logfire.warning("Seat selection returned unexpected output type")
        return None, result.all_messages(), result.usage

    except Exception as e:
        logfire.error("Seat selection error", error=str(e))
        return None, history, usage


# ------------------------------------------------------------------------------
# ✅ Ticket Purchase
# ------------------------------------------------------------------------------


async def buy_tickets(flight: FlightDetails, seat: SeatPreference) -> Dict[str, str]:
    with logfire.span('buy_tickets'):
        confirmation = _generate_confirmation()
        now = datetime.now().isoformat()

        purchase = {
            "flight_number": flight.flight_number,
            "airline": flight.airline,
            "seat": str(seat),
            "price": flight.price,
            "confirmation_number": confirmation,
            "status": "confirmed",
            "route": f"{flight.origin} → {flight.destination}",
            "date": str(flight.date),
            "departure_time": flight.departure_time,
            "arrival_time": flight.arrival_time,
            "purchase_time": now,
            "passenger_count": 1,
            "seat_type": seat.seat_type.value,
            "has_extra_legroom": seat.has_extra_legroom,
        }

        logfire.info("Ticket purchase completed", confirmation=confirmation)
        return purchase


def _generate_confirmation() -> str:
    letters = ''.join(random.choices(string.ascii_uppercase, k=3))
    numbers = ''.join(random.choices(string.digits, k=3))
    return f"{letters}{numbers}"


# ------------------------------------------------------------------------------
# ✅ Full Booking Workflow
# ------------------------------------------------------------------------------

@logfire.instrument("complete_booking_workflow", extract_args=True)
async def complete_booking_workflow(
    search_request: FlightSearchRequest,
    available_flights: List[FlightDetails],
    seat_preference_prompt: str | None = None,
    max_seat_retries: int = 3,
    usage: Optional[RunUsage] = None,
) -> Dict:

    history: List[ModelMessage] = []
    current_usage = usage or RunUsage()

    try:
        if not available_flights:
            return _error("No flights available", current_usage)

        # STEP 1: Run flight search
        search_result = await search_flights(search_request, current_usage)
        if hasattr(search_result, "message"):
            return _error(search_result.message, current_usage)

        # STEP 2: Pick the actual flight from available_flights
        flight = _match_flight(search_result, available_flights)
        if not flight:
            return _error("No suitable flight found", current_usage)

        # STEP 3: Seat selection with retries
        seat, history, current_usage = await select_seat_with_retry(
            current_usage,
            max_attempts=max_seat_retries,
            seat_input=seat_preference_prompt,
            message_history=history
        )

        # STEP 4: Purchase ticket
        purchase = await buy_tickets(flight, seat)

        return {
            **purchase,
            "status": "success",
            "search_criteria": search_request.model_dump(),
            "usage_stats": current_usage,
            "workflow_steps": {
                "seat_selection_attempts": max_seat_retries,
                "total_duration": current_usage.total_usage.total_duration if current_usage.total_usage else 0
            }
        }

    except Exception as e:
        logfire.error("Booking workflow error", error=str(e))
        return _error(str(e), current_usage)


def _match_flight(
    search_result, flights: List[FlightDetails]
) -> Optional[FlightDetails]:

    if not search_result.flights:
        return None

    best = getattr(search_result, 'best_value_flight', None) or search_result.flights[0]

    for f in flights:
        if f.airline == best.airline and f.flight_number == best.flight_number:
            return f

    return flights[0] if flights else None


def _error(reason: str, usage: RunUsage) -> Dict:
    return {
        "status": "error",
        "reason": reason,
        "usage_stats": usage,
        "timestamp": datetime.now().isoformat(),
    }


# ------------------------------------------------------------------------------
# ✅ Quick Booking (Shortcut for simple use cases)
# ------------------------------------------------------------------------------

@logfire.instrument("quick_booking", extract_args=True)
async def quick_booking(
    origin: str,
    destination: str,
    departure_date: str,
    available_flights: List[FlightDetails],
    seat_preference: str | None = None,
    passengers: int = 1,
    flight_class: str = "economy",
    usage: Optional[RunUsage] = None
) -> Dict:

    try:
        date = datetime.strptime(departure_date, "%Y-%m-%d").date()
    except ValueError:
        return _error(f"Invalid date: {departure_date}", usage or RunUsage())

    req = FlightSearchRequest(
        origin=origin.upper(),
        destination=destination.upper(),
        departure_date=date,
        passengers=passengers,
        flight_class=flight_class
    )

    return await complete_booking_workflow(
        search_request=req,
        available_flights=available_flights,
        seat_preference_prompt=seat_preference,
        usage=usage
    )