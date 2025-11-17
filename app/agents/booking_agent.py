import random
import string
import logfire
from pydantic_ai import Agent, RunContext, ModelRetry

from app.models.flight_models import (
    FlightDetails,
    FlightSearchRequest,
    SeatPreference,
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
    You are a flight booking coordinator for CONFIRMED flights only.
    
    **MANDATORY WORKFLOW** (Execute exactly in this order):
    1. **ALWAYS** call `select_seat_if_requested` tool first
       - This will return a SeatPreference or None (both are valid)
    2. **THEN** call `create_booking_confirmation` tool as your FINAL step
       - Pass the seat result from step 1 (even if it's None)
    
    **CRITICAL RULES**:
    - Never return text directly
    - Never skip the create_booking_confirmation tool
    - Your only valid output is a BookingConfirmation object
    """,
)

# @booking_agent.tool
# async def select_seat_if_requested(
#     ctx: RunContext[BookingDeps],
# ) -> SeatPreference | None:
#     """
#     Select seat based on user preference. 
#     Returns None if no preference or selection fails.
#     This is SAFE to call - it will never raise an exception.
#     """
#     if not ctx.deps.seat_preference_prompt:
#         logfire.info("No seat preference provided, skipping seat selection")
#         return None

#     try:
#         result = await seat_selection_agent.run(
#             ctx.deps.seat_preference_prompt,
#             # usage=ctx.usage,
#             # usage_limits=BOOKING_USAGE_LIMITS,
#         )
        
#         # Check if result has seat attribute (success) or is SeatSelectionFailed
#         if hasattr(result.data, 'seat'):
#             logfire.info("Seat selection succeeded", seat=str(result.data))
#             return result.data
            
#         logfire.warning("Seat selection resulted in failure", result=result.data)
#         return None
        
#     except Exception as e:
#         logfire.error("Seat selection agent failed", error=str(e), exc_info=True)
#         return None  # Graceful degradation - booking continues without seat


# @booking_agent.tool
# async def create_booking_confirmation(
#     ctx: RunContext[BookingDeps],
#     seat: SeatPreference | None,
# ) -> BookingConfirmation:
#     """
#     Generate booking confirmation with all details.
#     This MUST be called as the final step.
#     """
    
#     flight = ctx.deps.selected_flight
#     total_price = flight.price * ctx.deps.search_request.passengers
    
#     booking = BookingConfirmation(
#         flight=flight,
#         seat=seat,     
#         passengers=ctx.deps.search_request.passengers,
#         total_price=total_price,
#         confirmation_number="".join(random.choices(string.ascii_uppercase + string.digits, k=6)),
#     )
    
#     logfire.info("Booking confirmation created", 
#                  booking_id=booking.id, 
#                  flight=flight.flight_number,
#                  seat=str(seat) if seat else "Auto-assigned",
#                  total_price=total_price)
#     return booking

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
            seat_result = await seat_selection_agent.run(ctx.deps.seat_preference_prompt)
            if hasattr(seat_result.data, 'seat'):
                seat = seat_result.data
        except Exception as e:
            logfire.warning("Seat selection failed, continuing without seat", error=str(e))
    
    # Create booking confirmation
    flight = ctx.deps.selected_flight
    total_price = flight.price * ctx.deps.search_request.passengers
    
    return BookingConfirmation(
        flight=flight,
        seat=seat,
        passengers=ctx.deps.search_request.passengers,
        total_price=total_price,
        confirmation_number="".join(random.choices(string.ascii_uppercase + string.digits, k=6)),
    )
    
@booking_agent.output_validator
async def validate_booking_result(
    ctx: RunContext[BookingDeps], result: BookingConfirmation
) -> BookingConfirmation:
    """Final validation."""
    if not isinstance(result, BookingConfirmation):
        logfire.error("Invalid result type", got=type(result))
        raise ModelRetry("Must call process_booking tool to generate BookingConfirmation")
    return result