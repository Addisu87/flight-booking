import asyncio
import logfire
from playwright.async_api import async_playwright
from html2text import html2text
from app.utils.config import settings
from browserbase import Browserbase

# Session cache for connection reuse
_session_cache = {}


async def browserbase_tool(url: str, wait_time: int = 20) -> str:
    """Asynchronous Browserbase tool for scraping dynamic web pages."""

    if not settings.BROWSERBASE_API_KEY or not settings.BROWSERBASE_PROJECT_ID:
        raise ValueError("Browserbase credentials not configured")

    with logfire.span("browserbase_scraping", url=url):
        try:
            # Initialize or reuse session
            if "session" not in _session_cache:
                logfire.info("Creating new Browserbase session")
                bb = Browserbase(api_key=settings.BROWSERBASE_API_KEY)
                session = bb.sessions.create(project_id=settings.BROWSERBASE_PROJECT_ID)
                _session_cache["session"] = session
            else:
                session = _session_cache["session"]
                logfire.info("Reusing Browserbase session", session_id=session.id)

            # Scrape page asynchronously
            async with async_playwright() as playwright:
                chromium = playwright.chromium
                browser = await chromium.connect_over_cdp(session.connect_url)
                context = browser.contexts[0]
                page = context.pages[0]

                logfire.info("Navigating to URL", url=url)
                await page.goto(url, wait_until="networkidle")
                await asyncio.sleep(wait_time)

                content = html2text(await page.content())
                logfire.info("Successfully scraped page", length=len(content))
                return content

        except Exception as e:
            logfire.error("Browserbase scraping failed", error=str(e), exc_info=True)
            # Clear cache on error to force new session next time
            _session_cache.pop("session", None)
            return f"Error: {str(e)}"
