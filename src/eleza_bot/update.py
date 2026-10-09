"""Updates: what a bot receives by long polling or webhook."""

from __future__ import annotations

import json
from typing import Any, Dict, Optional, Union

from .errors import ElezaError


class UpdateType:
    """The ``type`` of an update. New types may appear at any time: ignore the
    ones you do not know."""

    #: The person pressed Start or sent /start (with an optional deep-link payload).
    USER_STARTED_BOT = "user.started_bot"
    MESSAGE_CREATED = "message.created"
    MESSAGE_EDITED = "message.edited"
    MESSAGE_DELETED = "message.deleted"
    #: A message that starts with /command (other than /start).
    COMMAND_RECEIVED = "command.received"
    #: A press on an inline button that carries callback_data.
    CALLBACK_QUERY = "callback_query"
    INLINE_QUERY = "inline_query"
    REACTION_CREATED = "reaction.created"
    REACTION_REMOVED = "reaction.removed"
    BOT_BLOCKED = "bot.blocked"
    BOT_UNBLOCKED = "bot.unblocked"
    #: Someone replied to one of the bot's Eli posts.
    POST_REPLY_CREATED = "post.reply_created"
    #: A like or dislike on one of the bot's Eli posts changed (never says who).
    POST_REACTION_CHANGED = "post.reaction_changed"
    FOLLOWER_ADDED = "follower.added"

    ALL = (
        USER_STARTED_BOT, MESSAGE_CREATED, MESSAGE_EDITED, MESSAGE_DELETED, COMMAND_RECEIVED, CALLBACK_QUERY,
        INLINE_QUERY, REACTION_CREATED, REACTION_REMOVED, BOT_BLOCKED, BOT_UNBLOCKED, POST_REPLY_CREATED,
        POST_REACTION_CHANGED, FOLLOWER_ADDED,
    )


class Update:
    """One update, as long polling returns it and a webhook receives it.

    Delivery is at least once: the same id may arrive twice, so handle updates
    idempotently (or remember the ids you have seen). Updates of one chat
    arrive in order; there is no order across chats.
    """

    __slots__ = ("id", "type", "occurred_at", "bot_id", "data", "version")

    def __init__(self, id: int, type: str, occurred_at: str = "", bot_id: str = "", data: Optional[Dict[str, Any]] = None, version: int = 1) -> None:
        #: Increasing per bot.
        self.id = id
        #: One of :class:`UpdateType`.
        self.type = type
        #: RFC 3339, UTC.
        self.occurred_at = occurred_at
        #: The bot that receives it.
        self.bot_id = bot_id
        #: The payload, by type.
        self.data: Dict[str, Any] = data or {}
        self.version = version

    @classmethod
    def from_dict(cls, u: Dict[str, Any]) -> "Update":
        if not isinstance(u, dict) or "update_id" not in u or "type" not in u:
            raise ElezaError("Not an update: update_id or type is missing")
        data = u.get("data")
        return cls(int(u["update_id"]), str(u["type"]), str(u.get("occurred_at", "")), str(u.get("bot_id", "")),
                   data if isinstance(data, dict) else {}, int(u.get("v", 1)))

    @classmethod
    def from_json(cls, raw: Union[str, bytes]) -> "Update":
        try:
            u = json.loads(raw)
        except ValueError as e:
            raise ElezaError("Not an update: the body is not JSON") from e
        return cls.from_dict(u)

    def is_(self, *types: str) -> bool:
        return self.type in types

    @property
    def chat_id(self) -> Optional[str]:
        """The chat it happened in; ``None`` for inline queries and Eli updates."""
        return self.data.get("chat_id")

    @property
    def sender(self) -> Optional[Dict[str, Any]]:
        """Who did it: ``{id, handle?, name?}``. ``handle`` and ``name`` are
        present only with the ``profile:read`` scope."""
        sender = self.data.get("from")
        return sender if isinstance(sender, dict) else None

    @property
    def sender_id(self) -> Optional[str]:
        return (self.sender or {}).get("id")

    @property
    def sender_name(self) -> str:
        """The person's name, or their handle, or "" when the bot may not read profiles."""
        sender = self.sender or {}
        return str(sender.get("name") or sender.get("handle") or "")

    @property
    def message(self) -> Optional[Dict[str, Any]]:
        """The message: the one sent or edited, or the one whose button was pressed."""
        message = self.data.get("message")
        return message if isinstance(message, dict) else None

    @property
    def text(self) -> str:
        """Text of the message (the caption for media); "" when there is none."""
        return str((self.message or {}).get("text") or "")

    @property
    def seq(self) -> Optional[int]:
        """Seq of the message the update is about."""
        seq = (self.message or {}).get("seq", self.data.get("seq"))
        return None if seq is None else int(seq)

    @property
    def command(self) -> Optional[str]:
        """The command without its slash, lower-case ("start" for user.started_bot)."""
        return self.data.get("command")

    @property
    def args(self) -> str:
        """The text after the command."""
        return str(self.data.get("args") or "")

    @property
    def payload(self) -> str:
        """user.started_bot: the deep-link parameter of ``eleza.me/<handle>?start=<payload>``."""
        return str(self.data.get("payload") or "")

    @property
    def is_first_start(self) -> bool:
        """user.started_bot: this is the person's first message to the bot."""
        return bool(self.data.get("first"))

    @property
    def query_id(self) -> Optional[str]:
        """Id of the callback query or inline query to answer."""
        if self.type in (UpdateType.CALLBACK_QUERY, UpdateType.INLINE_QUERY):
            return self.data.get("id")
        return None

    @property
    def callback_data(self) -> str:
        """callback_query: the callback_data of the pressed button."""
        return str(self.data.get("data") or "") if self.type == UpdateType.CALLBACK_QUERY else ""

    @property
    def query(self) -> str:
        """inline_query: what the person typed after @your_bot."""
        return str(self.data.get("query") or "")

    @property
    def offset(self) -> str:
        """inline_query: the next_offset of your previous answer, when the person scrolls."""
        return str(self.data.get("offset") or "")

    @property
    def emoji(self) -> str:
        """reaction.created: the emoji."""
        return str(self.data.get("emoji") or "")

    @property
    def post_id(self) -> Optional[str]:
        """Eli updates: the bot's post it is about."""
        return self.data.get("post_id")

    @property
    def reply(self) -> Optional[Dict[str, Any]]:
        """post.reply_created: the reply."""
        reply = self.data.get("reply")
        return reply if isinstance(reply, dict) else None

    @property
    def reaction(self) -> str:
        """post.reaction_changed: like | dislike | none."""
        return str(self.data.get("reaction") or "")

    @property
    def previous_reaction(self) -> str:
        """post.reaction_changed: what it was before."""
        return str(self.data.get("previous") or "")

    def __repr__(self) -> str:
        return f"<Update {self.id} {self.type}>"
