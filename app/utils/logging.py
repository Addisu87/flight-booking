import logfire
from app.utils.config import settings


def setup_logfire():
    """Initialize Logfire with configuration."""

    logfire.configure(
        token=settings.LOGFIRE_TOKEN,
        service_name=settings.APP_NAME,
        send_to_logfire=bool(settings.LOGFIRE_TOKEN),
    )

    # Instrument everything
    logfire.instrument_pydantic()
    logfire.instrument_httpx()
    logfire.instrument_pydantic_ai()

    return logfire
