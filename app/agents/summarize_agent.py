import logfire
from typing import List
from dataclasses import dataclass
from pydantic_ai import Agent, RunContext

from app.models.flight_models import FlightDetails, FlightSearchRequest
from app.core.llm import llm_model
from app.models.flight_models import FlightSummary


@dataclass
class SummarizeDeps:
    """Dependencies for the summarize agent."""
    search_request: FlightSearchRequest
    all_flights: List[FlightDetails]
    search_metadata: dict = None

# Summarize Agent
summarize_agent = Agent[SummarizeDeps, FlightSummary](
    llm_model,
    system_prompt="""
    You are an expert flight analyst. Analyze the provided flights and generate:
    1. A comprehensive summary of options
    2. Key insights about pricing, timing, and availability
    3. Practical recommendations for different traveler types
    
    Use the existing FlightDetails model for best_deal and best_timing fields.
    Focus on actionable insights and helpful recommendations.
    """,
)


@summarize_agent.tool
async def get_flight_analytics(ctx: RunContext[SummarizeDeps]) -> dict:
    """Get analytics about the available flights."""
    with logfire.span("get_flight_analytics"):
        flights = ctx.deps.all_flights
        
        if not flights:
            return {"message": "No flights to analyze"}
        
        prices = [flight.price for flight in flights]
        airlines = list(set(flight.airline for flight in flights))
        direct_flights = [f for f in flights if f.is_direct]
        
        return {
            "total_flights": len(flights),
            "price_min": min(prices),
            "price_max": max(prices),
            "price_avg": sum(prices) / len(prices),
            "airlines_count": len(airlines),
            "direct_flights_count": len(direct_flights),
            "connecting_flights_count": len(flights) - len(direct_flights),
        }


@summarize_agent.system_prompt_modifier
async def add_summary_context(ctx: RunContext[SummarizeDeps]) -> str:
    """Add search context to the system prompt."""
    with logfire.span("add_summary_context"):
        request = ctx.deps.search_request
        flights = ctx.deps.all_flights
        
        context = f"""
        SEARCH CONTEXT:
        - Route: {request.origin} → {request.destination}
        - Date: {request.departure_date}
        - Passengers: {request.passengers}
        - Class: {request.flight_class.value}
        - Total flights: {len(flights)}
        
        FOCUS ON:
        - Practical advice for travelers
        - Value-based recommendations
        - Timing and convenience factors
        """
        
        return context