"""Everything this SDK raises."""

from __future__ import annotations


class ElezaError(Exception):
    """Base class of everything this SDK raises."""


class TransportError(ElezaError):
    """The request did not get an HTTP answer: DNS, connection, TLS or timeout."""


class WebhookError(ElezaError):
    """A webhook delivery that is not signed by Eleza, is too old, or is not an update."""


class ApiError(ElezaError):
    """The API answered with an error (application/problem+json).

    Branch on ``code``: codes are stable, titles are for people.
    """

    UNAUTHORIZED = "bot.unauthorized"
    SUSPENDED = "bot.suspended"
    SWITCHED_OFF = "bot.switched_off"
    DISABLED = "bot.disabled"
    SCOPE_MISSING = "bot.scope_missing"
    CHAT_NOT_FOUND = "chat.not_found"
    USER_NOT_STARTED = "bot.user_not_started"
    CHAT_BLOCKED = "chat.blocked"
    POLL_CONFLICT = "bot.poll_conflict"
    WEBHOOK_ACTIVE = "bot.webhook_active"
    RATE_LIMITED = "rate_limited"
    PARSE_ERROR = "bot.parse_error"
    MARKUP_INVALID = "bot.markup_invalid"
    MEDIA_NOT_READY = "media.not_ready"
    CALLBACK_EXPIRED = "bot.callback_query_expired"
    INLINE_QUERY_EXPIRED = "bot.inline_query_expired"
    POST_IN_PROGRESS = "bot.post_in_progress"
    POSTS_DISABLED = "bot.posts_disabled"

    def __init__(
        self,
        code: str,
        title: str,
        status: int,
        retryable: bool = False,
        retry_after: int = 0,
        request_id: str = "",
    ) -> None:
        super().__init__(f"{code} ({status}): {title}")
        #: Stable machine code, e.g. ``"bot.user_not_started"``.
        self.code = code
        #: Human text, in the language asked for with the ``language`` option.
        self.title = title
        #: HTTP status.
        self.status = status
        #: The same request may succeed later.
        self.retryable = retryable
        #: Seconds to wait before trying again (rate limiting), 0 when not given.
        self.retry_after = retry_after
        #: Quote this when reporting a problem.
        self.request_id = request_id

    def is_(self, *codes: str) -> bool:
        return self.code in codes

    @property
    def cannot_write(self) -> bool:
        """The person has not started the bot, or has blocked it: nothing to send to for now."""
        return self.code in (self.USER_NOT_STARTED, self.CHAT_BLOCKED, self.CHAT_NOT_FOUND)
