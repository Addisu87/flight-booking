import random
import string
import logfire
from pydantic_ai import Agent, RunContext, ModelRetry

from app.models.flight_models import (
    FlightDetails,
    FlightSearchRequest,
    BookingConfirmation,
)
from dataclasses import dataclass
from app.agents.seat_selection_agent import seat_selection_agent
from app.core.llm import llm_model
# from pydantic_ai.usage import UsageLimits

# Global usage limits for seat selection
# BOOKING_USAGE_LIMITS = UsageLimits(
#     request_limit=10, output_tokens_limit=2000, total_tokens_limit=4000
# )


@dataclass
class BookingDeps:
    search_request: FlightSearchRequest
    selected_flight: FlightDetails
    seat_preference_prompt: str | None = None


# Booking Agent - orchestrates complete booking workflow
booking_agent = Agent[BookingDeps, BookingConfirmation](
    llm_model,
    system_prompt="""
    You are a flight booking coordinator.

    INSTRUCTIONS:
    - ALWAYS call the `process_booking` tool as your only step.
    - Never return text directly.
    - Your only valid output is a BookingConfirmation object.
    """,
)


@booking_agent.tool
async def process_booking(
    ctx: RunContext[BookingDeps],
) -> BookingConfirmation:
    """
    Process the complete booking workflow in one atomic operation.
    This prevents the LLM from making decisions about tool sequencing.
    """

    # Handle seat selection safely
    seat = None
    if ctx.deps.seat_preference_prompt:
        try:
            seat_result = await seat_selection_agent.run(
                ctx.deps.seat_preference_prompt
            )
            if hasattr(seat_result.data, "seat"):
                seat = seat_result.data
        except Exception as e:
            logfire.warning(
                "Seat selection failed, continuing without seat", error=str(e)
            )

    # Create booking confirmation
    flight = ctx.deps.selected_flight
    total_price = flight.price * ctx.deps.search_request.passengers

    return BookingConfirmation(
        flight=flight,
        seat=seat,
        passengers=ctx.deps.search_request.passengers,
        total_price=total_price,
        confirmation_number="".join(
            random.choices(string.ascii_uppercase + string.digits, k=6)
        ),
    )


@booking_agent.output_validator
async def validate_booking_result(
    ctx: RunContext[BookingDeps], result: BookingConfirmation
) -> BookingConfirmation:
    """Final validation."""
    if not isinstance(result, BookingConfirmation):
        logfire.error("Invalid result type", got=type(result))
        raise ModelRetry(
            "Must call process_booking tool to generate BookingConfirmation"
        )
    return result
