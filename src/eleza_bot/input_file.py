"""A file to upload: from disk or from memory."""

from __future__ import annotations

import mimetypes
import os
from typing import Optional, Union

from .errors import ElezaError


class InputFile:
    """A file to upload.

    Always built explicitly, never guessed from a string, so text that comes
    from a person can never be mistaken for a path on your server.
    """

    def __init__(self, *, path: Optional[str], content: Optional[bytes], filename: str, mime: str, size: int) -> None:
        self._path = path
        self._content = content
        self.filename = filename
        self.mime = mime
        self.size = size

    @classmethod
    def from_path(cls, path: Union[str, "os.PathLike[str]"], filename: Optional[str] = None, mime: Optional[str] = None) -> "InputFile":
        path = os.fspath(path)
        if not os.path.isfile(path):
            raise ElezaError(f"File is not readable: {path}")
        size = os.path.getsize(path)
        if size == 0:
            raise ElezaError(f"File is empty: {path}")
        filename = filename or os.path.basename(path)
        return cls(path=path, content=None, filename=filename, mime=mime or _mime_of(filename), size=size)

    @classmethod
    def from_bytes(cls, content: bytes, filename: str, mime: Optional[str] = None) -> "InputFile":
        if not content:
            raise ElezaError("File contents are empty")
        return cls(path=None, content=bytes(content), filename=filename, mime=mime or _mime_of(filename), size=len(content))

    def read(self, offset: int, length: int) -> bytes:
        """Bytes ``[offset, offset + length)`` of the file."""
        if self._content is not None:
            return self._content[offset : offset + length]
        assert self._path is not None
        with open(self._path, "rb") as f:
            f.seek(offset)
            return f.read(length)


def _mime_of(filename: str) -> str:
    return mimetypes.guess_type(filename)[0] or "application/octet-stream"
