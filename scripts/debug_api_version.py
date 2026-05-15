"""Debug: test gpt-5.4-pro with different API versions and configurations."""
import asyncio
import os

import httpx
from dotenv import load_dotenv

load_dotenv()

ENDPOINT = os.environ["AZURE_OPENAI_ENDPOINT"].rstrip("/")
API_KEY = os.environ["AZURE_OPENAI_API_KEY"]
DEPLOYMENT = os.environ["AZURE_OPENAI_DEPLOYMENT_NAME"]
FAST_DEPLOYMENT = os.environ.get("AZURE_OPENAI_FAST_DEPLOYMENT_NAME", "")

API_VERSIONS = [
    "2025-04-01-preview",
    "2025-03-01-preview",
    "2024-12-01-preview",
    "2024-10-21",
    "2024-08-01-preview",
    "2024-06-01",
    "2025-04-14",
]

BODY = {
    "messages": [{"role": "user", "content": "Say hi"}],
    "max_tokens": 10,
}


async def test_version(
    client: httpx.AsyncClient, deployment: str, api_version: str
) -> str:
    url = (
        f"{ENDPOINT}/openai/deployments/{deployment}"
        f"/chat/completions?api-version={api_version}"
    )
    headers = {"api-key": API_KEY, "Content-Type": "application/json"}
    try:
        resp = await client.post(url, json=BODY, headers=headers, timeout=30)
        if resp.status_code == 200:
            data = resp.json()
            content = data["choices"][0]["message"]["content"]
            return f"OK ({resp.status_code}) — {content[:50]}"
        else:
            body = resp.text[:200]
            return f"FAIL ({resp.status_code}) — {body}"
    except Exception as exc:
        return f"ERROR — {type(exc).__name__}: {exc}"


async def main():
    async with httpx.AsyncClient() as client:
        print(f"Deployment: {DEPLOYMENT}")
        print(f"Endpoint: {ENDPOINT}\n")

        for version in API_VERSIONS:
            result = await test_version(client, DEPLOYMENT, version)
            print(f"  {DEPLOYMENT} + {version}: {result}")

        if FAST_DEPLOYMENT:
            print(f"\nFast deployment: {FAST_DEPLOYMENT}\n")
            # Only test current version for fast (we know it works)
            result = await test_version(
                client, FAST_DEPLOYMENT, "2025-04-01-preview"
            )
            print(f"  {FAST_DEPLOYMENT} + 2025-04-01-preview: {result}")


if __name__ == "__main__":
    asyncio.run(main())
