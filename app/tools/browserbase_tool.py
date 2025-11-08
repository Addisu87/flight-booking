from time import sleep
from pydantic_ai.tools import tool
from playwright.sync_api import sync_playwright
from html2text import html2text
from app.utils.config import settings


@tool
def browserbase_tool(url: str) -> str:
    if not settings.BROWSERBASE_API_KEY:
        raise ValueError("BROWSERBASE_API_KEY is not set")
    
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.connect_over_cdp(
                f"wss://connect.browserbase.com?apiKey={settings.BROWSERBASE_API_KEY}"
            )
            context = browser.contexts[0]
            page = context.pages[0]
            
            # Navigate to the URL
            page.goto(url)
            
            # Wait for the flight search to finish (adjust timing as needed)
            sleep(25)
            
            # Extract and convert content to text
            content = html2text(page.content())
            browser.close()
            
            return content
    except Exception as e:
        return f"Error loading page: {str(e)}"