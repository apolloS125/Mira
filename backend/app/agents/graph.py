"""LangGraph orchestrator — tool-calling agent loop.

Flow:
  load_context → agent_loop (chat ↔ tools) → extract_memory

agent_loop runs an OpenAI-style tool-calling loop:
  - send messages + tool schemas to LLM
  - if LLM returns tool_calls, execute each, feed results back
  - repeat until LLM returns a final text reply, or MAX_STEPS exceeded
"""
import json
import logging
import uuid
from typing import List, Optional, TypedDict

from langfuse.decorators import observe
from langgraph.graph import END, StateGraph
from litellm import acompletion

from app.config import settings
from app.services import memory as memory_svc
from app.services import working_memory as wm
from app.tools import registry as tool_registry

logger = logging.getLogger(__name__)

MAX_STEPS = 6


SYSTEM_PROMPT = """You are Mira, a proactive personal secretary AI with persistent memory and the ability to use tools and author your own skills.

Personality:
- Warm, professional, concise
- Respond in the user's language (default Thai)
- Use emojis sparingly

You have access to:
- Long-term memories about the user (below, if any)
- Recent conversation history
- A set of callable tools (web_search, time_now, http_request, propose_skill, confirm_skill, create_skill, list_skills, connect_http_api, plus user-authored skills)

When the user asks for something that would benefit from a reusable capability (a recurring workflow, a specific API they want to use often):
  1. If it's trivial and touches no user data/accounts, call `create_skill` directly.
  2. Otherwise call `propose_skill` first, show the user the code in your reply, ask them to confirm, then call `confirm_skill` once they agree.

When the user wants to connect a new HTTP/REST API, prefer `connect_http_api` — it introspects an OpenAPI spec and drafts skills automatically.

When a tool can answer the user better than your own knowledge (anything time-sensitive, factual lookups, external APIs), CALL IT — don't guess.

Output the final answer in natural language. Cite source URLs only when you relied on search results."""


class AgentState(TypedDict, total=False):
    user_id: uuid.UUID
    user_message: str
    history: List[dict]
    memories: List[dict]
    messages: List[dict]  # full conversation for tool loop
    reply: str


async def node_load_context(state: AgentState) -> AgentState:
    user_id = state["user_id"]
    history = await wm.get_recent_turns(user_id, limit=10)
    memories = await memory_svc.search_memories(user_id, state["user_message"], limit=5)
    return {"history": history, "memories": memories}


def _build_system_prompt(memories: List[dict]) -> str:
    if not memories:
        return SYSTEM_PROMPT
    bullets = "\n".join(f"- {m['content']}" for m in memories)
    return f"{SYSTEM_PROMPT}\n\nRelevant memories about the user:\n{bullets}"


async def node_agent_loop(state: AgentState) -> AgentState:
    """Tool-calling loop: chat ↔ tools until final text reply."""
    messages: list[dict] = [
        {"role": "system", "content": _build_system_prompt(state.get("memories") or [])}
    ]
    messages.extend(state.get("history") or [])
    messages.append({"role": "user", "content": state["user_message"]})

    tools_schema = tool_registry.openai_schema()

    for step in range(MAX_STEPS):
        resp = await acompletion(
            model=settings.primary_model,
            messages=messages,
            tools=tools_schema or None,
            tool_choice="auto" if tools_schema else None,
            max_tokens=1200,
            temperature=0.5,
            api_base=settings.moonshot_api_base,
            api_key=settings.moonshot_api_key,
            metadata={
                "user_id": str(state["user_id"]),
                "langfuse_tags": ["agent_loop"],
            },
        )
        msg = resp.choices[0].message
        tool_calls = getattr(msg, "tool_calls", None) or []

        if not tool_calls:
            reply = msg.content or "ขออภัยค่ะ ลองใหม่อีกครั้งนะคะ"
            return {"reply": reply, "messages": messages}

        messages.append({
            "role": "assistant",
            "content": msg.content or "",
            "tool_calls": [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments,
                    },
                }
                for tc in tool_calls
            ],
        })

        for tc in tool_calls:
            name = tc.function.name
            try:
                args = json.loads(tc.function.arguments or "{}")
            except Exception:
                args = {}
            tool = tool_registry.get_tool(name)
            if tool is None:
                result = {"error": f"tool '{name}' not found"}
            else:
                try:
                    result = await tool.run(args)
                except Exception as e:
                    logger.exception(f"Tool '{name}' failed")
                    result = {"error": str(e)}
            logger.info(f"Tool call: {name}({args}) → {str(result)[:200]}")
            messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "name": name,
                "content": json.dumps(result, ensure_ascii=False, default=str)[:4000],
            })

    return {
        "reply": "ขออภัยค่ะ ใช้เครื่องมือหลายรอบเกินไป ลองถามใหม่อีกครั้งนะคะ",
        "messages": messages,
    }


async def node_extract_memory(state: AgentState) -> AgentState:
    user_id = state["user_id"]
    user_msg = state["user_message"]
    reply = state.get("reply", "")

    await wm.append_turn(user_id, "user", user_msg)
    await wm.append_turn(user_id, "assistant", reply)

    extracted = await memory_svc.extract_memories(user_msg, reply)
    for m in extracted:
        try:
            await memory_svc.add_memory(
                user_id=user_id,
                content=m["content"],
                mem_type=m.get("type", "semantic"),
            )
        except Exception as e:
            logger.warning(f"add_memory failed: {e}")
    if extracted:
        logger.info(f"Saved {len(extracted)} memories for user {user_id}")
    return {"reply": reply}


def _build_graph():
    g = StateGraph(AgentState)
    g.add_node("load_context", node_load_context)
    g.add_node("agent_loop", node_agent_loop)
    g.add_node("extract_memory", node_extract_memory)
    g.set_entry_point("load_context")
    g.add_edge("load_context", "agent_loop")
    g.add_edge("agent_loop", "extract_memory")
    g.add_edge("extract_memory", END)
    return g.compile()


_graph = None


def get_graph():
    global _graph
    if _graph is None:
        _graph = _build_graph()
    return _graph


@observe(name="agent_run")
async def run_agent(user_id: uuid.UUID, user_message: str) -> str:
    graph = get_graph()
    result = await graph.ainvoke({"user_id": user_id, "user_message": user_message})
    return result.get("reply", "ขออภัยค่ะ ลองใหม่อีกครั้งนะคะ")
