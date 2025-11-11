import logfire
from time import sleep
from playwright.sync_api import sync_playwright
from html2text import html2text
from app.utils.config import settings
from browserbase import Browserbase

def browserbase_tool(url: str, wait_time: int = 25) -> str:
    if not settings.BROWSERBASE_API_KEY:
        raise ValueError("BROWSERBASE_API_KEY is not set")

    with logfire.span("browserbase_navigation", url=url):
        # Initialize Browserbase (like the template)
        bb = Browserbase(api_key=settings.BROWSERBASE_API_KEY)
        
        try:
            # Create a session on Browserbase (like the template)
            session = bb.sessions.create(
                project_id=settings.BROWSERBASE_PROJECT_ID  
            )
            
            with sync_playwright() as playwright:
                # Connect to the remote session
                chromium = playwright.chromium
                browser = chromium.connect_over_cdp(session.connect_url)
                context = browser.contexts[0]
                page = context.pages[0]

                try:
                    # Execute Playwright actions on the remote browser tab
                    logfire.info("Navigating to URL", url=url)
                    page.goto(url)

                    # Wait for content to load
                    logfire.info(f"Waiting {wait_time} seconds for content to load")
                    sleep(wait_time)

                    # Extract and convert content to text
                    content = html2text(page.content())
                    
                    # Optional: Take screenshot for debugging
                    # page.screenshot(path=f"screenshot_{hash(url)}.png")
                    
                    logfire.info("Successfully loaded page", url=url)
                    logfire.info("Replay available at", replay_url=f"https://browserbase.com/sessions/{session.id}")

                    return content
                    
                except Exception as e:
                    logfire.error("Error during page interaction", error=str(e))
                    return f"Error loading page: {str(e)}"
                finally:
                    # Clean up resources
                    page.close()
                    browser.close()

        except Exception as e:
            logfire.error("Browserbase session creation failed", error=str(e))
            return f"Error creating Browserbase session: {str(e)}"