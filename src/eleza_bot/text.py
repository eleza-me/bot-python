"""Formatted text: a builder that needs no escaping, and helpers for parse_mode "markdown"."""

from __future__ import annotations

import re
from typing import Any, Dict, List


def utf16_length(text: str) -> int:
    """Length of ``text`` in UTF-16 code units (how entity offsets are counted)."""
    return len(text.encode("utf-16-le")) // 2


class Text:
    """Builds formatted text from pieces, without any escaping to get wrong::

        text = Text("سلام ").bold(name).plain("\\n").code(order_id)
        api.send_message(chat_id, text)

    Use it whenever a piece comes from a person or from another system.
    """

    def __init__(self, plain: str = "") -> None:
        self._text = ""
        self._length = 0  # in UTF-16 units
        self._entities: List[Dict[str, Any]] = []
        self.plain(plain)

    def plain(self, text: str) -> "Text":
        self._text += text
        self._length += utf16_length(text)
        return self

    def bold(self, text: str) -> "Text":
        return self._span("bold", text)

    def italic(self, text: str) -> "Text":
        return self._span("italic", text)

    def underline(self, text: str) -> "Text":
        return self._span("underline", text)

    def strikethrough(self, text: str) -> "Text":
        return self._span("strikethrough", text)

    def spoiler(self, text: str) -> "Text":
        """Hidden until tapped."""
        return self._span("spoiler", text)

    def code(self, text: str) -> "Text":
        """Monospace; a tap copies it."""
        return self._span("code", text)

    def pre(self, text: str, language: str = "") -> "Text":
        """A block of code."""
        return self._span("pre", text, **({"language": language} if language else {}))

    def link(self, text: str, url: str) -> "Text":
        """``url`` is http or https."""
        return self._span("text_link", text, url=url)

    def newline(self, count: int = 1) -> "Text":
        return self.plain("\n" * count)

    @property
    def text(self) -> str:
        return self._text

    @property
    def entities(self) -> List[Dict[str, Any]]:
        """``[{type, offset, length, url?, language?}]`` with UTF-16 offsets."""
        return [dict(e) for e in self._entities]

    def __str__(self) -> str:
        return self._text

    def _span(self, type_: str, text: str, **extra: str) -> "Text":
        if not text:
            return self
        offset = self._length
        self.plain(text)
        self._entities.append({"type": type_, "offset": offset, "length": self._length - offset, **extra})
        return self


class Markdown:
    """Helpers for ``parse_mode="markdown"``::

        *bold*  _italic_  __underline__  ~strikethrough~  ||spoiler||
        `code`  ```lang\\ncode block```  [text](https://example.com)

    A backslash makes the next character literal. An unclosed marker is refused
    by the API (400 ``bot.parse_error``), so escape everything you did not write
    yourself — or build the message with :class:`Text`, which needs no escaping.
    """

    PARSE_MODE = "markdown"

    @staticmethod
    def escape(text: str) -> str:
        """Makes ``text`` literal: no character of it starts formatting."""
        return re.sub(r"([\\*_~|`\[])", r"\\\1", text)

    @classmethod
    def bold(cls, text: str) -> str:
        return f"*{cls.escape(text)}*"

    @classmethod
    def italic(cls, text: str) -> str:
        return f"_{cls.escape(text)}_"

    @classmethod
    def underline(cls, text: str) -> str:
        return f"__{cls.escape(text)}__"

    @classmethod
    def strikethrough(cls, text: str) -> str:
        return f"~{cls.escape(text)}~"

    @classmethod
    def spoiler(cls, text: str) -> str:
        return f"||{cls.escape(text)}||"

    @staticmethod
    def link(text: str, url: str) -> str:
        # The link target ends at the first ")".
        label = re.sub(r"([\\\]])", r"\\\1", text)
        return f"[{label}]({url.replace(')', '%29').replace(' ', '%20')})"
