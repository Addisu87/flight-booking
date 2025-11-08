from pydantic_ai import Agent, RunContext
from pydantic_ai.models.openai import OpenAIModel

from app.models.flight_models import SeatPreference, SeatSelectionFailed
from app.utils.config import settings
from app.core.llm import llm_model


# Seat Selection Agent
seat_selection_agent = Agent[None, SeatPreference | SeatSelectionFailed](
    llm_model,
    result_type=SeatPreference | SeatSelectionFailed,
    system_prompt="""
    You are a seat selection expert. Extract the user's seat preference from their message.
    
    Important information:
    - Rows are numbered 1-30
    - Seats are A-F (A and F are window seats, C and D are aisle seats)
    - Row 1, 14, and 20 have extra leg room
    - Emergency exit rows typically have more space
    
    If the user's preference is unclear or invalid, respond with a failure.
    """,
    retries=1,
)