"""Built-in web search tool."""
from app.services import web_search
from app.tools.registry import register


@register(
    name="web_search",
    description="Search the public web for current facts, news, prices, weather, or anything time-sensitive.",
    parameters={
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Search query, concise"},
            "max_results": {"type": "integer", "default": 5, "minimum": 1, "maximum": 10},
        },
        "required": ["query"],
    },
)
async def _run(args: dict):
    results = await web_search.search(
        query=args["query"],
        max_results=int(args.get("max_results", 5)),
    )
    return {"results": results}
