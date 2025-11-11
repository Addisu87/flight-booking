import logfire
from app.models.flight_models import FlightSearchRequest


def kayak_search_tool(req: FlightSearchRequest) -> str:
    with logfire.span("kayak_url_generation"):
        departure = req.departure_date.strftime("%Y-%m-%d")
        url = f"https://www.kayak.com/flights/{req.origin}-{req.destination}/{departure}"

        if req.return_date:
            url += f"/{req.return_date.strftime('%Y-%m-%d')}"

        url += "?sort=bestflight_a&currency=USD"

        logfire.debug("Generated Kayak URL", kayak_url=url)
        return url
