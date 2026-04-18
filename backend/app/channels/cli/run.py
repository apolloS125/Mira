"""Interactive terminal chat with Mira.

Usage:
    python -m app.channels.cli.run [--user alice]

Demonstrates the channel-adapter contract end-to-end without any framework:
read a line, call core_chat(), print the reply. Use as a template when
building a new channel.
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys

from app.services.chat import chat as core_chat

CHANNEL = "cli"


async def _loop(external_user_id: str, display_name: str) -> None:
    print(f"Mira CLI — channel={CHANNEL} user={external_user_id} (Ctrl-D to exit)\n")
    loop = asyncio.get_event_loop()
    while True:
        try:
            line = await loop.run_in_executor(None, sys.stdin.readline)
        except (KeyboardInterrupt, EOFError):
            break
        if not line:
            break
        text = line.strip()
        if not text:
            continue
        result = await core_chat(
            channel=CHANNEL,
            external_user_id=external_user_id,
            message=text,
            display_name=display_name,
            language_code="th",
        )
        print(f"Mira: {result.reply}\n")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--user", default=os.environ.get("USER", "local"))
    args = parser.parse_args()
    asyncio.run(_loop(external_user_id=args.user, display_name=args.user))


if __name__ == "__main__":
    main()
