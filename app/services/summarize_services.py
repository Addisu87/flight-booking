import logfire
from datetime import datetime
from typing import List
from pydantic_ai.usage import RunUsage, UsageLimits

from app.agents.summarize_agent import summarize_agent, SummarizeDeps
from app.models.flight_models import FlightDetails, FlightSearchRequest
from app.utils.usage_utils import get_usage_stats

summarize_usage_limits = UsageLimits(
    request_limit=5, output_tokens_limit=500, total_tokens_limit=1000
)


async def generate_flight_summary(
    search_request: FlightSearchRequest,
    flights: List[FlightDetails],
    usage: RunUsage | None = None,
) -> dict:
    """Generate AI-powered flight summary."""
    with logfire.span("generate_flight_summary"):
        current_usage = usage or RunUsage()

        if not flights:
            return _empty_summary(search_request, current_usage)

        try:
            result = await summarize_agent.run(
                "Generate flight summary",
                deps=SummarizeDeps(search_request=search_request, all_flights=flights),
                usage=current_usage,
                usage_limits=summarize_usage_limits,
            )
            return _format_summary(result.output, search_request, len(flights), result.usage)
        except Exception as e:
            logfire.error("Summary generation failed", error=str(e))
            return _fallback_summary(search_request, flights, current_usage)


def generate_quick_insights(flights: List[FlightDetails]) -> dict:
    """Generate quick statistical insights."""
    if not flights:
        return {"insights": ["No flights available"]}

    prices = [f.price for f in flights]
    airlines = list({f.airline for f in flights})
    direct = sum(1 for f in flights if f.stops == 0)

    return {
        "insights": [
            f"{len(flights)} flights found",
            f"Prices: ${min(prices):.0f}–${max(prices):.0f}",
            f"{len(airlines)} airlines",
            f"{direct} direct flights",
        ],
        "statistics": {
            "min_price": min(prices),
            "max_price": max(prices),
            "avg_price": sum(prices) / len(flights),
            "direct_pct": (direct / len(flights)) * 100,
        },
    }


def _format_summary(data, search_request, count, usage):
    return {
        "search_criteria": search_request.model_dump(),
        "total_flights": count,
        "summary_text": getattr(data, "summary_text", ""),
        "key_insights": getattr(data, "key_insights", []),
        "recommendations": getattr(data, "recommendations", []),
        "best_deal": getattr(data, "best_deal", None),
        "best_timing": getattr(data, "best_timing", None),
        "usage_stats": get_usage_stats(usage),
        "generated_at": datetime.now().isoformat(),
    }


def _empty_summary(search_request, usage):
    return {
        "search_criteria": search_request.model_dump(),
        "total_flights": 0,
        "summary_text": "No flights found",
        "key_insights": ["No flights available"],
        "recommendations": ["Try different dates", "Check airport codes"],
        "best_deal": None,
        "best_timing": None,
        "usage_stats": get_usage_stats(usage),
        "generated_at": datetime.now().isoformat(),
    }


def _fallback_summary(search_request, flights, usage):
    prices = [f.price for f in flights]
    airlines = list({f.airline for f in flights})
    direct = sum(1 for f in flights if f.stops == 0)

    return {
        "search_criteria": search_request.model_dump(),
        "total_flights": len(flights),
        "summary_text": f"{len(flights)} flights found. Prices: ${min(prices):.0f}–${max(prices):.0f}",
        "key_insights": [
            f"Airlines: {', '.join(airlines[:3])}",
            f"Price range: ${min(prices):.0f}–${max(prices):.0f}",
            f"{direct} direct flights",
        ],
        "recommendations": [
            "Compare prices across airlines",
            "Choose direct flights for shorter travel",
        ],
        "best_deal": min(flights, key=lambda x: x.price).model_dump(),
        "best_timing": flights[0].model_dump(),
        "usage_stats": get_usage_stats(usage),
        "generated_at": datetime.now().isoformat(),
    }