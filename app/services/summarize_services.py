from typing import List, Dict
from pydantic_ai.usage import RunUsage, UsageLimits
import logfire

from app.agents.summarize_agent import summarize_agent, SummarizeDeps
from app.models.flight_models import FlightDetails, FlightSearchRequest

summarize_usage_limits = UsageLimits(request_limit=5, output_tokens_limit=500, total_tokens_limit=1000)

# ---------------------------------------------------------
# ✅ PUBLIC: Generate Flight Summary (AI-powered)
# ---------------------------------------------------------

@logfire.instrument("generate_flight_summary", extract_args=True)
async def generate_flight_summary(
    search_request: FlightSearchRequest,
    flights: List[FlightDetails],
    usage: RunUsage | None = None,
    include_recommendations: bool = True,
    include_insights: bool = True
) -> Dict:
    usage = usage or RunUsage()

    if not flights:
        return _create_empty_summary(search_request, "No flights found.")

    try:
        deps = SummarizeDeps(
            search_request=search_request,
            all_flights=flights,
            search_metadata={
                "include_recommendations": include_recommendations,
                "include_insights": include_insights
            }
        )

        result = await summarize_agent.run(
            "Generate flight summary",
            deps=deps,
            usage=usage,
            usage_limits=summarize_usage_limits
        )

        return _format_summary_result(
            result.output, search_request, len(flights), usage
        )

    except Exception as e:
        logfire.error("Summary generation failed", error=str(e))
        return _create_fallback_summary(search_request, flights, usage)


# ---------------------------------------------------------
# ✅ PUBLIC: Comparative Analysis (non-AI)
# ---------------------------------------------------------

@logfire.instrument("generate_comparative_analysis", extract_args=True)
async def generate_comparative_analysis(
    flights: List[FlightDetails],
    usage: RunUsage | None = None
) -> Dict:
    usage = usage or RunUsage()

    if not flights:
        return {"error": "No flights provided", "usage_stats": usage}

    try:
        analysis = _perform_basic_comparison(flights)
        analysis["usage_stats"] = usage
        return analysis
    except Exception as e:
        logfire.error("Comparative analysis failed", error=str(e))
        return {"error": str(e), "usage_stats": _get_usage_stats(usage)}


# ---------------------------------------------------------
# ✅ PUBLIC: Traveler Recommendations (non-AI logic)
# ---------------------------------------------------------

@logfire.instrument("generate_travel_recommendations", extract_args=True)
async def generate_travel_recommendations(
    search_request: FlightSearchRequest,
    flights: List[FlightDetails],
    traveler_type: str = "general",
    usage: RunUsage | None = None
) -> Dict:
    usage = usage or RunUsage()

    if not flights:
        return {
            "traveler_type": traveler_type,
            "recommendations": ["No flights available"],
            "suitable_flights": [],
            "usage_stats": usage
        }

    try:
        suitable = _filter_flights(flights, traveler_type)
        recs = _traveler_recommendations(suitable, traveler_type, search_request)

        return {
            "traveler_type": traveler_type,
            "recommendations": recs,
            "suitable_flights": [_flight_dict(f) for f in suitable[:5]],
            "total_suitable_flights": len(suitable),
            "usage_stats": usage
        }

    except Exception as e:
        logfire.error("Recommendation generation failed", error=str(e))
        return {
            "traveler_type": traveler_type,
            "recommendations": ["Error generating recommendations"],
            "suitable_flights": [],
            "usage_stats": usage
        }


# ---------------------------------------------------------
# ✅ PUBLIC: Quick Insights (simple stats)
# ---------------------------------------------------------

@logfire.instrument("generate_quick_insights", extract_args=True)
def generate_quick_insights(flights: List[FlightDetails]) -> Dict:
    if not flights:
        return {"insights": ["No flights available"]}

    prices = [f.price for f in flights]
    airlines = list({f.airline for f in flights})
    direct = sum(1 for f in flights if f.stops == 0)

    insights = [
        f"{len(flights)} flights found",
        f"Prices: ${min(prices):.0f}–${max(prices):.0f}",
        f"{len(airlines)} airlines",
        f"{direct} direct flights"
    ]

    return {
        "insights": insights,
        "statistics": {
            "min_price": min(prices),
            "max_price": max(prices),
            "avg_price": sum(prices) / len(flights),
            "direct_pct": (direct / len(flights)) * 100
        }
    }


# ---------------------------------------------------------
# ✅ PUBLIC: Usage Tracker
# ---------------------------------------------------------

def create_usage_tracker() -> RunUsage:
    return RunUsage()


# ---------------------------------------------------------
# ✅ INTERNAL HELPERS (NOT EXPORTED)
# ---------------------------------------------------------

def _format_summary_result(data, search_request, count, usage):
    return {
        "search_criteria": search_request.dict(),
        "total_flights": count,
        "summary_text": getattr(data, "summary_text", ""),
        "key_insights": getattr(data, "key_insights", []),
        "recommendations": getattr(data, "recommendations", []),
        "price_range": getattr(data, "price_range", ""),
        "airlines": getattr(data, "airlines", []),
        "direct_flights": getattr(data, "direct_flights", 0),
        "connecting_flights": getattr(data, "connecting_flights", 0),
        "best_deal": getattr(data, "best_deal", None),
        "best_timing": getattr(data, "best_timing", None),
        "usage_stats": usage,
        "generated_at": _timestamp()
    }


def _create_empty_summary(search_request, message):
    return {
        "search_criteria": search_request.dict(),
        "total_flights": 0,
        "summary_text": message,
        "key_insights": ["No flights available"],
        "recommendations": [
            "Try adjusting travel dates",
            "Consider nearby airports",
            "Check seasonal variations"
        ],
        "price_range": "N/A",
        "airlines": [],
        "direct_flights": 0,
        "connecting_flights": 0,
        "best_deal": None,
        "best_timing": None,
        "usage_stats": {"total_requests": 0, "total_tokens": 0, "total_duration": 0},
        "generated_at": _timestamp()
    }


def _create_fallback_summary(search_request, flights, usage):
    prices = [f.price for f in flights]
    airlines = list({f.airline for f in flights})
    direct = sum(1 for f in flights if f.stops == 0)

    text = (
        f"{len(flights)} flights found "
        f"from {search_request.origin} to {search_request.destination}. "
        f"Prices: ${min(prices):.0f}–${max(prices):.0f}. "
        f"{direct} direct flights."
    )

    return {
        "search_criteria": search_request.dict(),
        "total_flights": len(flights),
        "summary_text": text,
        "key_insights": [
            f"Airlines: {', '.join(airlines[:3])}",
            f"Price range: ${min(prices):.0f}–${max(prices):.0f}",
            f"{direct} direct flights"
        ],
        "recommendations": [
            "Compare prices across airlines",
            "Choose direct flights for shorter travel",
            "Book early to save money"
        ],
        "price_range": f"${min(prices):.0f}–${max(prices):.0f}",
        "airlines": airlines,
        "direct_flights": direct,
        "connecting_flights": len(flights) - direct,
        "best_deal": min(flights, key=lambda x: x.price),
        "best_timing": flights[0],
        "usage_stats": _get_usage_stats(usage),
        "generated_at": _timestamp()
    }


def _perform_basic_comparison(flights):
    cheapest = min(flights, key=lambda f: f.price)
    airlines = list({f.airline for f in flights})

    return {
        "cheapest_option": _flight_dict(cheapest),
        "price_range": {
            "min": min(f.price for f in flights),
            "max": max(f.price for f in flights)
        },
        "total_flights": len(flights),
        "unique_airlines": len(airlines)
    }


def _filter_flights(flights, traveler_type):
    if traveler_type == "budget":
        return sorted(flights, key=lambda x: x.price)[:10]
    if traveler_type in {"business", "comfort", "family"}:
        directs = [f for f in flights if f.stops == 0]
        return sorted(directs or flights, key=lambda x: x.price)[:10]
    return flights[:10]


def _traveler_recommendations(flights, traveler_type, req):
    if not flights:
        return ["No suitable flights found"]

    cheapest = min(flights, key=lambda x: x.price)
    recs = []

    if traveler_type == "budget":
        recs.append(f"Choose {cheapest.airline} at ${cheapest.price} for best savings")

    if traveler_type in {"business", "comfort", "family"}:
        directs = [f for f in flights if f.stops == 0]
        if directs:
            best = min(directs, key=lambda x: x.price)
            recs.append(f"Direct flight recommended: {best.airline}")

    recs.extend([
        "Compare baggage policies",
        "Verify travel documentation",
        "Consider travel insurance"
    ])

    return recs


def _flight_dict(f):
    return {
        "airline": f.airline,
        "flight_number": f.flight_number,
        "price": f.price,
        "origin": f.origin,
        "destination": f.destination,
        "departure_time": f.departure_time,
        "arrival_time": f.arrival_time,
        "duration": f.duration,
        "stops": f.stops,
        "is_direct": f.stops == 0
    }