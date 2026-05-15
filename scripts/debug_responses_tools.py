"""Confirm gpt-5.4-pro works with Responses API using the correct tool format."""
import asyncio
import os

import httpx
from dotenv import load_dotenv

load_dotenv()

ENDPOINT = os.environ["AZURE_OPENAI_ENDPOINT"].rstrip("/")
API_KEY = os.environ["AZURE_OPENAI_API_KEY"]
DEPLOYMENT = os.environ["AZURE_OPENAI_DEPLOYMENT_NAME"]
API_VERSION = os.environ.get("AZURE_OPENAI_API_VERSION", "2025-04-01-preview")
HEADERS = {"api-key": API_KEY, "Content-Type": "application/json"}


async def main():
    url = f"{ENDPOINT}/openai/responses?api-version={API_VERSION}"

    async with httpx.AsyncClient() as client:
        # Responses API flat tool format
        body = {
            "model": DEPLOYMENT,
            "input": "What is the weather in Paris?",
            "max_output_tokens": 200,
            "tools": [
                {
                    "type": "function",
                    "name": "get_weather",
                    "description": "Get current weather for a city",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "city": {
                                "type": "string",
                                "description": "City name",
                            }
                        },
                        "required": ["city"],
                    },
                }
            ],
        }
        resp = await client.post(url, json=body, headers=HEADERS, timeout=60)
        print(f"Status: {resp.status_code}")
        print(f"Body: {resp.text[:1200]}")


if __name__ == "__main__":
    asyncio.run(main())
