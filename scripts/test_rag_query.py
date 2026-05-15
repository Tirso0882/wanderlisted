#!/usr/bin/env python
"""Quick RAG retrieval test — runs a query and shows results."""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dotenv import load_dotenv

load_dotenv()

from src.tools.destination_rag import search_destination_guides

# ── Test queries ─────────────────────────────────────────────────────────
TEST_QUERIES = [
    "best street food in Bangkok",
    "Wroclaw old town attractions",
    "budget hotels in Cancun",
    "Parisian cafes and restaurants",
    "Tokyo sightseeing temples",
    "how to get around London by train",
]


def main():
    print("=" * 70)
    print("  Wanderlisted — RAG Retrieval Test")
    print("=" * 70)
    print()

    for i, query in enumerate(TEST_QUERIES, 1):
        print(f'[Query {i}/{len(TEST_QUERIES)}] "{query}"')
        print("─" * 70)
        # search_destination_guides is an async @tool, so invoke it with asyncio
        result = asyncio.run(search_destination_guides.ainvoke({"query": query}))

        # Parse result to show source + section
        lines = result.split("\n\n---\n\n")
        for j, match in enumerate(lines, 1):
            # Extract source and section from the [i] prefix
            lines_in_match = match.split("\n", 1)
            header = lines_in_match[0]
            content = lines_in_match[1] if len(lines_in_match) > 1 else ""

            # Show snippet
            snippet = content[:150].replace("\n", " ") if content else ""
            print(f"  Match {j}: {header}")
            print(f"    {snippet}…")

        print()

    print("=" * 70)
    print("  Test Complete ✓")
    print("=" * 70)
    print("\nNext step: Run a full end-to-end test with the agent:")
    print("  python -m uvicorn src.api.main:app --reload")
    print()


if __name__ == "__main__":
    main()
