from typing import List, Dict
from pydantic_ai.usage import RunUsage, UsageLimits
import logfire
from datetime import datetime

from app.agents.summarize_agent import summarize_agent, SummarizeDeps
from app.models.flight_models import FlightDetails, FlightSearchRequest
from app.utils.usage_utils import get_usage_stats

summarize_usage_limits = UsageLimits(
    request_limit=5, output_tokens_limit=500, total_tokens_limit=1000
)


def _timestamp():
    return datetime.now().isoformat()


# ---------------------------------------------------------
# ✅ PUBLIC: Generate Flight Summary (AI-powered)
# ---------------------------------------------------------


async def generate_flight_summary(
    search_request: FlightSearchRequest,
    flights: List[FlightDetails],
    usage: RunUsage | None = None,
    include_recommendations: bool = True,
    include_insights: bool = True,
) -> Dict:
    with logfire.span("generate_flight_summary"):
        current_usage = usage or RunUsage()

        if not flights:
            return _create_empty_summary(
                search_request, "No flights found.", current_usage
            )

        try:
            with logfire.span("prepare_summary_dependencies"):
                deps = SummarizeDeps(
                    search_request=search_request,
                    all_flights=flights,
                    search_metadata={
                        "include_recommendations": include_recommendations,
                        "include_insights": include_insights,
                    },
                )

            with logfire.span("run_summarize_agent"):
                result = await summarize_agent.run(
                    "Generate flight summary",
                    deps=deps,
                    usage=current_usage,
                    usage_limits=summarize_usage_limits,
                )

            return _format_summary_result(
                result.output, search_request, len(flights), result.usage
            )

        except Exception as e:
            logfire.error("Summary generation failed", error=str(e))
            return _create_fallback_summary(search_request, flights, current_usage)


# ---------------------------------------------------------
# ✅ PUBLIC: Comparative Analysis (non-AI)
# ---------------------------------------------------------


async def generate_comparative_analysis(
    flights: List[FlightDetails],
    usage: RunUsage | None = None,
) -> Dict:
    with logfire.span("generate_comparative_analysis"):
        current_usage = usage or RunUsage()

        if not flights:
            return {
                "error": "No flights provided",
                "usage_stats": get_usage_stats(current_usage),
            }

        try:
            with logfire.span("perform_basic_comparison"):
                analysis = _perform_basic_comparison(flights)
                analysis["usage_stats"] = get_usage_stats(current_usage)
            return analysis
        except Exception as e:
            logfire.error("Comparative analysis failed", error=str(e))
            return {"error": str(e), "usage_stats": get_usage_stats(current_usage)}


# ---------------------------------------------------------
# ✅ PUBLIC: Traveler Recommendations (non-AI logic)
# ---------------------------------------------------------


async def generate_travel_recommendations(
    search_request: FlightSearchRequest,
    flights: List[FlightDetails],
    traveler_type: str = "general",
    usage: RunUsage | None = None,
) -> Dict:
    with logfire.span("generate_travel_recommendations"):
        current_usage = usage or RunUsage()

        if not flights:
            return {
                "traveler_type": traveler_type,
                "recommendations": ["No flights available"],
                "suitable_flights": [],
                "usage_stats": get_usage_stats(current_usage),
            }

        try:
            with logfire.span("filter_and_analyze_flights"):
                suitable = _filter_flights(flights, traveler_type)
                recs = _traveler_recommendations(
                    suitable, traveler_type, search_request
                )

            return {
                "traveler_type": traveler_type,
                "recommendations": recs,
                "suitable_flights": [f.model_dump() for f in suitable[:5]],
                "total_suitable_flights": len(suitable),
                "usage_stats": get_usage_stats(current_usage),
            }

        except Exception as e:
            logfire.error("Recommendation generation failed", error=str(e))
            return {
                "traveler_type": traveler_type,
                "recommendations": ["Error generating recommendations"],
                "suitable_flights": [],
                "usage_stats": get_usage_stats(current_usage),
            }


# ---------------------------------------------------------
# ✅ PUBLIC: Quick Insights (simple stats)
# ---------------------------------------------------------


def generate_quick_insights(flights: List[FlightDetails]) -> Dict:
    with logfire.span("generate_quick_insights"):
        if not flights:
            return {"insights": ["No flights available"]}

        with logfire.span("calculate_insight_metrics"):
            prices = [f.price for f in flights]
            airlines = list({f.airline for f in flights})
            direct = sum(1 for f in flights if f.stops == 0)

            insights = [
                f"{len(flights)} flights found",
                f"Prices: ${min(prices):.0f}–${max(prices):.0f}",
                f"{len(airlines)} airlines",
                f"{direct} direct flights",
            ]

        return {
            "insights": insights,
            "statistics": {
                "min_price": min(prices),
                "max_price": max(prices),
                "avg_price": sum(prices) / len(flights),
                "direct_pct": (direct / len(flights)) * 100,
            },
        }


# ---------------------------------------------------------
# ✅ INTERNAL HELPERS (NOT EXPORTED)
# ---------------------------------------------------------


def _format_summary_result(data, search_request, count, usage):
    with logfire.span("format_summary_result"):
        return {
            "search_criteria": search_request.model_dump(),
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
            "usage_stats": get_usage_stats(usage),
            "generated_at": _timestamp(),
        }


def _create_empty_summary(search_request, message, usage):
    with logfire.span("create_empty_summary"):
        return {
            "search_criteria": search_request.model_dump(),
            "total_flights": 0,
            "summary_text": message,
            "key_insights": ["No flights available"],
            "recommendations": [
                "Try adjusting travel dates",
                "Consider nearby airports",
                "Check seasonal variations",
            ],
            "price_range": "N/A",
            "airlines": [],
            "direct_flights": 0,
            "connecting_flights": 0,
            "best_deal": None,
            "best_timing": None,
            "usage_stats": get_usage_stats(usage),
            "generated_at": _timestamp(),
        }


def _create_fallback_summary(search_request, flights, usage):
    with logfire.span("create_fallback_summary"):
        with logfire.span("calculate_fallback_metrics"):
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
            "search_criteria": search_request.model_dump(),
            "total_flights": len(flights),
            "summary_text": text,
            "key_insights": [
                f"Airlines: {', '.join(airlines[:3])}",
                f"Price range: ${min(prices):.0f}–${max(prices):.0f}",
                f"{direct} direct flights",
            ],
            "recommendations": [
                "Compare prices across airlines",
                "Choose direct flights for shorter travel",
                "Book early to save money",
            ],
            "price_range": f"${min(prices):.0f}–${max(prices):.0f}",
            "airlines": airlines,
            "direct_flights": direct,
            "connecting_flights": len(flights) - direct,
            "best_deal": min(flights, key=lambda x: x.price).model_dump(),
            "best_timing": flights[0].model_dump(),
            "usage_stats": get_usage_stats(usage),
            "generated_at": _timestamp(),
        }


def _perform_basic_comparison(flights):
    with logfire.span("perform_basic_comparison"):
        with logfire.span("find_cheapest_flight"):
            cheapest = min(flights, key=lambda f: f.price)

        return {
            "cheapest_option": cheapest.model_dump(),
            "price_range": {
                "min": min(f.price for f in flights),
                "max": max(f.price for f in flights),
            },
            "total_flights": len(flights),
            "unique_airlines": len({f.airline for f in flights}),
        }


def _filter_flights(flights, traveler_type):
    with logfire.span("filter_flights"):
        if traveler_type == "budget":
            return sorted(flights, key=lambda x: x.price)[:10]
        if traveler_type in {"business", "comfort", "family"}:
            directs = [f for f in flights if f.stops == 0]
            return sorted(directs or flights, key=lambda x: x.price)[:10]
        return flights[:10]


def _traveler_recommendations(flights, traveler_type, req):
    with logfire.span("generate_traveler_recommendations"):
        if not flights:
            return ["No suitable flights found"]

        with logfire.span("analyze_flight_recommendations"):
            cheapest = min(flights, key=lambda x: x.price)
            recs = []

            if traveler_type == "budget":
                recs.append(
                    f"Choose {cheapest.airline} at ${cheapest.price} for best savings"
                )

            if traveler_type in {"business", "comfort", "family"}:
                directs = [f for f in flights if f.stops == 0]
                if directs:
                    best = min(directs, key=lambda x: x.price)
                    recs.append(f"Direct flight recommended: {best.airline}")

            recs.extend(
                [
                    "Compare baggage policies",
                    "Verify travel documentation",
                    "Consider travel insurance",
                ]
            )

        return recs
