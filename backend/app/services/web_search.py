"""Web search via DuckDuckGo (no API key required)."""
import asyncio
import logging
from typing import List

logger = logging.getLogger(__name__)


def _sync_search(query: str, max_results: int = 5) -> List[dict]:
    from ddgs import DDGS

    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results))
        return [
            {
                "title": r.get("title", ""),
                "url": r.get("href", ""),
                "snippet": r.get("body", ""),
            }
            for r in results
        ]
    except Exception as e:
        logger.warning(f"DDG search failed: {e}")
        return []


async def search(query: str, max_results: int = 5) -> List[dict]:
    """Run DuckDuckGo search off the event loop."""
    return await asyncio.to_thread(_sync_search, query, max_results)


def format_results(results: List[dict]) -> str:
    """Format search results as a compact bullet list for the LLM."""
    if not results:
        return "No search results."
    lines = []
    for i, r in enumerate(results, 1):
        lines.append(f"{i}. {r['title']}\n   {r['snippet']}\n   {r['url']}")
    return "\n".join(lines)
