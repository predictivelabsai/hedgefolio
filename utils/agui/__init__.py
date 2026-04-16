"""Hedgefolio AG-UI — FastHTML + LangGraph streaming chat.

Based on the port inside alpatrade (MIT, Novia-RDI-Seafaring/ft-ag-ui).
Simplified for hedgefolio: no auth, no long-running command streaming.
"""

from .chat_store import (
    delete_conversation,
    list_conversations,
    load_conversation_messages,
    save_conversation,
    save_message,
)
from .core import AGUISetup, AGUIThread, UI, setup_agui
from .styles import CHAT_UI_STYLES, get_chat_styles, get_custom_theme

__all__ = [
    "AGUISetup",
    "AGUIThread",
    "CHAT_UI_STYLES",
    "UI",
    "delete_conversation",
    "get_chat_styles",
    "get_custom_theme",
    "list_conversations",
    "load_conversation_messages",
    "save_conversation",
    "save_message",
    "setup_agui",
]
