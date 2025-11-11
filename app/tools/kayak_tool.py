import logfire
from app.models.flight_models import FlightSearchRequest


def kayak_search_tool(search_request: FlightSearchRequest) -> str:
    with logfire.span("kayak_url_generation"):
        # Ensure dates are formatted correctly
        departure = search_request.departure_date.strftime("%Y-%m-%d")
        return_date = (
            search_request.return_date.strftime("%Y-%m-%d")
            if search_request.return_date
            else None
        )

        # Base Kayak URL
        url = f"https://www.kayak.com/flights/{search_request.origin}-{search_request.destination}/{departure}"

        # Add return date if round-trip
        if return_date:
            url += f"/{return_date}"

        # Sorting + currency params
        url += "?sort=bestflight_a&currency=USD"

        # Logfire tracking
        logfire.debug(
            "Generated Kayak URL",
            kayak_url=url,
            origin=search_request.origin,
            destination=search_request.destination,
            departure_date=departure,
            return_date=return_date,
        )

        return url
