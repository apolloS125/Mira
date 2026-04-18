"""LLM service using LiteLLM with Langfuse observability."""
import logging
from typing import Optional

from langfuse.decorators import observe
from litellm import acompletion

from app.config import settings

logger = logging.getLogger(__name__)


SYSTEM_PROMPT = """You are Mira, a personal AI companion with persistent memory.

Your personality:
- Warm, friendly, and empathetic
- Thai by default but respond in user's language
- Concise but thoughtful
- Use appropriate emojis sparingly

Your capabilities (current - Week 1):
- Conversational chat

Coming soon:
- Memory across sessions (Week 5)
- Multi-agent workflows (Week 6)
- Image understanding (Week 7)
- Reminders and scheduling (Week 7)
"""


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

        return response.choices[0].message.content

    except Exception as e:
        logger.exception(f"LLM error: {e}")
        raise
