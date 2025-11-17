from typing import List
from dataclasses import dataclass
from pydantic_ai import Agent, RunContext

from app.models.flight_models import FlightDetails, FlightSearchRequest, FlightSummary
from app.core.llm import llm_model
# from pydantic_ai.usage import UsageLimits


# SUMMARIZE_USAGE_LIMITS = UsageLimits(
#     request_limit=5, output_tokens_limit=500, total_tokens_limit=1000
# )


@dataclass
class SummarizeDeps:
    """Dependencies for the summarize agent."""

    search_request: FlightSearchRequest
    flights: List[FlightDetails]


# Summarize Agent - analyzes flights and generates insights
summarize_agent = Agent[SummarizeDeps, FlightSummary](
    llm_model,
    system_prompt="""
    You are an expert flight analyst. Analyze the provided flights and generate:
    1. A comprehensive summary of options
    2. Key insights about pricing, timing, and availability
    3. Practical recommendations for different traveler types
    
    Use the flight analytics tool to get statistics.
    Focus on actionable insights and value-based recommendations.
    """,
)


@summarize_agent.tool
async def get_flight_analytics(ctx: RunContext[SummarizeDeps]) -> dict:
    """Get analytics about the available flights."""
    flights = ctx.deps.flights

    if not flights:
        return {"message": "No flights to analyze"}

    prices = [f.price for f in flights]
    airlines = list(set(f.airline for f in flights))
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


@summarize_agent.tool
async def add_search_context(ctx: RunContext[SummarizeDeps]) -> str:
    """Add search context for better analysis."""
    req = ctx.deps.search_request
    return f"""
    SEARCH CONTEXT:
    - Route: {req.origin} → {req.destination}
    - Date: {req.departure_date}
    - Passengers: {req.passengers}
    - Class: {req.flight_class.value}
    """
