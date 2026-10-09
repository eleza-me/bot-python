"""Routing updates to your handlers, from long polling or from a webhook."""

from __future__ import annotations

import logging
import re
import signal
import threading
import time
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional, Pattern, Sequence, Tuple, Union

from . import webhook
from .client import ChatAction, Client, Json, Media
from .errors import ApiError, ElezaError, WebhookError
from .keyboards import InlineResult
from .text import Text
from .update import Update, UpdateType

log = logging.getLogger("eleza_bot")

Handler = Callable[["Context"], Any]
ErrorHandler = Callable[[BaseException, Optional[Update]], Any]

_MAX_WEBHOOK_BODY = 1 << 20


class Context:
    """What a handler receives: the update, and shortcuts that act on it::

        @bot.on_text
        def echo(ctx):
            ctx.reply("شما گفتید: " + ctx.text)
    """

    def __init__(self, update: Update, api: Client) -> None:
        self.update = update
        self.api = api

    @property
    def chat_id(self) -> Optional[str]:
        return self.update.chat_id

    @property
    def sender(self) -> Optional[Dict[str, Any]]:
        return self.update.sender

    @property
    def sender_id(self) -> Optional[str]:
        return self.update.sender_id

    @property
    def sender_name(self) -> str:
        return self.update.sender_name

    @property
    def message(self) -> Optional[Dict[str, Any]]:
        return self.update.message

    @property
    def text(self) -> str:
        return self.update.text

    @property
    def command(self) -> Optional[str]:
        return self.update.command

    @property
    def args(self) -> str:
        return self.update.args

    @property
    def payload(self) -> str:
        return self.update.payload

    @property
    def callback_data(self) -> str:
        return self.update.callback_data

    @property
    def query(self) -> str:
        return self.update.query

    def reply(self, text: Union[str, Text], **options: Any) -> Json:
        """Sends a message to the chat of this update (options as ``Client.send_message``)."""
        return self.api.send_message(self._chat(), text, **options)

    def reply_quoting(self, text: Union[str, Text], **options: Any) -> Json:
        """The same, as a reply to the message of this update."""
        seq = self.update.seq
        if seq is not None:
            options.setdefault("reply_to_seq", seq)
        return self.reply(text, **options)

    def reply_with_photo(self, photo: Media, **options: Any) -> Json:
        return self.api.send_photo(self._chat(), photo, **options)

    def reply_with_file(self, file: Media, **options: Any) -> Json:
        return self.api.send_file(self._chat(), file, **options)

    def typing(self, action: str = ChatAction.TYPING) -> None:
        """Shows "typing…" (or another ChatAction) in the chat of this update."""
        self.api.send_chat_action(self._chat(), action)

    def react(self, emoji: str) -> None:
        """Reacts to the message of this update."""
        self.api.set_reaction(self._chat(), self._seq(), emoji)

    def answer(self, text: Optional[str] = None, *, alert: bool = False, url: Optional[str] = None) -> bool:
        """callback_query: answers the press (a toast, a dialog with ``alert``, or
        nothing at all — the button stops spinning either way)."""
        if self.update.type != UpdateType.CALLBACK_QUERY:
            raise ElezaError(f"answer() is for callback_query updates; this one is {self.update.type}")
        return self.api.answer_callback_query(str(self.update.query_id), text, alert=alert, url=url)

    def edit_message(self, text: Union[str, Text, None] = None, **options: Any) -> Json:
        """callback_query: edits the message the pressed button is on."""
        return self.api.edit_message(self._chat(), self._seq(), text, **options)

    def answer_inline(self, results: Iterable[Union[InlineResult, Mapping[str, Any]]], *, cache_time: int = 0,
                      is_personal: bool = False, next_offset: str = "") -> None:
        """inline_query: answers it."""
        if self.update.type != UpdateType.INLINE_QUERY:
            raise ElezaError(f"answer_inline() is for inline_query updates; this one is {self.update.type}")
        self.api.answer_inline_query(str(self.update.query_id), results, cache_time=cache_time, is_personal=is_personal, next_offset=next_offset)

    def _chat(self) -> str:
        if self.update.chat_id is None:
            raise ElezaError(f"A {self.update.type} update has no chat to answer in")
        return self.update.chat_id

    def _seq(self) -> int:
        if self.update.seq is None:
            raise ElezaError(f"A {self.update.type} update has no message")
        return self.update.seq


class Bot:
    """Routes updates to your handlers::

        bot = Bot(os.environ["ELEZA_BOT_TOKEN"])

        @bot.on_start
        def start(ctx):
            ctx.reply("سلام!")

        @bot.on_text
        def echo(ctx):
            ctx.reply(ctx.text)

        bot.run()

    The first handler that matches an update handles it. An exception raised
    by a handler goes to ``on_error`` and the bot carries on with the next update.

    :param token: the bot token, or a :class:`Client` you configured yourself
    :param client_options: as ``Client(...)``, when a token is given
    """

    def __init__(self, token: Union[str, Client], **client_options: Any) -> None:
        self.api = token if isinstance(token, Client) else Client(token, **client_options)
        self._routes: List[Tuple[Callable[[Update], bool], Handler]] = []
        self._fallback: Optional[Handler] = None
        self._error_handler: ErrorHandler = _log_error
        self._running = False

    # ------------------------------------------------------------- handlers

    def route(self, matches: Callable[[Update], bool]) -> Callable[[Handler], Handler]:
        """Handles the updates a test of yours decides on."""
        def register(handler: Handler) -> Handler:
            self._routes.append((matches, handler))
            return handler
        return register

    def on(self, *types: str) -> Callable[[Handler], Handler]:
        """Handles updates of the given type(s) (:class:`UpdateType`)."""
        return self.route(lambda u: u.type in types)

    def on_start(self, handler: Handler) -> Handler:
        """The person pressed Start (or sent /start). ``ctx.payload`` is the
        deep-link parameter of ``eleza.me/<handle>?start=<payload>``."""
        return self.on(UpdateType.USER_STARTED_BOT)(handler)

    def on_command(self, *commands: str) -> Callable[[Handler], Handler]:
        """A command: ``@bot.on_command("help")`` handles "/help" and
        "/help@your_bot". ``ctx.args`` is the text after it."""
        names = {c.lstrip("/").lower() for c in commands}
        return self.route(lambda u: u.type in (UpdateType.COMMAND_RECEIVED, UpdateType.USER_STARTED_BOT) and u.command in names)

    def on_message(self, handler: Handler) -> Handler:
        """Any new message that is not a command: text, photo, voice, …"""
        return self.on(UpdateType.MESSAGE_CREATED)(handler)

    def on_text(self, handler: Optional[Handler] = None, *, pattern: Union[str, Pattern[str], None] = None) -> Any:
        """A new text message that is not a command. With ``pattern`` (a regular
        expression) only texts it is found in::

            @bot.on_text
            @bot.on_text(pattern=r"^\\d+$")
        """
        compiled = re.compile(pattern) if isinstance(pattern, str) else pattern

        def matches(u: Update) -> bool:
            return (u.type == UpdateType.MESSAGE_CREATED and (u.message or {}).get("kind") == "text"
                    and (compiled is None or compiled.search(u.text) is not None))

        register = self.route(matches)
        return register(handler) if handler is not None else register

    def on_kind(self, *kinds: str) -> Callable[[Handler], Handler]:
        """A new message of the given kind(s): photo, video, file, voice, audio,
        gif, video_note, sticker, location, …"""
        return self.route(lambda u: u.type == UpdateType.MESSAGE_CREATED and (u.message or {}).get("kind") in kinds)

    def on_callback(self, data: Union[str, Handler, None] = None) -> Any:
        """A press on an inline button. ``data`` says which buttons: the exact
        callback_data, or a prefix ending in "*"; nothing = all::

            @bot.on_callback("city:*")
            @bot.on_callback
        """
        handler = data if callable(data) else None
        wanted = None if callable(data) else data

        def matches(u: Update) -> bool:
            if u.type != UpdateType.CALLBACK_QUERY:
                return False
            if wanted is None:
                return True
            return u.callback_data.startswith(wanted[:-1]) if wanted.endswith("*") else u.callback_data == wanted

        register = self.route(matches)
        return register(handler) if handler is not None else register

    def on_inline_query(self, handler: Handler) -> Handler:
        """Someone typed "@your_bot …" in a chat (turn inline mode on in BotFather)."""
        return self.on(UpdateType.INLINE_QUERY)(handler)

    def fallback(self, handler: Handler) -> Handler:
        """Handles every update no other handler took."""
        self._fallback = handler
        return handler

    def on_error(self, handler: ErrorHandler) -> ErrorHandler:
        """Called with what a handler (or, while polling, the network) raised,
        and the update when there is one. The default logs it to the
        ``eleza_bot`` logger."""
        self._error_handler = handler
        return handler

    # ------------------------------------------------------------- dispatch

    def handle(self, update: Update) -> bool:
        """Runs the handler of one update. Returns whether a handler took it.
        Never raises: errors go to ``on_error``."""
        try:
            for matches, handler in self._routes:
                if matches(update):
                    handler(Context(update, self.api))
                    return True
            if self._fallback is not None:
                self._fallback(Context(update, self.api))
                return True
        except Exception as e:
            self._report(e, update)
            return True
        return False

    # --------------------------------------------------------- long polling

    def run(self, *, timeout: int = 30, limit: int = 100, allowed_updates: Optional[Sequence[str]] = None,
            drop_pending_updates: bool = False) -> None:
        """Receives updates by long polling until ``stop()`` is called, Ctrl+C
        is pressed or the process gets SIGTERM.

        Run one process per bot: a second poll of the same bot ends the first
        with ``bot.poll_conflict``.

        :param timeout: seconds one poll waits for updates (at most 50)
        :param limit: updates per poll
        :param allowed_updates: the only types to receive from now on (``[]`` = all)
        :param drop_pending_updates: skip what queued up while the bot was not running

        Raises :class:`ApiError` when polling cannot work: a bad token, a
        webhook that is set, another poller.
        """
        timeout = max(0, min(50, int(timeout)))
        limit = max(1, min(100, int(limit)))
        self._running = True
        restore = self._install_sigterm()
        offset = 0
        try:
            if drop_pending_updates:
                offset = self._skip_pending()
            while self._running:
                try:
                    updates = self.api.get_updates(offset, limit, timeout, allowed_updates)
                    allowed_updates = None  # stored by the first call
                except ApiError as e:
                    if e.status < 500 and e.status != 429:
                        raise  # nothing a retry would fix
                    self._report(e, None)
                    self._pause(3)
                    continue
                except ElezaError as e:
                    self._report(e, None)
                    self._pause(3)
                    continue
                for update in updates:
                    self.handle(update)
                    # Confirmed by the next poll: an update is gone only after its handler returned.
                    offset = update.id + 1
        except KeyboardInterrupt:
            pass
        finally:
            self._running = False
            restore()
            if offset > 0:
                try:
                    self.api.get_updates(offset, 1, 0)  # confirm what was handled before leaving
                except Exception:
                    pass  # they come again on the next start; handlers must be idempotent anyway

    def stop(self) -> None:
        """Ends ``run()`` after the poll that is in flight."""
        self._running = False

    # -------------------------------------------------------------- webhook

    def handle_webhook(self, secret: str, raw_body: Union[str, bytes], headers: Mapping[str, Any]) -> Update:
        """Verifies one webhook delivery and runs its handler.

        ``raw_body`` is the request body exactly as received; ``headers`` are
        the request headers. Answer 200 afterwards (within 10 seconds).

        Raises :class:`WebhookError` when the delivery is not authentic: answer 401 and do nothing.
        """
        update = webhook.parse(secret, raw_body, headers)
        self.handle(update)
        return update

    def wsgi_app(self, secret: str) -> Callable[..., Iterable[bytes]]:
        """A WSGI application that is the whole webhook endpoint, for gunicorn,
        uWSGI, mod_wsgi or ``wsgiref``::

            application = bot.wsgi_app(os.environ["ELEZA_WEBHOOK_SECRET"])
        """
        def app(environ: Dict[str, Any], start_response: Callable[..., Any]) -> Iterable[bytes]:
            def answer(status: str, extra: Sequence[Tuple[str, str]] = ()) -> Iterable[bytes]:
                start_response(status, [("Content-Length", "0"), *extra])
                return [b""]

            if environ.get("REQUEST_METHOD") != "POST":
                return answer("405 Method Not Allowed", [("Allow", "POST")])
            try:
                length = int(environ.get("CONTENT_LENGTH") or 0)
            except ValueError:
                length = 0
            if length <= 0 or length > _MAX_WEBHOOK_BODY:
                return answer("400 Bad Request")
            body = environ["wsgi.input"].read(length)
            headers = {k[5:].replace("_", "-"): v for k, v in environ.items() if k.startswith("HTTP_")}
            try:
                self.handle_webhook(secret, body, headers)
            except WebhookError:
                return answer("401 Unauthorized")
            return answer("200 OK")

        return app

    # ------------------------------------------------------------ internals

    def _skip_pending(self) -> int:
        """Confirms everything that is queued and returns the offset to continue from."""
        offset = 0
        while True:
            updates = self.api.get_updates(offset, 100, 0)
            if not updates:
                return offset
            offset = updates[-1].id + 1

    def _report(self, error: BaseException, update: Optional[Update]) -> None:
        try:
            self._error_handler(error, update)
        except Exception:
            pass  # an error handler that fails must not take the bot down

    def _pause(self, seconds: float) -> None:
        end = time.monotonic() + seconds
        while self._running and time.monotonic() < end:
            time.sleep(0.1)

    def _install_sigterm(self) -> Callable[[], None]:
        """SIGTERM (systemd, Docker) stops the bot as cleanly as Ctrl+C does."""
        if threading.current_thread() is not threading.main_thread():
            return lambda: None
        try:
            previous = signal.signal(signal.SIGTERM, lambda *_: self.stop())
        except (ValueError, OSError):
            return lambda: None
        return lambda: signal.signal(signal.SIGTERM, previous)


def _log_error(error: BaseException, update: Optional[Update]) -> None:
    where = f"update {update.id} ({update.type}): " if update is not None else ""
    log.error("%s%s: %s", where, type(error).__name__, error, exc_info=error if update is not None else None)
