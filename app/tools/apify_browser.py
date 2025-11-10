import logfire
import requests
from html2text import html2text
from app.utils.config import settings

APIFY_ACTOR_ID = "apify/website-content-crawler"


def apify_browser_tool(url: str) -> str:
    if not settings.APIFY_API_TOKEN:
        raise ValueError("APIFY_API_TOKEN is not set")

    with logfire.span("apify_navigation", url=url):
        try:
            logfire.info("Starting Apify crawl", url=url)

            # Start the Actor run
            run = requests.post(
                f"https://api.apify.com/v2/actor-tasks/{APIFY_ACTOR_ID}/runs",
                json={"startUrls": [{"url": url}]},
                params={"token": settings.APIFY_API_TOKEN},
            ).json()

            run_id = run["data"]["id"]

            # Poll until finished
            while True:
                status = requests.get(
                    f"https://api.apify.com/v2/actor-runs/{run_id}",
                    params={"token": settings.APIFY_API_TOKEN},
                ).json()
                
                if status["data"]["status"] in ["SUCCEEDED", "FAILED", "ABORTED"]:
                    break

            if status["data"]["status"] != "SUCCEEDED":
                return f"Apify run failed: {status['data']['status']}"

            # Get dataset results
            dataset_id = status["data"]["defaultDatasetId"]
            items = requests.get(
                f"https://api.apify.com/v2/datasets/{dataset_id}/items",
                params={"token": settings.APIFY_API_TOKEN},
            ).json()

            if not items:
                return "No content extracted from Apify."

            html = items[0].get("html", "")
            return html2text(html)

        except Exception as e:
            return f"Apify error: {str(e)}"
