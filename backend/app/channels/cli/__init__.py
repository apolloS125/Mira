"""CLI channel — a minimal reference adapter.

Run: `python -m app.channels.cli.run`

This exists to document the channel-adapter pattern: any new channel
(Discord, LINE, Slack, ...) should follow the same shape — accept a
platform-specific event, call `core_chat()` with a stable
(channel, external_user_id), deliver the reply back.
"""
