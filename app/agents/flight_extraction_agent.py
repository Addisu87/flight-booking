from pydantic_ai import Agent
from app.core.llm import llm_model

flight_extraction_agent = Agent(
    llm_model,
    system_prompt="""
    Extract flights:
    - Airline
    - Flight number
    - Price
    - Duration
    - Stops
    - Origin/Destination codes
    - Departure/Arrival time
    - Booking URL
    Output list of FlightDetails objects.
    """,
)
