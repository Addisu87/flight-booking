from typing import List, Dict, Optional
from pydantic_ai.usage import RunUsage
import logfire

from app.agents.summarize_agent import summarize_agent, SummarizeDeps
from app.models.flight_models import FlightDetails, FlightSearchRequest
from app.utils.config import settings


@logfire.instrument("generate_flight_summary", extract_args=True)
async def generate_flight_summary(
    search_request: FlightSearchRequest,
    flights: List[FlightDetails],
    usage: Optional[RunUsage] = None,
    include_recommendations: bool = True,
    include_insights: bool = True
) -> Dict:
    """
    Generate a comprehensive summary of flight search results.
    
    Args:
        search_request: Original search criteria
        flights: List of found flights
        usage: Optional usage tracker
        include_recommendations: Whether to include AI recommendations
        include_insights: Whether to include key insights
    
    Returns:
        Dictionary with summary, insights, and recommendations
    
    Example:
        >>> summary = await generate_flight_summary(search_request, flights)
        >>> print(summary['summary_text'])
    """
    current_usage = usage or RunUsage()
    
    if not flights:
        return _create_empty_summary(search_request, "No flights found for the search criteria.")
    
    try:
        # Use the existing summarize agent with our flights
        context = SummarizeDeps(
            search_request=search_request,
            all_flights=flights,
            search_metadata={
                'include_recommendations': include_recommendations,
                'include_insights': include_insights
            }
        )
        
        result = await summarize_agent.run(
            "Generate a comprehensive flight search summary with insights and recommendations",
            deps=context,
            usage=current_usage
        )
        
        summary_data = result.data
        
        # Convert to dictionary format for consistency
        return _format_summary_result(summary_data, search_request, len(flights), current_usage)
        
    except Exception as e:
        logfire.error("Summary generation failed", error=str(e))
        return _create_fallback_summary(search_request, flights, current_usage)


def _format_summary_result(summary_data, search_request: FlightSearchRequest, total_flights: int, usage: RunUsage) -> Dict:
    """Format the summary result into a consistent dictionary format."""
    return {
        'search_criteria': search_request.dict(),
        'total_flights': total_flights,
        'summary_text': getattr(summary_data, 'summary_text', ''),
        'key_insights': getattr(summary_data, 'key_insights', []),
        'recommendations': getattr(summary_data, 'recommendations', []),
        'price_range': getattr(summary_data, 'price_range', ''),
        'airlines': getattr(summary_data, 'airlines', []),
        'direct_flights': getattr(summary_data, 'direct_flights', 0),
        'connecting_flights': getattr(summary_data, 'connecting_flights', 0),
        'best_deal': getattr(summary_data, 'best_deal', None),
        'best_timing': getattr(summary_data, 'best_timing', None),
        'usage_stats': _get_usage_stats(usage),
        'generated_at': _get_current_timestamp()
    }


def _create_empty_summary(search_request: FlightSearchRequest, message: str) -> Dict:
    """Create an empty summary for no flights scenario."""
    return {
        'search_criteria': search_request.dict(),
        'total_flights': 0,
        'summary_text': message,
        'key_insights': ["No flights available for analysis"],
        'recommendations': [
            "Try adjusting your search dates",
            "Consider nearby airports",
            "Check for seasonal variations"
        ],
        'price_range': 'N/A',
        'airlines': [],
        'direct_flights': 0,
        'connecting_flights': 0,
        'best_deal': None,
        'best_timing': None,
        'usage_stats': {'total_requests': 0, 'total_tokens': 0, 'total_duration': 0},
        'generated_at': _get_current_timestamp()
    }


def _create_fallback_summary(search_request: FlightSearchRequest, flights: List[FlightDetails], usage: RunUsage) -> Dict:
    """Create a fallback summary when AI summarization fails."""
    if not flights:
        return _create_empty_summary(search_request, "No flights available for summary.")
    
    prices = [f.price for f in flights]
    airlines = list(set(f.airline for f in flights))
    direct_flights = len([f for f in flights if f.stops == 0])
    
    summary_text = f"""
    Found {len(flights)} flights from {search_request.origin} to {search_request.destination}.
    Prices range from ${min(prices):.0f} to ${max(prices):.0f} across {len(airlines)} airlines.
    {direct_flights} direct flights available.
    """
    
    return {
        'search_criteria': search_request.dict(),
        'total_flights': len(flights),
        'summary_text': summary_text.strip(),
        'key_insights': [
            f"Multiple options available from {', '.join(airlines[:3])}",
            f"Price range: ${min(prices):.0f} - ${max(prices):.0f}",
            f"{direct_flights} direct flights available"
        ],
        'recommendations': [
            "Compare prices across different airlines",
            "Consider direct flights for time savings",
            "Book in advance for best prices"
        ],
        'price_range': f"${min(prices):.0f} - ${max(prices):.0f}",
        'airlines': airlines,
        'direct_flights': direct_flights,
        'connecting_flights': len(flights) - direct_flights,
        'best_deal': min(flights, key=lambda x: x.price) if flights else None,
        'best_timing': flights[0] if flights else None,  # Simple fallback
        'usage_stats': _get_usage_stats(usage),
        'generated_at': _get_current_timestamp()
    }


@logfire.instrument("generate_comparative_analysis", extract_args=True)
async def generate_comparative_analysis(
    flights: List[FlightDetails],
    usage: Optional[RunUsage] = None
) -> Dict:
    """
    Generate comparative analysis between multiple flight options.
    
    Args:
        flights: List of flights to compare
        usage: Optional usage tracker
    
    Returns:
        Dictionary with comparative analysis
    
    Example:
        >>> analysis = await generate_comparative_analysis(flights)
        >>> print(analysis['cheapest_option'])
    """
    current_usage = usage or RunUsage()
    
    if not flights:
        return {'error': 'No flights provided for analysis'}
    
    try:
        # Use basic analysis without AI for simple comparisons
        analysis = _perform_basic_comparative_analysis(flights)
        
        logfire.info(
            "Comparative analysis generated",
            flights_analyzed=len(flights),
            cheapest_price=analysis.get('cheapest_option', {}).get('price', 0)
        )
        
        analysis['usage_stats'] = _get_usage_stats(current_usage)
        return analysis
        
    except Exception as e:
        logfire.error("Comparative analysis failed", error=str(e))
        return {'error': str(e), 'usage_stats': _get_usage_stats(current_usage)}


def _perform_basic_comparative_analysis(flights: List[FlightDetails]) -> Dict:
    """Perform basic comparative analysis without AI."""
    if not flights:
        return {}
    
    # Find best options by different criteria
    cheapest = min(flights, key=lambda x: x.price)
    fastest = _find_fastest_flight(flights)
    best_direct = _find_best_direct_flight(flights)
    best_value = _find_best_value_flight(flights)
    
    # Airlines analysis
    airlines = list(set(f.airline for f in flights))
    airline_prices = {
        airline: min(f.price for f in flights if f.airline == airline)
        for airline in airlines
    }
    
    return {
        'cheapest_option': _flight_to_dict(cheapest),
        'fastest_option': _flight_to_dict(fastest) if fastest else None,
        'best_direct_option': _flight_to_dict(best_direct) if best_direct else None,
        'best_value_option': _flight_to_dict(best_value) if best_value else None,
        'airline_comparison': airline_prices,
        'price_range': {
            'min': min(f.price for f in flights),
            'max': max(f.price for f in flights),
            'average': sum(f.price for f in flights) / len(flights)
        },
        'flight_statistics': {
            'total_flights': len(flights),
            'direct_flights': len([f for f in flights if f.stops == 0]),
            'connecting_flights': len([f for f in flights if f.stops > 0]),
            'unique_airlines': len(airlines)
        }
    }


def _find_fastest_flight(flights: List[FlightDetails]) -> Optional[FlightDetails]:
    """Find the flight with shortest duration."""
    try:
        return min(flights, key=lambda x: _parse_duration_to_minutes(x.duration))
    except:
        return None


def _find_best_direct_flight(flights: List[FlightDetails]) -> Optional[FlightDetails]:
    """Find the best direct flight (cheapest direct)."""
    direct_flights = [f for f in flights if f.stops == 0]
    return min(direct_flights, key=lambda x: x.price) if direct_flights else None


def _find_best_value_flight(flights: List[FlightDetails]) -> Optional[FlightDetails]:
    """Find the best value flight (balance of price and duration)."""
    if len(flights) < 2:
        return flights[0] if flights else None
    
    try:
        # Simple value calculation: lower price and shorter duration are better
        def value_score(flight):
            price_score = 1 / (flight.price + 1)  # Avoid division by zero
            duration_score = 1 / (_parse_duration_to_minutes(flight.duration) + 1)
            return price_score * 0.7 + duration_score * 0.3  # Weight price more heavily
        
        return max(flights, key=value_score)
    except:
        return min(flights, key=lambda x: x.price)  # Fallback to cheapest


def _parse_duration_to_minutes(duration_str: str) -> int:
    """Parse duration string to total minutes."""
    try:
        hours = 0
        minutes = 0
        if 'h' in duration_str:
            hours = int(duration_str.split('h')[0].strip())
        if 'm' in duration_str:
            min_part = duration_str.split('h')[1] if 'h' in duration_str else duration_str
            minutes = int(min_part.split('m')[0].strip())
        return hours * 60 + minutes
    except:
        return 0


def _flight_to_dict(flight: FlightDetails) -> Dict:
    """Convert FlightDetails to dictionary for JSON serialization."""
    return {
        'airline': flight.airline,
        'flight_number': flight.flight_number,
        'price': flight.price,
        'origin': flight.origin,
        'destination': flight.destination,
        'departure_time': flight.departure_time,
        'arrival_time': flight.arrival_time,
        'duration': flight.duration,
        'date': str(flight.date),
        'stops': flight.stops,
        'flight_class': flight.flight_class.value,
        'is_direct': flight.stops == 0
    }


@logfire.instrument("generate_travel_recommendations", extract_args=True)
async def generate_travel_recommendations(
    search_request: FlightSearchRequest,
    flights: List[FlightDetails],
    traveler_type: str = "general",
    usage: Optional[RunUsage] = None
) -> Dict:
    """
    Generate personalized travel recommendations based on flight options and traveler type.
    
    Args:
        search_request: Search criteria
        flights: Available flights
        traveler_type: Type of traveler ('budget', 'business', 'comfort', 'family')
        usage: Optional usage tracker
    
    Returns:
        Dictionary with personalized recommendations
    """
    current_usage = usage or RunUsage()
    
    if not flights:
        return {
            'traveler_type': traveler_type,
            'recommendations': ["No flights available for recommendations"],
            'suitable_flights': [],
            'usage_stats': _get_usage_stats(current_usage)
        }
    
    try:
        # Filter flights based on traveler type
        suitable_flights = _filter_flights_for_traveler(flights, traveler_type)
        
        # Generate recommendations
        recommendations = _generate_traveler_specific_recommendations(
            suitable_flights, traveler_type, search_request
        )
        
        logfire.info(
            "Travel recommendations generated",
            traveler_type=traveler_type,
            suitable_flights_count=len(suitable_flights),
            recommendations_count=len(recommendations)
        )
        
        return {
            'traveler_type': traveler_type,
            'recommendations': recommendations,
            'suitable_flights': [_flight_to_dict(f) for f in suitable_flights[:5]],  # Top 5
            'total_suitable_flights': len(suitable_flights),
            'usage_stats': _get_usage_stats(current_usage)
        }
        
    except Exception as e:
        logfire.error("Travel recommendations failed", error=str(e))
        return {
            'traveler_type': traveler_type,
            'recommendations': ["Error generating recommendations"],
            'suitable_flights': [],
            'usage_stats': _get_usage_stats(current_usage)
        }


def _filter_flights_for_traveler(flights: List[FlightDetails], traveler_type: str) -> List[FlightDetails]:
    """Filter flights based on traveler type preferences."""
    if traveler_type == "budget":
        # Prefer cheaper flights, don't care much about stops
        return sorted(flights, key=lambda x: x.price)[:10]  # Top 10 cheapest
    
    elif traveler_type == "business":
        # Prefer direct flights, morning departures, business class
        business_flights = [f for f in flights if f.stops == 0]
        if not business_flights:
            business_flights = flights
        return sorted(business_flights, key=lambda x: x.price)[:10]
    
    elif traveler_type == "comfort":
        # Prefer direct flights, more legroom rows, premium classes
        comfort_flights = [f for f in flights if f.stops == 0]
        if not comfort_flights:
            comfort_flights = flights
        return sorted(comfort_flights, key=lambda x: x.price)[:10]
    
    elif traveler_type == "family":
        # Prefer direct flights, reasonable prices, family-friendly timing
        family_flights = [f for f in flights if f.stops == 0]
        if not family_flights:
            family_flights = flights
        return sorted(family_flights, key=lambda x: x.price)[:10]
    
    else:  # general
        return flights[:10]  # Just return first 10


def _generate_traveler_specific_recommendations(
    flights: List[FlightDetails], 
    traveler_type: str,
    search_request: FlightSearchRequest
) -> List[str]:
    """Generate recommendations specific to traveler type."""
    recommendations = []
    
    if not flights:
        return ["No suitable flights found for your preferences"]
    
    cheapest = min(flights, key=lambda x: x.price)
    direct_flights = [f for f in flights if f.stops == 0]
    
    if traveler_type == "budget":
        recommendations.extend([
            f"Choose {cheapest.airline} at ${cheapest.price} for the best price",
            "Consider flights with stops for additional savings",
            "Book 3-4 weeks in advance for lowest prices"
        ])
    
    elif traveler_type == "business":
        if direct_flights:
            best_direct = min(direct_flights, key=lambda x: x.price)
            recommendations.extend([
                f"Take {best_direct.airline} direct flight for efficiency",
                "Morning flights typically have better productivity time",
                "Consider business class for better comfort during work"
            ])
    
    elif traveler_type == "comfort":
        if direct_flights:
            best_direct = min(direct_flights, key=lambda x: x.price)
            recommendations.extend([
                f"Select {best_direct.airline} for a comfortable journey",
                "Choose aisle seats for easier movement",
                "Consider premium economy for extra comfort"
            ])
    
    elif traveler_type == "family":
        if direct_flights:
            best_family = min(direct_flights, key=lambda x: x.price)
            recommendations.extend([
                f"Fly {best_family.airline} direct to minimize travel stress",
                "Choose seats together when traveling with children",
                "Consider early morning flights for better child routines"
            ])
    
    # General recommendations for all types
    recommendations.extend([
        "Check baggage policies as they vary by airline",
        "Verify travel documentation requirements",
        "Consider travel insurance for peace of mind"
    ])
    
    return recommendations


@logfire.instrument("generate_quick_insights", extract_args=True)
def generate_quick_insights(flights: List[FlightDetails]) -> Dict:
    """
    Generate quick insights without AI for fast response times.
    
    Args:
        flights: List of flights to analyze
    
    Returns:
        Dictionary with basic insights
    """
    if not flights:
        return {'insights': ['No flights available for analysis']}
    
    prices = [f.price for f in flights]
    airlines = list(set(f.airline for f in flights))
    direct_flights = len([f for f in flights if f.stops == 0])
    
    insights = [
        f"Found {len(flights)} total flight options",
        f"Price range: ${min(prices):.0f} - ${max(prices):.0f}",
        f"Flying with {len(airlines)} different airlines",
        f"{direct_flights} direct flights available"
    ]
    
    # Add timing insights if we have time data
    morning_flights = len([f for f in flights if _is_morning_flight(f)])
    if morning_flights > 0:
        insights.append(f"{morning_flights} morning departure options")
    
    return {
        'insights': insights,
        'statistics': {
            'cheapest_price': min(prices),
            'most_expensive_price': max(prices),
            'average_price': sum(prices) / len(prices),
            'direct_flight_percentage': (direct_flights / len(flights)) * 100
        }
    }


def _is_morning_flight(flight: FlightDetails) -> bool:
    """Check if flight is a morning departure."""
    try:
        hour = int(flight.departure_time.split(':')[0])
        return 6 <= hour < 12
    except:
        return False


def _get_usage_stats(usage: RunUsage) -> Dict:
    """Extract usage statistics from RunUsage object."""
    return {
        "total_requests": usage.total_usage.request_count,
        "total_tokens": usage.total_usage.total_tokens,
        "total_duration": usage.total_usage.total_duration,
    }


def _get_current_timestamp() -> str:
    """Get current timestamp in ISO format."""
    from datetime import datetime
    return datetime.now().isoformat()


def create_usage_tracker() -> RunUsage:
    """Create a new usage tracker instance."""
    return RunUsage()


# Export main functions for easy access
__all__ = [
    'generate_flight_summary',
    'generate_comparative_analysis',
    'generate_travel_recommendations',
    'generate_quick_insights',
    'create_usage_tracker'
]