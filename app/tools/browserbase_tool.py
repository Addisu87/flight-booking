import logfire
from time import sleep
from playwright.sync_api import sync_playwright
from html2text import html2text
from app.utils.config import settings


def browserbase_tool(url: str) -> str:
    if not settings.BROWSERBASE_API_KEY:
        raise ValueError("BROWSERBASE_API_KEY is not set")

    with logfire.span("browserbase_navigation", url=url):
        try:
            with sync_playwright() as playwright:
                browser = playwright.chromium.connect_over_cdp(
                    f"wss://connect.browserbase.com?apiKey={settings.BROWSERBASE_API_KEY}"
                )

                # Create new context for isolation
                context = browser.contexts[0]
                page = context.pages[0]

                # Navigate to the URL
                logfire.info("Navigating to URL", url=url)
                page.goto(url)

                # Wait for the flight search to finish (adjust timing as needed)
                sleep(25)

                # Extract and convert content to text
                content = html2text(page.content())
                browser.close()

                logfire.info("Successfully loaded page", url=url)

                return content
        except Exception as e:
            return f"Error loading page: {str(e)}"
