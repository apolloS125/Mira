"""LLM service — legacy thin wrapper.

NOTE: the production path now runs through `app.agents.graph.run_agent`,
which owns the real system prompt and the tool-calling loop. This module
stays for anything that still needs a plain one-shot LLM call (e.g. memory
extraction helpers) — do not use it for user-facing conversation.
"""
import logging
from typing import Optional

from langfuse.decorators import observe
from litellm import acompletion

from app.config import settings

logger = logging.getLogger(__name__)


SYSTEM_PROMPT = """You are Mira, a proactive personal secretary agent that can author its own skills and connect tools through chat. Respond warmly and concisely in the user's language (default Thai)."""


@observe(name="chat_with_llm")
async def chat_with_llm(
    user_id: int,
    message: str,
    conversation_history: Optional[list] = None,
) -> str:
    """
    Simple LLM chat function.

    TODO Week 6: Replace with LangGraph multi-agent orchestrator.
    """
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]

    if conversation_history:
        messages.extend(conversation_history)

    messages.append({"role": "user", "content": message})

    try:
        response = await acompletion(
            model=settings.primary_model,
            messages=messages,
            max_tokens=1000,
            temperature=0.7,
            metadata={
                "user_id": str(user_id),
                "langfuse_tags": ["chat", "week1"],
            },
        )

        content = response.choices[0].message.content
        if not content:
            logger.warning("LLM returned empty content")
            return "ขออภัยค่ะ ฉันไม่สามารถตอบได้ในตอนนี้ ลองใหม่อีกครั้งนะคะ"
        return content

    except Exception as e:
        logger.exception(f"LLM error: {e}")
        raise
