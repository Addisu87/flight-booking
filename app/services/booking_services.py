"""
Booking Service
==============

Handles flight booking operations including:
- Seat selection with retry logic
- Ticket purchase simulation
- Complete booking workflow

Integrates with:
- seat_agent.py for seat selection
- flight_service.py for flight search
- flight_models.py for data models
"""

import asyncio
import random
import string
from typing import Optional, List, Dict, Tuple
from datetime import datetime
from pydantic_ai.usage import RunUsage, UsageLimits
from pydantic_ai.messages import ModelMessage
from rich.prompt import Prompt
import logfire

from app.agents.seat_agent import seat_selection_agent
from app.models.flight_models import (
    FlightDetails,
    FlightSearchRequest,
    SeatPreference,
    SeatSelectionFailed
)
from app.utils.config import settings

# Import flight service functions
from app.services.flight_service import search_flights, create_usage_tracker

# Global usage limits for booking operations
booking_usage_limits = UsageLimits(request_limit=10)


@logfire.instrument("select_seat_with_retry", extract_args=True)
async def select_seat_with_retry(
    usage: RunUsage,
    max_attempts: int = 3,
    user_prompt: Optional[str] = None,
    message_history: Optional[List[ModelMessage]] = None
) -> Tuple[SeatPreference, List[ModelMessage], RunUsage]:
    """
    Select a seat with retry logic and intelligent parsing.
    
    Args:
        usage: Usage tracker for API calls
        max_attempts: Maximum number of selection attempts (default: 3)
        user_prompt: Optional pre-provided seat preference
        message_history: Previous message history for context
    
    Returns:
        Tuple containing:
        - Selected SeatPreference (or default fallback)
        - Updated message history
        - Updated usage tracker
    """
    current_message_history = message_history.copy() if message_history else []
    current_usage = usage
    
    for attempt in range(1, max_attempts + 1):
        seat, new_message_history, new_usage = await _execute_single_seat_selection_attempt(
            current_message_history, current_usage, attempt, max_attempts, user_prompt
        )
        
        current_message_history = new_message_history
        current_usage = new_usage
        
        if seat:
            logfire.info(
                "Seat selection successful",
                attempt=attempt,
                seat=str(seat),
                seat_type=seat.seat_type.value,
                has_extra_legroom=seat.has_extra_legroom
            )
            return seat, current_message_history, current_usage
    
    # Fallback to default seat after all attempts
    default_seat = _get_default_seat_fallback(max_attempts)
    return default_seat, current_message_history, current_usage


async def _execute_single_seat_selection_attempt(
    message_history: List[ModelMessage],
    usage: RunUsage,
    attempt: int,
    max_attempts: int,
    user_prompt: Optional[str] = None
) -> Tuple[Optional[SeatPreference], List[ModelMessage], RunUsage]:
    """
    Execute a single seat selection attempt with the seat selection agent.
    """
    with logfire.span("seat_selection_attempt", attempt=attempt):
        # Get user input
        answer = _get_seat_preference_input(attempt, max_attempts, user_prompt)
        
        if not answer:
            return None, message_history, usage
        
        logfire.debug("Processing seat selection", user_input=answer, attempt=attempt)
        
        try:
            result = await seat_selection_agent.run(
                answer,
                message_history=message_history.copy() if message_history else None,
                usage=usage,
                usage_limits=booking_usage_limits,
            )
            
            if isinstance(result.data, SeatPreference):
                return result.data, result.all_messages(), result.usage
            else:
                _handle_failed_seat_selection(result.data, attempt, max_attempts)
                return None, result.all_messages(), result.usage
                
        except Exception as e:
            logfire.error(
                "Seat selection agent error",
                error=str(e),
                attempt=attempt
            )
            return None, message_history, usage


def _get_seat_preference_input(
    attempt: int, 
    max_attempts: int, 
    user_prompt: Optional[str] = None
) -> str:
    """
    Get seat preference input from user with context-aware prompts.
    """
    if user_prompt and attempt == 1:
        return user_prompt
    
    if attempt == 1:
        prompt_text = (
            "What seat would you like? \n"
            "Examples: '12A', 'window seat', 'aisle seat row 5', 'extra legroom seat': "
        )
    else:
        prompt_text = f"Attempt {attempt}/{max_attempts} - Please specify your seat preference: "
    
    try:
        return Prompt.ask(prompt_text).strip()
    except (KeyboardInterrupt, EOFError):
        logfire.info("Seat selection cancelled by user")
        return ""


def _handle_failed_seat_selection(
    failed_result: SeatSelectionFailed, 
    attempt: int, 
    max_attempts: int
):
    """
    Handle failed seat selection with user-friendly messaging.
    """
    logfire.warning(
        "Seat selection failed",
        reason=failed_result.reason,
        user_input=failed_result.user_input,
        attempt=attempt
    )
    
    print(f"❌ {failed_result.reason}")
    
    if attempt < max_attempts:
        print("💡 Tips: Use format '12A' or describe like 'window seat row 10'")
        print("   Seats: A/F=Window, C/D=Aisle, B/E=Middle")
        print("   Extra legroom: Rows 1, 14, 20")


def _get_default_seat_fallback(max_attempts: int) -> SeatPreference:
    """
    Get default seat assignment when all selection attempts fail.
    """
    default_seat = SeatPreference(row=10, seat="C")
    
    logfire.info(
        "Using default seat after failed attempts",
        default_seat=str(default_seat),
        max_attempts=max_attempts
    )
    
    print(f"⚠️  Max retries reached. Assigning default seat {default_seat}.")
    print("   This is an aisle seat with standard legroom.")
    
    return default_seat


@logfire.instrument("buy_tickets", extract_args=True)
async def buy_tickets(
    flight_details: FlightDetails, 
    seat: SeatPreference
) -> Dict[str, str]:
    """
    Simulate ticket purchase with confirmation details.
    
    Args:
        flight_details: Selected flight details
        seat: Selected seat preference
    
    Returns:
        Dictionary with purchase confirmation details
    """
    with logfire.span("ticket_purchase"):
        confirmation_number = _generate_confirmation_number()
        purchase_time = datetime.now().isoformat()
        
        purchase_data = {
            "flight_number": flight_details.flight_number,
            "airline": flight_details.airline,
            "seat": str(seat),
            "price": flight_details.price,
            "confirmation_number": confirmation_number,
            "status": "confirmed",
            "route": f"{flight_details.origin} → {flight_details.destination}",
            "date": str(flight_details.date),
            "departure_time": flight_details.departure_time,
            "arrival_time": flight_details.arrival_time,
            "purchase_time": purchase_time,
            "passenger_count": 1,
            "seat_type": seat.seat_type.value,
            "has_extra_legroom": seat.has_extra_legroom
        }
        
        logfire.info(
            "Ticket purchase simulation completed",
            flight_number=purchase_data["flight_number"],
            seat=purchase_data["seat"],
            price=purchase_data["price"],
            confirmation_number=confirmation_number
        )
        
        _print_purchase_summary(purchase_data, seat)
        
        return purchase_data


def _print_purchase_summary(purchase_data: Dict, seat: SeatPreference):
    """
    Print a formatted purchase summary to the console.
    """
    print("\n" + "="*50)
    print("🎫 TICKET PURCHASE CONFIRMED")
    print("="*50)
    print(f"   ✈️  Flight: {purchase_data['airline']} {purchase_data['flight_number']}")
    print(f"   🛣️  Route: {purchase_data['route']}")
    print(f"   📅 Date: {purchase_data['date']}")
    print(f"   🕒 Time: {purchase_data['departure_time']} → {purchase_data['arrival_time']}")
    print(f"   💺 Seat: {seat.row}{seat.seat} ({seat.seat_type.value})")
    print(f"   💰 Price: ${purchase_data['price']}")
    print(f"   ✅ Confirmation: {purchase_data['confirmation_number']}")
    
    if seat.has_extra_legroom:
        print("   🦵 Note: Your seat has extra legroom!")
    
    if seat.seat_type.value == "window":
        print("   🌅 Enjoy the view!")
    elif seat.seat_type.value == "aisle":
        print("   🛣️ Easy access to the aisle!")
    
    print("="*50)
    print("📧 A confirmation email has been sent to your registered email.")
    print("Thank you for choosing FlightFinder Pro! ✈️")


def _generate_confirmation_number() -> str:
    """
    Generate a realistic confirmation number.
    """
    letters = ''.join(random.choices(string.ascii_uppercase, k=3))
    numbers = ''.join(random.choices(string.digits, k=3))
    return f"{letters}{numbers}"


@logfire.instrument("complete_booking_workflow", extract_args=True)
async def complete_booking_workflow(
    search_request: FlightSearchRequest,
    available_flights: List[FlightDetails],
    seat_preference_prompt: Optional[str] = None,
    max_seat_retries: int = 3
) -> Dict:
    """
    Complete flight booking workflow from search to purchase.
    
    Args:
        search_request: The flight search criteria
        available_flights: List of available flights to choose from
        seat_preference_prompt: Optional initial seat preference
        max_seat_retries: Maximum retries for seat selection (default: 3)
    
    Returns:
        Dictionary with booking confirmation details and status
    """
    usage = create_usage_tracker()
    message_history = create_message_history()
    
    try:
        # Validate inputs
        if not available_flights:
            return _create_error_result("No available flights provided", usage)
        
        # Step 1: Search for flight using flight_service
        logfire.info("Starting flight search", 
                    search_request=search_request.dict(),
                    available_flights_count=len(available_flights))
        
        flight_result = await search_flights(search_request, usage)
        
        if hasattr(flight_result, 'message'):  # NoFlightFound
            return _create_error_result(flight_result.message, usage)
        
        # Extract flight from successful search result
        flight = _extract_flight_from_search_result(flight_result, available_flights)
        if not flight:
            return _create_error_result("No suitable flight found in search results", usage)
        
        # Step 2: Select seat
        logfire.info("Starting seat selection", 
                    flight_number=flight.flight_number,
                    airline=flight.airline)
        
        seat, message_history, usage = await select_seat_with_retry(
            usage, max_seat_retries, seat_preference_prompt, message_history
        )
        
        # Step 3: Purchase tickets
        logfire.info("Initiating ticket purchase", 
                    flight_number=flight.flight_number, 
                    seat=str(seat))
        
        purchase_result = await buy_tickets(flight, seat)
        
        # Combine results
        final_result = {
            **purchase_result,
            "status": "success",
            "usage_stats": get_usage_stats(usage),
            "search_criteria": search_request.dict(),
            "workflow_steps": {
                "seat_selection_attempts": max_seat_retries,
                "total_duration": usage.total_usage.total_duration
            }
        }
        
        logfire.info(
            "Booking completed successfully",
            confirmation_number=purchase_result["confirmation_number"],
            total_usage=get_usage_stats(usage)
        )
        
        return final_result
        
    except Exception as e:
        logfire.error("Booking workflow failed", error=str(e))
        return _create_error_result(str(e), usage)


def _extract_flight_from_search_result(
    search_result: FlightSearchResult, 
    available_flights: List[FlightDetails]
) -> Optional[FlightDetails]:
    """
    Extract the best flight from search results.
    """
    if not search_result.flights:
        return None
    
    # Use the best value flight if available, otherwise first flight
    best_flight = search_result.best_value_flight or search_result.flights[0]
    
    # Find matching flight in available flights
    for flight in available_flights:
        if (flight.airline == best_flight.airline and 
            flight.flight_number == best_flight.flight_number):
            return flight
    
    return available_flights[0] if available_flights else None


def _create_error_result(reason: str, usage: RunUsage) -> Dict:
    """
    Create a standardized error result dictionary.
    """
    return {
        "status": "error", 
        "reason": reason,
        "usage_stats": get_usage_stats(usage),
        "confirmation_number": None,
        "timestamp": datetime.now().isoformat()
    }


@logfire.instrument("quick_booking", extract_args=True)
async def quick_booking(
    origin: str,
    destination: str,
    departure_date: str,
    available_flights: List[FlightDetails],
    seat_preference: Optional[str] = None,
    passengers: int = 1,
    flight_class: str = "economy"
) -> Dict:
    """
    Simplified booking function for common use cases.
    
    Args:
        origin: Departure airport code (3 letters)
        destination: Arrival airport code (3 letters)
        departure_date: Flight date in YYYY-MM-DD format
        available_flights: List of available flights
        seat_preference: Optional seat preference string
        passengers: Number of passengers (default: 1)
        flight_class: Flight class (default: "economy")
    
    Returns:
        Booking result dictionary
    """
    # Parse date if string
    if isinstance(departure_date, str):
        try:
            departure_date = datetime.strptime(departure_date, "%Y-%m-%d").date()
        except ValueError:
            return _create_error_result(
                f"Invalid date format: {departure_date}. Use YYYY-MM-DD.", 
                create_usage_tracker()
            )
    
    search_request = FlightSearchRequest(
        origin=origin.upper(),
        destination=destination.upper(),
        departure_date=departure_date,
        passengers=passengers,
        flight_class=flight_class
    )
    
    return await complete_booking_workflow(
        search_request=search_request,
        available_flights=available_flights,
        seat_preference_prompt=seat_preference
    )


# Utility Functions
def create_message_history() -> List[ModelMessage]:
    """
    Create an empty message history list.
    """
    return []


def clear_message_history(message_history: List[ModelMessage]) -> List[ModelMessage]:
    """
    Clear message history and return empty list.
    """
    message_history.clear()
    return message_history


def get_usage_stats(usage: RunUsage) -> Dict:
    """
    Extract usage statistics from RunUsage object.
    """
    return {
        "total_requests": usage.total_usage.request_count,
        "total_tokens": usage.total_usage.total_tokens,
        "total_duration": usage.total_usage.total_duration,
        "cost_estimate": _estimate_cost(usage.total_usage.total_tokens)
    }


def _estimate_cost(total_tokens: int) -> float:
    """
    Estimate cost based on token usage (approximate).
    """
    # Rough estimate: $0.01 per 1K tokens for input, $0.03 for output
    # Using average of $0.02 per 1K tokens
    return (total_tokens / 1000) * 0.02


# Integration with other services
@logfire.instrument("validate_booking_eligibility", extract_args=True)
async def validate_booking_eligibility(flight: FlightDetails) -> Tuple[bool, str]:
    """
    Validate if a flight can be booked (mock implementation).
    
    Args:
        flight: Flight to validate
    
    Returns:
        Tuple of (is_eligible, reason)
    """
    # Mock validation checks
    if flight.price <= 0:
        return False, "Invalid flight price"
    
    if not all([flight.airline, flight.flight_number, flight.origin, flight.destination]):
        return False, "Incomplete flight information"
    
    # Check if flight date is in the future
    if flight.date < datetime.now().date():
        return False, "Flight date is in the past"
    
    return True, "Flight is eligible for booking"


@logfire.instrument("get_booking_status", extract_args=True)
async def get_booking_status(confirmation_number: str) -> Dict:
    """
    Mock function to get booking status by confirmation number.
    
    Args:
        confirmation_number: Booking confirmation number
    
    Returns:
        Dictionary with booking status information
    """
    # Mock implementation - in real scenario, this would query a database
    statuses = ["confirmed", "pending", "cancelled"]
    status = random.choice(statuses)
    
    return {
        "confirmation_number": confirmation_number,
        "status": status,
        "last_updated": datetime.now().isoformat(),
        "can_modify": status == "confirmed",
        "can_cancel": status == "confirmed"
    }