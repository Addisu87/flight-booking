import logfire
import requests
import time
from html2text import html2text
from app.utils.config import settings

APIFY_ACTOR_ID = "apify/website-content-crawler"


def apify_browser_tool(url: str) -> str:
    if not settings.APIFY_API_TOKEN:
        logfire.error("APIFY_API_TOKEN missing")
        return ""

    with logfire.span("apify_navigation", url=url):
        try:
            start = requests.post(
                f"https://api.apify.com/v2/actors/{APIFY_ACTOR_ID}/runs",
                json={"startUrls": [{"url": url}]},
                params={"token": settings.APIFY_API_TOKEN},
                timeout=30,
            )

            if start.status_code != 200:
                logfire.error("Apify run start failed", status=start.status_code)
                return ""

            run_id = start.json()["data"]["id"]

            # Poll
            for _ in range(20):
                status = requests.get(
                    f"https://api.apify.com/v2/actor-runs/{run_id}",
                    params={"token": settings.APIFY_API_TOKEN},
                    timeout=10,
                ).json()

                if status["data"]["status"] in (
                    "SUCCEEDED",
                    "FAILED",
                    "ABORTED",
                    "TIMED_OUT",
                ):
                    break

                time.sleep(8)

            if status["data"]["status"] != "SUCCEEDED":
                logfire.error(
                    "Apify run did not succeed", status=status["data"]["status"]
                )
                return ""

            dataset_id = status["data"]["defaultDatasetId"]

            items = requests.get(
                f"https://api/apify.com/v2/datasets/{dataset_id}/items",
                params={"token": settings.APIFY_API_TOKEN},
                timeout=15,
            ).json()

            html = items[0].get("html") or items[0].get("pageContent") or ""
            return html2text(html)

        except Exception as e:
            logfire.error("Exception during apify_browser_tool", error=str(e))
            return ""
