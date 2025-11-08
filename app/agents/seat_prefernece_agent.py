import logfire
from pydantic_ai import Agent, RunContext, ModelRetry
from pydantic_ai.usage import UsageLimits

from app.models.flight_models import SeatPreference, SeatSelectionFailed
from app.core.llm import llm_model


# Seat Selection Agent
seat_selection_agent = Agent[None, SeatPreference | SeatSelectionFailed](
    llm_model,
    result_type=SeatPreference | SeatSelectionFailed,
    usage_limits=UsageLimits(request_limit=5),
    system_prompt="""
    You are a precise seat selection specialist. Extract seat preferences from user messages.
    
    SEAT MAP KNOWLEDGE:
    - Rows: 1-30 (1 is front, 30 is back)
    - Seats: A-F (A=left window, F=right window, C/D=aisle, B/E=middle)
    - Extra legroom: Rows 1, 14, 20
    - Emergency exits: Varies by aircraft
    
    EXTRACTION RULES:
    1. Must have both row (1-30) and seat (A-F)
    2. Convert spelled numbers to digits (twelve → 12)
    3. Handle formats: "12A", "row 12 seat A", "window seat row 5"
    4. Validate seat exists (A-F only)
    5. If unclear, ask for clarification via SeatSelectionFailed
    
    Be precise and conservative. Only return valid seats.
    """,
    retries=1,
)


@seat_selection_agent.result_validator
async def validate_seat_selection(
    ctx: RunContext[None], 
    result: SeatPreference | SeatSelectionFailed
) -> SeatPreference | SeatSelectionFailed:
    """Validate seat selection with comprehensive checks."""
    with logfire.span('validate_seat_selection'): 
        if isinstance(result, SeatSelectionFailed):
            logfire.info("Seat selection failed", reason=result.reason, user_input=result.user_input)
            
            return result
        
        # Additional validation
        if result.row < 1 or result.row > 30:
            logfire.warning("Invalid seat row", row=result.row)
            raise ModelRetry(f"Invalid row {result.row}. Must be between 1-30.")
        
        if result.seat not in ["A", "B", "C", "D", "E", "F"]:
            logfire.warning("Invalid seat letter", seat=result.seat)
            raise ModelRetry(f"Invalid seat {result.seat}. Must be A-F.")
        
        logfire.info(
            "Seat selection validated",
            seat=str(result),
            seat_type=result.seat_type.value,
            has_extra_legroom=result.has_extra_legroom
        )
        
        return result