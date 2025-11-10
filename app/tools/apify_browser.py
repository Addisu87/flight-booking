import logfire
import requests
import time
from html2text import html2text
from app.utils.config import settings

# Use YOUR specific actor ID from the Apify console
APIFY_ACTOR_ID = "jupri/skyscanner-flight"


def apify_browser_tool(url: str) -> str:
    print(f"🔍 DEBUG: Starting Apify browser tool with URL: {url}")
    
    if not settings.APIFY_API_TOKEN:
        error_msg = "APIFY_API_TOKEN is not set"
        print(f"❌ DEBUG: {error_msg}")
        raise ValueError(error_msg)

    with logfire.span("apify_navigation", url=url):
        try:
            print("🔍 DEBUG: Starting Apify crawl")
            logfire.info("Starting Apify crawl", url=url)

            # Start YOUR custom actor
            print(f"🔍 DEBUG: Calling Apify API to start actor: {APIFY_ACTOR_ID}")
            
            # Use the correct API endpoint for your custom actor
            response = requests.post(
                f"https://api.apify.com/v2/actors/{APIFY_ACTOR_ID}/runs",  # Changed from actor-tasks to actors
                json={
                    "startUrls": [{"url": url}],
                    "waitForSelector": '[data-testid="flight-card"]'
                },
                params={"token": settings.APIFY_API_TOKEN},
                timeout=30
            )
            
            print(f"🔍 DEBUG: Apify start response status: {response.status_code}")
            print(f"🔍 DEBUG: Apify start response body: {response.text[:500]}")
            
            if response.status_code != 200:
                error_msg = f"Apify API returned status {response.status_code}: {response.text[:200]}"
                print(f"❌ DEBUG: {error_msg}")
                return error_msg
            
            run = response.json()
            print(f"🔍 DEBUG: Apify run created: {run}")
            
            run_id = run["data"]["id"]
            print(f"🔍 DEBUG: Run ID: {run_id}")

            # Poll until finished with timeout
            print("🔍 DEBUG: Starting to poll for run completion...")
            max_polls = 20  # 20 * 10 seconds = ~3 minutes max
            poll_count = 0
            
            for poll_count in range(max_polls):
                print(f"🔍 DEBUG: Polling attempt {poll_count + 1}/{max_polls}")
                
                status_response = requests.get(
                    f"https://api.apify.com/v2/actor-runs/{run_id}",
                    params={"token": settings.APIFY_API_TOKEN},
                    timeout=10
                )
                
                print(f"🔍 DEBUG: Status response status: {status_response.status_code}")
                
                if status_response.status_code != 200:
                    error_msg = f"Status check failed: {status_response.status_code}"
                    print(f"❌ DEBUG: {error_msg}")
                    return error_msg
                
                status = status_response.json()
                run_status = status["data"]["status"]
                print(f"🔍 DEBUG: Run status: {run_status}")
                
                if run_status in ["SUCCEEDED", "FAILED", "ABORTED", "TIMED_OUT"]:
                    print(f"🔍 DEBUG: Run finished with status: {run_status}")
                    break
                
                # Wait 10 seconds before next poll
                time.sleep(10)
            else:
                error_msg = f"Max polling attempts reached. Last status: {run_status}"
                print(f"❌ DEBUG: {error_msg}")
                return error_msg

            if run_status != "SUCCEEDED":
                error_msg = f"Apify run failed: {run_status}"
                if "statusMessage" in status["data"]:
                    error_msg += f" - {status['data']['statusMessage']}"
                print(f"❌ DEBUG: {error_msg}")
                return error_msg

            # Get dataset results
            dataset_id = status["data"]["defaultDatasetId"]
            print(f"🔍 DEBUG: Getting dataset items from ID: {dataset_id}")
            
            items_response = requests.get(
                f"https://api.apify.com/v2/datasets/{dataset_id}/items",
                params={"token": settings.APIFY_API_TOKEN},
                timeout=10
            )
            
            print(f"🔍 DEBUG: Items response status: {items_response.status_code}")
            
            if items_response.status_code != 200:
                error_msg = f"Failed to get dataset: {items_response.status_code}"
                print(f"❌ DEBUG: {error_msg}")
                return error_msg

            items = items_response.json()
            print(f"🔍 DEBUG: Got {len(items)} items from dataset")
            
            if not items:
                error_msg = "No content extracted from Apify."
                print(f"❌ DEBUG: {error_msg}")
                return error_msg

            # Extract content from the first item
            first_item = items[0]
            html = first_item.get("html", first_item.get("pageContent", ""))
            print(f"🔍 DEBUG: Extracted content length: {len(html)}")
            
            if not html:
                error_msg = "No HTML content in response"
                print(f"❌ DEBUG: {error_msg}")
                return error_msg
                
            text_content = html2text(html)
            print(f"🔍 DEBUG: Converted to text, length: {len(text_content)}")
            print(f"🔍 DEBUG: Text preview: {text_content[:200]}...")
            
            print("✅ DEBUG: Apify crawl completed successfully")
            return text_content

        except requests.exceptions.Timeout:
            error_msg = "Apify request timeout"
            print(f"❌ DEBUG: {error_msg}")
            return error_msg
        except requests.exceptions.ConnectionError:
            error_msg = "Apify connection error"
            print(f"❌ DEBUG: {error_msg}")
            return error_msg
        except Exception as e:
            error_msg = f"Apify error: {str(e)}"
            print(f"❌ DEBUG: Exception occurred: {error_msg}")
            print(f"❌ DEBUG: Exception type: {type(e).__name__}")
            import traceback
            print(f"❌ DEBUG: Traceback: {traceback.format_exc()}")
            return error_msg