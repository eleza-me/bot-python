"""Keyboards a bot attaches to its messages, and inline query results."""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Union

from .errors import ElezaError
from .text import Text

MAX_CALLBACK_DATA_BYTES = 64


class Button(dict):  # type: ignore[type-arg]
    """One button of an inline keyboard. It does exactly one thing."""

    @classmethod
    def callback(cls, text: str, data: str) -> "Button":
        """Pressing it sends you a ``callback_query`` update with ``data`` (1–64 bytes).

        The data never reaches the apps: the server tells you which button was
        pressed and by whom, so you can trust what you receive.
        """
        if not data or len(data.encode("utf-8")) > MAX_CALLBACK_DATA_BYTES:
            raise ElezaError(f"callback_data must be 1 to {MAX_CALLBACK_DATA_BYTES} bytes")
        return cls(text=text, callback_data=data)

    @classmethod
    def url(cls, text: str, url: str) -> "Button":
        """Opens an http(s) link (after the app asks the person)."""
        return cls(text=text, url=url)

    @classmethod
    def switch_inline(cls, text: str, query: str = "") -> "Button":
        """Lets the person pick a chat and starts ``@your_bot query`` there."""
        return cls(text=text, switch_inline_query=query)

    @classmethod
    def switch_inline_current_chat(cls, text: str, query: str = "") -> "Button":
        """Starts ``@your_bot query`` in the chat the button is in."""
        return cls(text=text, switch_inline_query_current_chat=query)


class InlineKeyboard:
    """Buttons under a message::

        InlineKeyboard().row(Button.callback("تهران", "city:thr"), Button.callback("شیراز", "city:syz")) \\
                        .row(Button.url("سایت", "https://example.com"))

    Up to 25 rows, 8 buttons per row, 100 buttons in total.
    """

    def __init__(self) -> None:
        self._rows: List[List[Dict[str, Any]]] = []

    @classmethod
    def none(cls) -> "InlineKeyboard":
        """For ``edit_message``: takes the inline keyboard of a message away."""
        return cls()

    def row(self, *buttons: Dict[str, Any]) -> "InlineKeyboard":
        if buttons:
            self._rows.append([dict(b) for b in buttons])
        return self

    def grid(self, buttons: Iterable[Dict[str, Any]], per_row: int = 2) -> "InlineKeyboard":
        """Adds buttons, ``per_row`` to a row."""
        row: List[Dict[str, Any]] = []
        for button in buttons:
            row.append(dict(button))
            if len(row) == max(1, per_row):
                self._rows.append(row)
                row = []
        if row:
            self._rows.append(row)
        return self

    def to_dict(self) -> Dict[str, Any]:
        return {"inline_keyboard": [list(r) for r in self._rows]}


class ReplyKeyboard:
    """Buttons shown instead of the person's keyboard. Pressing one sends its
    text as an ordinary message from the person::

        ReplyKeyboard().row("امروز", "این هفته").row("تنظیمات").resize()

    It stays until a later message of the bot replaces it or sends
    ``ReplyKeyboard.remove()``.
    """

    def __init__(self) -> None:
        self._rows: List[List[Dict[str, str]]] = []
        self._options: Dict[str, Any] = {}
        self._remove = False

    @classmethod
    def remove(cls) -> "ReplyKeyboard":
        """Takes a reply keyboard shown earlier away."""
        k = cls()
        k._remove = True
        return k

    def row(self, *texts: str) -> "ReplyKeyboard":
        if texts:
            self._rows.append([{"text": t} for t in texts])
        return self

    def resize(self, on: bool = True) -> "ReplyKeyboard":
        """Fit the keyboard's height to its rows."""
        return self._option("resize_keyboard", on)

    def one_time(self, on: bool = True) -> "ReplyKeyboard":
        """Hide after one press."""
        return self._option("one_time_keyboard", on)

    def persistent(self, on: bool = True) -> "ReplyKeyboard":
        """Keep it shown when the system keyboard would hide it."""
        return self._option("is_persistent", on)

    def placeholder(self, text: str) -> "ReplyKeyboard":
        """Shown in the empty input field."""
        return self._option("input_field_placeholder", text)

    def to_dict(self) -> Dict[str, Any]:
        if self._remove:
            return {"remove_keyboard": True}
        return {"keyboard": [list(r) for r in self._rows], **self._options}

    def _option(self, name: str, value: Union[bool, str]) -> "ReplyKeyboard":
        if value:
            self._options[name] = value
        else:
            self._options.pop(name, None)
        return self


class InlineResult:
    """One result of an inline query answer. When the person picks it, its text
    is sent as their message, marked "via @your_bot"."""

    def __init__(self, fields: Dict[str, Any]) -> None:
        self._fields = fields

    @classmethod
    def article(cls, id: str, title: str, text: Union[str, Text]) -> "InlineResult":
        """``id`` is unique within the answer (1–64 bytes); ``title`` is the row
        in the results list; ``text`` is what gets sent."""
        fields: Dict[str, Any] = {"type": "article", "id": id, "title": title, "text": str(text)}
        if isinstance(text, Text) and text.entities:
            fields["entities"] = text.entities
        return cls(fields)

    def description(self, description: str) -> "InlineResult":
        """Second line of the row."""
        return self._with("description", description)

    def thumbnail(self, https_url: str) -> "InlineResult":
        """An https image shown in the results list."""
        return self._with("thumb_url", https_url)

    def link_preview(self, url: str) -> "InlineResult":
        """The URL to show a preview of under the sent message."""
        return self._with("link_preview", url)

    def keyboard(self, keyboard: InlineKeyboard) -> "InlineResult":
        """URL and switch-inline buttons only: nobody could answer a callback button here."""
        return self._with("reply_markup", keyboard.to_dict())

    def to_dict(self) -> Dict[str, Any]:
        return dict(self._fields)

    def _with(self, key: str, value: Any) -> "InlineResult":
        self._fields[key] = value
        return self
