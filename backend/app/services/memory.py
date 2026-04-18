"""Semantic memory service backed by Qdrant + local embeddings.

Memories are extracted from user messages by an LLM, embedded locally,
and stored in a single Qdrant collection keyed by user UUID in the payload.
"""
import json
import logging
import uuid
from typing import List, Optional

from litellm import acompletion
from qdrant_client import AsyncQdrantClient
from qdrant_client.http import models as qmodels

from app.config import settings
from app.services.embeddings import EMBEDDING_DIM, embed

logger = logging.getLogger(__name__)

COLLECTION = settings.qdrant_collection

_client: Optional[AsyncQdrantClient] = None
_collection_ready = False


def _get_client() -> AsyncQdrantClient:
    global _client
    if _client is None:
        _client = AsyncQdrantClient(
            url=settings.qdrant_url,
            api_key=settings.qdrant_api_key,
        )
    return _client


async def ensure_collection() -> None:
    """Create the Qdrant collection on first use."""
    global _collection_ready
    if _collection_ready:
        return
    client = _get_client()
    existing = {c.name for c in (await client.get_collections()).collections}
    if COLLECTION not in existing:
        await client.create_collection(
            collection_name=COLLECTION,
            vectors_config=qmodels.VectorParams(
                size=EMBEDDING_DIM,
                distance=qmodels.Distance.COSINE,
            ),
        )
        await client.create_payload_index(
            collection_name=COLLECTION,
            field_name="user_id",
            field_schema=qmodels.PayloadSchemaType.KEYWORD,
        )
        logger.info(f"Created Qdrant collection '{COLLECTION}'")
    _collection_ready = True


EXTRACTION_PROMPT = """You extract durable facts about the user from a conversation turn.

Return JSON: {"memories": [{"type": "semantic|episodic|procedural", "content": "<fact>"}]}

- semantic: stable facts ("allergic to shrimp", "lives in Bangkok", "works as designer")
- episodic: events ("went to Japan last week", "had a fight with mom yesterday")
- procedural: preferences ("prefers short responses", "likes dark mode")

Rules:
- Only extract facts that will be useful later. Skip small talk.
- Be concise. One fact per memory.
- Write in the same language as the user.
- If nothing worth remembering, return {"memories": []}.
"""


async def extract_memories(user_message: str, assistant_reply: str) -> List[dict]:
    """Ask the LLM to extract memories from a conversation turn."""
    try:
        resp = await acompletion(
            model=settings.router_model,
            messages=[
                {"role": "system", "content": EXTRACTION_PROMPT},
                {
                    "role": "user",
                    "content": f"User: {user_message}\nAssistant: {assistant_reply}",
                },
            ],
            max_tokens=500,
            temperature=0.2,
            response_format={"type": "json_object"},
            api_base=settings.moonshot_api_base,
            api_key=settings.moonshot_api_key,
        )
        content = resp.choices[0].message.content or "{}"
        data = json.loads(content)
        memories = data.get("memories", [])
        return [m for m in memories if m.get("content")]
    except Exception as e:
        logger.warning(f"Memory extraction failed: {e}")
        return []


async def add_memory(
    user_id: uuid.UUID,
    content: str,
    mem_type: str = "semantic",
    metadata: Optional[dict] = None,
) -> str:
    """Store a memory in Qdrant. Returns the point id."""
    await ensure_collection()
    point_id = str(uuid.uuid4())
    vector = embed(content)
    payload = {
        "user_id": str(user_id),
        "type": mem_type,
        "content": content,
        "metadata": metadata or {},
    }
    await _get_client().upsert(
        collection_name=COLLECTION,
        points=[qmodels.PointStruct(id=point_id, vector=vector, payload=payload)],
    )
    return point_id


async def search_memories(
    user_id: uuid.UUID,
    query: str,
    limit: int = 5,
) -> List[dict]:
    """Semantic search within a user's memories."""
    await ensure_collection()
    vector = embed(query)
    results = await _get_client().search(
        collection_name=COLLECTION,
        query_vector=vector,
        query_filter=qmodels.Filter(
            must=[
                qmodels.FieldCondition(
                    key="user_id",
                    match=qmodels.MatchValue(value=str(user_id)),
                )
            ]
        ),
        limit=limit,
    )
    return [
        {"id": str(r.id), "score": r.score, **(r.payload or {})}
        for r in results
    ]


async def list_memories(user_id: uuid.UUID, limit: int = 20) -> List[dict]:
    """List a user's memories (most recent first is not guaranteed — Qdrant scroll order)."""
    await ensure_collection()
    points, _ = await _get_client().scroll(
        collection_name=COLLECTION,
        scroll_filter=qmodels.Filter(
            must=[
                qmodels.FieldCondition(
                    key="user_id",
                    match=qmodels.MatchValue(value=str(user_id)),
                )
            ]
        ),
        limit=limit,
        with_payload=True,
        with_vectors=False,
    )
    return [{"id": str(p.id), **(p.payload or {})} for p in points]


async def delete_memory(memory_id: str) -> None:
    """Delete a memory by Qdrant point id."""
    await _get_client().delete(
        collection_name=COLLECTION,
        points_selector=qmodels.PointIdsList(points=[memory_id]),
    )


async def delete_memories_by_topic(user_id: uuid.UUID, topic: str, limit: int = 20) -> int:
    """Semantic-search for a topic and delete the top matches. Returns count deleted."""
    matches = await search_memories(user_id, topic, limit=limit)
    ids = [m["id"] for m in matches if m.get("score", 0) >= 0.5]
    if not ids:
        return 0
    await _get_client().delete(
        collection_name=COLLECTION,
        points_selector=qmodels.PointIdsList(points=ids),
    )
    return len(ids)
