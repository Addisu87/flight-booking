import logfire
from time import sleep
from playwright.sync_api import sync_playwright
from html2text import html2text
from app.utils.config import settings
from browserbase import Browserbase

session_cache = {}

def browserbase_tool(url: str, wait_time: int = 25) -> str:
    if not settings.BROWSERBASE_API_KEY or not settings.BROWSERBASE_PROJECT_ID:
        raise ValueError("Browserbase API key or project ID not set")

    with logfire.span("browserbase_navigation", url=url):
        try:
            if 'session' not in session_cache:
                logfire.info("Creating new Browserbase session")
                bb = Browserbase(api_key=settings.BROWSERBASE_API_KEY)
                session = bb.sessions.create(project_id=settings.BROWSERBASE_PROJECT_ID)
                session_cache['session'] = session
            else:
                session = session_cache['session']
                logfire.info("Reusing existing Browserbase session", session_id=session.id)

            with sync_playwright() as playwright:
                chromium = playwright.chromium
                browser = chromium.connect_over_cdp(session.connect_url)

                context = browser.contexts[0]
                page = context.pages[0]

                logfire.info("Navigating to URL", url=url)
                page.goto(url)
                sleep(wait_time)

                content = html2text(page.content())

                logfire.info("Successfully loaded page", url=url)
                return content

        except Exception as e:
            logfire.error("Browserbase navigation failed", error=str(e))
            return f"Error: {str(e)}"
