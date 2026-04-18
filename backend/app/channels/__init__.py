"""Channel adapters — thin shells over app.services.chat.

Every channel adapter (telegram, discord, web, cli, ...) follows the same
pattern: translate platform-specific events into a call to `core_chat()`,
then deliver the reply back to the platform. See `base.py` for the contract
and `telegram/` for a full reference implementation.
"""
