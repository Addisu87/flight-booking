from pydantic_ai.usage import RunUsage, UsageLimits

async def find_flight(deps: Deps, usage: RunUsage) -> FlightDetails | None:
    """Handles flight search and validation logic."""
    message_history: list[ModelMessage] | None = None
    
    for _ in range(3):
        prompt = Prompt.ask(
            f"Find me a flight from {deps.req_origin} to {deps.req_destination} on {deps.req_date}",
        )
        result = await flight_search_agent.run(
            prompt,
            deps=deps,
            usage=usage,
            message_history=message_history,
            usage_limits=usage_limits,
        )

        if isinstance(result.output, FlightDetails):
            return result.output
        else: 
            message_history = result.all_messages(
                output_tool_return_content='Please try again.'
            )


async def find_seat(usage: RunUsage) -> SeatPreference:
    """Handles seat selection with limited retries."""
    max_attempts = 3
    attempts = 0
    message_history: list[ModelMessage] | None = None

    while attempts < max_attempts:
        answer = Prompt.ask("What seat would you like? (e.g., 12A)")

        result = await seat_preference_agent.run(
            answer,
            message_history=message_history,
            usage=usage,
            usage_limits=usage_limits,
        )

        if isinstance(result.output, SeatPreference):
            return result.output
        else:
            print("Invalid seat selection. Try again.")
            message_history = result.all_messages()
            attempts += 1

    print("Max retries reached. Assigning default seat 10C.")
    return SeatPreference(row=10, seat="C")


async def buy_tickets(flight_details: FlightDetails, seat: SeatPreference):
    """Mock function to simulate purchasing a flight."""
    print(
        f"Purchasing flight {flight_details.flight_number} with seat {seat.row}{seat.seat}..."
    )
    
# restrict how many requests this app can make to the LLM
usage_limits = UsageLimits(request_limit=15)
