"""Test gpt-5.4-pro via the Responses API with correct parameters."""
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
        # Test 1: Plain text
        body1 = {
            "model": DEPLOYMENT,
            "input": "Say hello in one word",
            "max_output_tokens": 50,
        }
        resp = await client.post(url, json=body1, headers=HEADERS, timeout=30)
        print(f"Test 1 (plain text): {resp.status_code}")
        print(f"Body: {resp.text[:600]}")

        # Test 2: With tools
        print()
        body2 = {
            "model": DEPLOYMENT,
            "input": "What is the weather in Paris?",
            "max_output_tokens": 200,
            "tools": [
                {
                    "type": "function",
                    "function": {
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
                    },
                }
            ],
        }
        resp2 = await client.post(url, json=body2, headers=HEADERS, timeout=30)
        print(f"Test 2 (with tools): {resp2.status_code}")
        print(f"Body: {resp2.text[:800]}")


if __name__ == "__main__":
    asyncio.run(main())
