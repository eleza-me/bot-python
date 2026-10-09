"""The Eleza Bot API (v1), one method per route."""

from __future__ import annotations

import json
import random
import sys
import time
import uuid
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional, Sequence, Union
from urllib.parse import quote, urlencode

from .errors import ApiError, ElezaError, TransportError
from .input_file import InputFile
from .keyboards import InlineResult
from .text import Text
from .transport import Response, Transport, UrllibTransport
from .update import Update

__version__ = "1.0.0"

DEFAULT_BASE_URL = "https://api.eleza.me"

# Message kind -> kind of the upload behind it.
_UPLOAD_KIND = {
    "photo": "image", "video": "video", "file": "file", "voice": "voice",
    "audio": "audio", "gif": "gif", "video_note": "video_note",
}

Json = Dict[str, Any]
Media = Union[str, InputFile]


class ChatAction:
    """Activity indicators for :meth:`Client.send_chat_action`."""

    TYPING = "typing"
    RECORDING_VOICE = "recording_voice"
    RECORDING_VIDEO_NOTE = "recording_video_note"
    UPLOADING_PHOTO = "uploading_photo"
    UPLOADING_VIDEO = "uploading_video"
    UPLOADING_FILE = "uploading_file"
    UPLOADING_VOICE = "uploading_voice"
    UPLOADING_VIDEO_NOTE = "uploading_video_note"
    UPLOADING_GIF = "uploading_gif"
    UPLOADING_AUDIO = "uploading_audio"
    #: Hides the indicator before it times out.
    CANCEL = "cancel"


class Client:
    """The Eleza Bot API::

        api = Client(os.environ["ELEZA_BOT_TOKEN"])
        api.send_message(chat_id, "سلام!")

    Ids of chats, people, media and posts are opaque strings; a message inside
    a chat is addressed by its integer ``seq``.

    :param token: the token BotFather gave you (``"ezb1.…"``)
    :param timeout: seconds per request
    :param max_retries: extra attempts after a rate limit, a 5xx or a network error
    :param media_ready_timeout: seconds to wait for uploaded media to finish processing when sending it
    :param language: ``"fa"`` or ``"en"``, the language of error titles
    """

    def __init__(
        self,
        token: str,
        *,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = 30.0,
        max_retries: int = 3,
        media_ready_timeout: float = 60.0,
        language: Optional[str] = None,
        user_agent: Optional[str] = None,
        transport: Optional[Transport] = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        token = (token or "").strip()
        if not token:
            raise ElezaError("The bot token is empty. Get one from @BotFather in Eleza.")
        self._token = token
        self._base_url = base_url.rstrip("/")
        self._timeout = float(timeout)
        self._max_retries = max(0, int(max_retries))
        self._media_ready_timeout = float(media_ready_timeout)
        self._language = language
        self._user_agent = user_agent or f"eleza-bot-sdk-python/{__version__} Python/{sys.version_info[0]}.{sys.version_info[1]}"
        self._transport = transport or UrllibTransport()
        self._sleep = sleep

    def __repr__(self) -> str:  # keeps the token out of logs and tracebacks
        return f"<eleza_bot.Client {self._base_url}>"

    # ------------------------------------------------------------------ bot

    def get_me(self) -> Json:
        """The bot this token belongs to: ``{id, handle, name, is_bot, scopes, link, …}``."""
        return self.request("GET", "/bot/v1/me")

    # ------------------------------------------------------------- messages

    def send_message(self, chat_id: str, text: Union[str, Text], **options: Any) -> Json:
        """Sends a text message. ``text`` is a string, or a :class:`Text` that carries its own formatting.

        Options (all optional):

        - ``parse_mode``: ``"markdown"`` (see :class:`Markdown`)
        - ``entities``: ``[{type, offset, length, url?, language?}]`` with UTF-16 offsets, instead of parse_mode
        - ``reply_to_seq``: seq of the message to reply to
        - ``reply_markup``: an InlineKeyboard, a ReplyKeyboard or a dict
        - ``link_preview``: the URL to show a preview of
        - ``client_message_id``: a UUID that makes a retried send safe; generated when you leave it out

        Returns ``{chat_id, message_id, seq, created_at, duplicate?}``.
        """
        return self.send(chat_id, {"kind": "text", **options, "text": text})

    def send(self, chat_id: str, message: Mapping[str, Any]) -> Json:
        """Sends a message of any kind. Prefer ``send_message`` / ``send_photo`` / …;
        this is the route itself.

        ``message`` keys: kind, text, attachment, sticker, parse_mode, entities, reply_to_seq,
        reply_markup, link_preview, media_spoiler, audio, client_message_id.
        """
        body = {k: v for k, v in message.items() if v is not None}
        body.setdefault("client_message_id", str(uuid.uuid4()))
        _apply_text(body)
        if "reply_markup" in body:
            body["reply_markup"] = _markup(body["reply_markup"])
        path = f"/bot/v1/chats/{quote(chat_id, safe='')}/messages"

        has_media = "attachment" in body
        deadline = time.monotonic() + self._media_ready_timeout
        wait = 1.0
        while True:
            try:
                # The client_message_id makes a repeated send return the first message.
                return self.request("POST", path, body=body, idempotent=True)
            except ApiError as e:
                # Media that was just uploaded is still being processed.
                if not has_media or e.code != ApiError.MEDIA_NOT_READY or time.monotonic() + wait > deadline:
                    raise
                self._sleep(wait)
                wait = min(wait * 1.5, 5.0)

    def send_photo(self, chat_id: str, photo: Media, **options: Any) -> Json:
        """``photo`` is a media id from :meth:`upload_file`, or an :class:`InputFile` to upload now.
        ``text`` is the caption; also ``media_spoiler`` and everything ``send_message`` takes."""
        return self.send_media(chat_id, "photo", photo, **options)

    def send_video(self, chat_id: str, video: Media, **options: Any) -> Json:
        return self.send_media(chat_id, "video", video, **options)

    def send_file(self, chat_id: str, file: Media, **options: Any) -> Json:
        """A document of any type."""
        return self.send_media(chat_id, "file", file, **options)

    def send_voice(self, chat_id: str, voice: Media, **options: Any) -> Json:
        """A voice message."""
        return self.send_media(chat_id, "voice", voice, **options)

    def send_audio(self, chat_id: str, audio: Media, **options: Any) -> Json:
        """Music, shown with a player. Also ``audio={"title": …, "performer": …}``."""
        return self.send_media(chat_id, "audio", audio, **options)

    def send_gif(self, chat_id: str, gif: Media, **options: Any) -> Json:
        return self.send_media(chat_id, "gif", gif, **options)

    def send_video_note(self, chat_id: str, video_note: Media, **options: Any) -> Json:
        """A round video message."""
        return self.send_media(chat_id, "video_note", video_note, **options)

    def send_sticker(self, chat_id: str, sticker_id: str, **options: Any) -> Json:
        """``sticker_id`` is the id of a sticker of a published pack."""
        return self.send(chat_id, {**options, "kind": "sticker", "sticker": sticker_id})

    def send_media(self, chat_id: str, kind: str, media: Media, **options: Any) -> Json:
        """Sends media of the given message kind (photo, video, file, voice, audio, gif, video_note)."""
        if kind not in _UPLOAD_KIND:
            raise ElezaError(f"Unknown media kind: {kind}")
        if isinstance(media, InputFile):
            media = self.upload_file(media, _UPLOAD_KIND[kind])
        return self.send(chat_id, {**options, "kind": kind, "attachment": media})

    def edit_message(self, chat_id: str, seq: int, text: Union[str, Text, None] = None, **options: Any) -> Json:
        """Edits one of the bot's own messages: its text, its inline keyboard, or both.

        ``text=None`` keeps the text. Options: parse_mode, entities, link_preview,
        reply_markup (an inline keyboard; ``InlineKeyboard.none()`` removes it).
        Returns the message as it is now.
        """
        body: Dict[str, Any] = dict(options)
        if text is not None:
            body["text"] = text
        _apply_text(body)
        if "reply_markup" in body:
            body["reply_markup"] = _markup(body["reply_markup"])
        if "text" not in body and "reply_markup" not in body:
            raise ElezaError("edit_message() needs a new text, a new reply_markup, or both")
        return self.request("PATCH", self._message_path(chat_id, seq), body=body, idempotent=True)

    def edit_reply_markup(self, chat_id: str, seq: int, reply_markup: Any) -> Json:
        """Replaces (or, with ``InlineKeyboard.none()``, removes) the inline keyboard of the bot's own message."""
        return self.edit_message(chat_id, seq, reply_markup=reply_markup)

    def delete_message(self, chat_id: str, seq: int) -> None:
        """Deletes one of the bot's own messages."""
        self.request("DELETE", self._message_path(chat_id, seq))

    def set_reaction(self, chat_id: str, seq: int, emoji: str) -> None:
        """Reacts to a message with one emoji (replaces the bot's earlier reaction)."""
        self.request("PUT", self._message_path(chat_id, seq) + "/reaction", body={"emoji": emoji})

    def remove_reaction(self, chat_id: str, seq: int) -> None:
        self.request("DELETE", self._message_path(chat_id, seq) + "/reaction")

    def send_chat_action(self, chat_id: str, action: str = ChatAction.TYPING) -> None:
        """Shows what the bot is doing for a few seconds (a :class:`ChatAction`)."""
        self.request("POST", f"/bot/v1/chats/{quote(chat_id, safe='')}/action", body={"action": action})

    def get_chat(self, chat_id: str) -> Json:
        """A chat of the bot: ``{id, type, state, user, started, can_send, last_seq}``."""
        return self.request("GET", f"/bot/v1/chats/{quote(chat_id, safe='')}")

    # -------------------------------------------------------------- updates

    def get_updates(self, offset: int = 0, limit: int = 100, timeout: int = 0, allowed_updates: Optional[Sequence[str]] = None) -> List[Update]:
        """Long polling. Returns the updates that are waiting; with ``timeout > 0``
        the call waits up to that many seconds (at most 50) for the first one.

        ``offset`` confirms (deletes) every update with an id below it, so pass
        "last update id + 1" once you have handled a batch. Updates that were
        returned but not confirmed are returned again.

        ``allowed_updates`` stores which types the bot wants (``[]`` = all);
        ``None`` leaves it as it is.
        """
        query: Dict[str, Any] = {"limit": limit, "timeout": timeout}
        if offset > 0:
            query["offset"] = offset
        if allowed_updates is not None:
            query["allowed_updates"] = ",".join(allowed_updates)
        out = self.request("GET", "/bot/v1/updates", query=query, timeout=timeout + max(10.0, self._timeout))
        return [Update.from_dict(u) for u in out.get("updates") or []]

    def set_webhook(
        self,
        url: str,
        *,
        secret: Optional[str] = None,
        max_connections: Optional[int] = None,
        allowed_updates: Optional[Sequence[str]] = None,
        drop_pending_updates: bool = False,
    ) -> Json:
        """Has Eleza POST every update to ``url`` instead of long polling.

        The URL must be HTTPS on port 443 or 8443 at a public address.
        ``secret`` is 16–256 characters of ``A-Za-z0-9_-``; when left out one is
        generated, and the answer carries it in ``"secret"`` — only this once. Store it.
        """
        body: Dict[str, Any] = {"url": url}
        if secret is not None:
            body["secret"] = secret
        if max_connections is not None:
            body["max_connections"] = max_connections
        if allowed_updates is not None:
            body["allowed_updates"] = list(allowed_updates)
        if drop_pending_updates:
            body["drop_pending_updates"] = True
        return self.request("PUT", "/bot/v1/webhook", body=body)

    def get_webhook_info(self) -> Json:
        """Webhook configuration and delivery health: ``{url, pending_update_count, last_error?, next_retry_at?, …}``."""
        return self.request("GET", "/bot/v1/webhook")

    def delete_webhook(self, drop_pending_updates: bool = False) -> None:
        """Removes the webhook: back to long polling."""
        self.request("DELETE", "/bot/v1/webhook", query={"drop_pending_updates": "true"} if drop_pending_updates else None)

    # ------------------------------------------------------------- commands

    def set_commands(self, commands: Union[Mapping[str, str], Iterable[Mapping[str, str]]], language: Optional[str] = None) -> None:
        """Replaces the list shown in the app's command menu.

        ``commands`` is ``{"today": "Today's weather", "help": "Help"}`` or the
        API's own ``[{"command": …, "description": …}]``. ``language`` (e.g.
        ``"fa"``) sets a list for one language; ``None`` is for every language.
        """
        if isinstance(commands, Mapping):
            items = [{"command": str(k).lstrip("/"), "description": str(v)} for k, v in commands.items()]
        else:
            items = [dict(c) for c in commands]
        body: Dict[str, Any] = {"commands": items}
        if language is not None:
            body["language"] = language
        self.request("PUT", "/bot/v1/commands", body=body)

    def get_commands(self, language: Optional[str] = None) -> List[Json]:
        out = self.request("GET", "/bot/v1/commands", query={"language": language} if language is not None else None)
        return out.get("commands") or []

    def delete_commands(self, language: Optional[str] = None) -> None:
        self.request("DELETE", "/bot/v1/commands", query={"language": language} if language is not None else None)

    # ---------------------------------------------------- callbacks, inline

    def answer_callback_query(self, query_id: str, text: Optional[str] = None, *, alert: bool = False, url: Optional[str] = None) -> bool:
        """Answers a button press. Call it for every callback_query within 10
        seconds, even with no arguments, so the button stops spinning.

        ``text`` is a short notice; ``alert`` shows it in a dialog instead of a
        toast; ``url`` opens a URL instead. Returns ``False`` when the person
        was no longer waiting for the answer.
        """
        body: Dict[str, Any] = {}
        if text is not None:
            body["text"] = text
        if alert:
            body["alert"] = True
        if url is not None:
            body["url"] = url
        out = self.request("POST", f"/bot/v1/callback-queries/{quote(query_id, safe='')}/answer", body=body)
        return bool(out.get("delivered"))

    def answer_inline_query(
        self,
        query_id: str,
        results: Iterable[Union[InlineResult, Mapping[str, Any]]],
        *,
        cache_time: int = 0,
        is_personal: bool = False,
        next_offset: str = "",
    ) -> None:
        """Answers an inline query (within 8 seconds) with up to 50 results.

        ``cache_time``: seconds the answer may be reused for the same query;
        ``is_personal``: cache per person instead of for everyone;
        ``next_offset``: comes back as ``offset`` when the person scrolls.
        """
        body: Dict[str, Any] = {"results": [r.to_dict() if isinstance(r, InlineResult) else dict(r) for r in results]}
        if cache_time > 0:
            body["cache_time"] = cache_time
        if is_personal:
            body["is_personal"] = True
        if next_offset:
            body["next_offset"] = next_offset
        self.request("POST", f"/bot/v1/inline-queries/{quote(query_id, safe='')}/answer", body=body)

    # ------------------------------------------------------------ Eli posts

    def create_post(
        self,
        text: Optional[str] = None,
        *,
        media: Optional[Sequence[Mapping[str, str]]] = None,
        poll: Optional[Mapping[str, Any]] = None,
        reply_policy: Optional[str] = None,
        client_post_id: Optional[str] = None,
    ) -> Json:
        """Publishes an Eli post as the bot.

        - ``text``: the text, or the caption of the media
        - ``media``: ``[{"id": media_id, "alt": "…"}]`` — upload with purpose ``"post"``
        - ``poll``: ``{"question": "…", "options": ["…", "…"], "duration": "24h"}``
        - ``reply_policy``: everyone (default) | followers | following | mentioned
        - ``client_post_id``: makes a retried call safe for 24 hours; generated when you leave it out

        Returns ``{id, created_at?, limited?, duplicate?}``. ``limited`` means the bot
        has no official mark, so the post reaches followers and the profile only.
        """
        body: Dict[str, Any] = {"client_post_id": client_post_id or str(uuid.uuid4())}
        if text is not None:
            body["text"] = text
        if media:
            body["media"] = [dict(m) for m in media]
        if poll:
            body["poll"] = dict(poll)
        if reply_policy:
            body["reply_policy"] = reply_policy
        return self.request("POST", "/bot/v1/posts", body=body, idempotent=True)

    def delete_post(self, post_id: str) -> None:
        self.request("DELETE", f"/bot/v1/posts/{quote(post_id, safe='')}")

    # ---------------------------------------------------------------- media

    def upload_file(self, file: InputFile, kind: str = "file", purpose: str = "chat") -> str:
        """Uploads a file and returns its media id, ready to be sent as an
        attachment (chat) or listed in a post's media (purpose ``"post"``).

        ``kind`` is what the file is: image, video, video_note, voice, audio,
        gif or file (the kind of an upload: a "photo" message carries an "image").
        """
        upload = self.create_upload(purpose=purpose, kind=kind, size=file.size, mime=file.mime, filename=file.filename)
        upload_id = str(upload["upload_id"])
        try:
            part_size = int(upload.get("part_size") or 0)
            for part in upload.get("parts") or []:
                offset = (int(part["n"]) - 1) * part_size
                self._put_part(str(part["url"]), file.read(offset, part_size or file.size))
            if upload.get("state") != "ready":
                upload = self.complete_upload(upload_id)
        except BaseException:
            try:
                self.abort_upload(upload_id)
            except Exception:
                pass  # the session expires on its own
            raise
        return str(upload["media_id"])

    def create_upload(self, *, purpose: str, kind: str, size: int, mime: str, filename: Optional[str] = None) -> Json:
        """Starts a resumable upload (``upload_file`` does all the steps for you).
        Returns ``{upload_id, media_id, part_size, parts: [{n, url}], state, expires_at}``."""
        body: Dict[str, Any] = {"purpose": purpose, "kind": kind, "size": size, "mime": mime}
        if filename:
            body["filename"] = filename
        return self.request("POST", "/bot/v1/uploads", body=body)

    def get_upload(self, upload_id: str) -> Json:
        """The parts already uploaded and fresh URLs for the rest."""
        return self.request("GET", f"/bot/v1/uploads/{quote(upload_id, safe='')}")

    def complete_upload(self, upload_id: str) -> Json:
        """Finishes an upload once every part is stored. Safe to repeat."""
        return self.request("POST", f"/bot/v1/uploads/{quote(upload_id, safe='')}/complete", idempotent=True, timeout=max(150.0, self._timeout))

    def abort_upload(self, upload_id: str) -> None:
        self.request("DELETE", f"/bot/v1/uploads/{quote(upload_id, safe='')}")

    def get_media(self, media_id: str, variant: Optional[str] = None) -> Json:
        """State and metadata of media this bot uploaded. With ``variant`` and
        ready media, the answer carries a temporary ``url`` for it."""
        return self.request("GET", f"/bot/v1/media/{quote(media_id, safe='')}", query={"variant": variant} if variant else None)

    # ------------------------------------------------------------ internals

    def request(
        self,
        method: str,
        path: str,
        *,
        query: Optional[Mapping[str, Any]] = None,
        body: Optional[Mapping[str, Any]] = None,
        idempotent: bool = False,
        timeout: Optional[float] = None,
    ) -> Json:
        """Calls a route of the API. Public so that a route newer than this SDK
        can be reached without waiting for a release.

        ``idempotent``: repeating the call cannot do the thing twice (GET, PUT
        and DELETE always count as such). Returns the decoded answer (``{}``
        for an empty one).

        Raises :class:`ApiError` when the API refused the call and
        :class:`TransportError` when no answer was received.
        """
        url = self._base_url + path + ("?" + urlencode(query, quote_via=quote) if query else "")
        headers = {"Authorization": "Bot " + self._token, "Accept": "application/json", "User-Agent": self._user_agent}
        if self._language:
            headers["Accept-Language"] = self._language
        payload: Optional[bytes] = None
        if body is not None:
            payload = json.dumps(body, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
            headers["Content-Type"] = "application/json"
        elif method == "POST":
            payload = b""
        idempotent = idempotent or method != "POST"

        attempt = 0
        while True:
            last = attempt >= self._max_retries
            try:
                response = self._transport.send(method, url, headers, payload, timeout if timeout is not None else self._timeout)
            except TransportError:
                if last or not idempotent:
                    raise
                self._sleep(_backoff(attempt))
                attempt += 1
                continue
            if 200 <= response.status < 300:
                return _decode(response)
            error = _error(response)
            retry = error.status == 429 or error.retryable or (error.status >= 500 and idempotent)
            # Not ready yet / another poller: the caller decides what to do with those.
            if last or not retry or error.code in (ApiError.MEDIA_NOT_READY, ApiError.POLL_CONFLICT):
                raise error
            self._sleep(float(error.retry_after) if error.retry_after > 0 else _backoff(attempt))
            attempt += 1

    def _put_part(self, url: str, data: bytes) -> None:
        """Stores one part of an upload. The URL is signed: the bot token is never sent to it."""
        attempt = 0
        while True:
            last = attempt >= self._max_retries
            try:
                response = self._transport.send("PUT", url, {"Content-Type": "application/octet-stream"}, data, max(120.0, self._timeout))
            except TransportError:
                if last:
                    raise
            else:
                if 200 <= response.status < 300:
                    return
                if last or response.status < 500:
                    raise ApiError("upload.part_failed", "Storing a part of the upload failed", response.status, response.status >= 500)
            self._sleep(_backoff(attempt))
            attempt += 1

    @staticmethod
    def _message_path(chat_id: str, seq: int) -> str:
        return f"/bot/v1/chats/{quote(chat_id, safe='')}/messages/{int(seq)}"


def _apply_text(body: Dict[str, Any]) -> None:
    """A Text in ``body["text"]`` becomes plain text plus entities."""
    text = body.get("text")
    if isinstance(text, Text):
        body["text"] = text.text
        if text.entities:
            body["entities"] = text.entities


def _markup(markup: Any) -> Any:
    """A keyboard object or dict as the JSON object the API takes."""
    return markup.to_dict() if hasattr(markup, "to_dict") else markup


def _decode(response: Response) -> Json:
    if not response.body.strip():
        return {}
    try:
        data = json.loads(response.body)
    except ValueError:
        data = None
    if not isinstance(data, dict):
        raise ElezaError(f"The API answered {response.status} with a body that is not a JSON object")
    return data


def _int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _error(response: Response) -> ApiError:
    try:
        p = json.loads(response.body)
    except ValueError:
        p = None
    if not isinstance(p, dict) or "code" not in p:
        # Not from the API itself: a proxy or a gateway in between.
        return ApiError(f"http.{response.status}", f"Unexpected HTTP {response.status}", response.status,
                        response.status >= 500, _int(response.header("Retry-After")))
    return ApiError(
        str(p["code"]),
        str(p.get("title") or ""),
        _int(p.get("status")) or response.status,
        bool(p.get("retryable")),
        _int(p.get("retry_after")) or _int(response.header("Retry-After")),
        str(p.get("request_id") or ""),
    )


def _backoff(attempt: int) -> float:
    return min(0.5 * (2 ** attempt), 8.0) + random.uniform(0, 0.25)
