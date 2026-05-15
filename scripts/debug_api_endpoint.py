"""Debug: test gpt-5.4-pro with different API endpoints.

GPT-5.4-Pro deployed via Azure Foundry ("Direct from Azure") may use the
Responses API instead of Chat Completions.
"""
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


async def test_endpoint(
    client: httpx.AsyncClient, path: str, body: dict, label: str
) -> None:
    url = f"{ENDPOINT}{path}"
    print(f"\n--- {label} ---")
    print(f"URL: {url}")
    try:
        resp = await client.post(url, json=body, headers=HEADERS, timeout=30)
        print(f"Status: {resp.status_code}")
        text = resp.text[:600]
        print(f"Body: {text}")
    except Exception as exc:
        print(f"Error: {type(exc).__name__}: {exc}")


async def main():
    print(f"Deployment: {DEPLOYMENT}")
    print(f"Endpoint: {ENDPOINT}")
    print(f"API Version: {API_VERSION}")

    async with httpx.AsyncClient() as client:
        # 1. Standard Chat Completions (known to fail)
        await test_endpoint(
            client,
            f"/openai/deployments/{DEPLOYMENT}/chat/completions?api-version={API_VERSION}",
            {"messages": [{"role": "user", "content": "Say hi"}], "max_completion_tokens": 10},
            "Chat Completions (deployment-scoped)",
        )

        # 2. Responses API (deployment-scoped)
        await test_endpoint(
            client,
            f"/openai/deployments/{DEPLOYMENT}/responses?api-version={API_VERSION}",
            {"input": "Say hi", "max_output_tokens": 10},
            "Responses API (deployment-scoped)",
        )

        # 3. Responses API with model param
        await test_endpoint(
            client,
            f"/openai/responses?api-version={API_VERSION}",
            {"model": DEPLOYMENT, "input": "Say hi", "max_output_tokens": 10},
            "Responses API (model-routed)",
        )

        # 4. Responses API with tools
        await test_endpoint(
            client,
            f"/openai/deployments/{DEPLOYMENT}/responses?api-version={API_VERSION}",
            {
                "input": "What is the weather in Paris?",
                "max_output_tokens": 100,
                "tools": [
                    {
                        "type": "function",
                        "function": {
                            "name": "get_weather",
                            "description": "Get current weather",
                            "parameters": {
                                "type": "object",
                                "properties": {
                                    "city": {"type": "string", "description": "City name"}
                                },
                                "required": ["city"],
                            },
                        },
                    }
                ],
            },
            "Responses API (with tools)",
        )

        # 5. Chat Completions model-routed
        await test_endpoint(
            client,
            f"/openai/chat/completions?api-version={API_VERSION}",
            {"model": DEPLOYMENT, "messages": [{"role": "user", "content": "Say hi"}], "max_completion_tokens": 10},
            "Chat Completions (model-routed)",
        )

        # 6. Responses API with 2025-03-01-preview
        await test_endpoint(
            client,
            f"/openai/deployments/{DEPLOYMENT}/responses?api-version=2025-03-01-preview",
            {"input": "Say hi", "max_output_tokens": 10},
            "Responses API (2025-03-01-preview)",
        )


if __name__ == "__main__":
    asyncio.run(main())
