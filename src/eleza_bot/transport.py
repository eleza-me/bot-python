"""Sending one HTTP request. Replace the transport to use your own HTTP client, or in tests."""

from __future__ import annotations

import http.client
import socket
import urllib.error
import urllib.request
from typing import Dict, Mapping, Optional

from .errors import TransportError


class Response:
    __slots__ = ("status", "body", "headers")

    def __init__(self, status: int, body: bytes = b"", headers: Optional[Mapping[str, str]] = None) -> None:
        self.status = status
        self.body = body
        self.headers: Dict[str, str] = {k.lower(): v for k, v in (headers or {}).items()}

    def header(self, name: str) -> Optional[str]:
        return self.headers.get(name.lower())


class Transport:
    """The interface: one method. Raise :class:`TransportError` when no HTTP answer was received."""

    def send(
        self,
        method: str,
        url: str,
        headers: Optional[Mapping[str, str]] = None,
        body: Optional[bytes] = None,
        timeout: float = 30.0,
    ) -> Response:
        raise NotImplementedError


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):  # type: ignore[no-untyped-def]
        return None  # a redirect is an answer, not something to follow with the token


class UrllibTransport(Transport):
    """The default transport, on the standard library only.

    Proxies come from the environment (``HTTPS_PROXY``), as usual for urllib.
    """

    def __init__(self) -> None:
        self._opener = urllib.request.build_opener(_NoRedirect())

    def send(
        self,
        method: str,
        url: str,
        headers: Optional[Mapping[str, str]] = None,
        body: Optional[bytes] = None,
        timeout: float = 30.0,
    ) -> Response:
        request = urllib.request.Request(url, data=body, method=method, headers=dict(headers or {}))
        try:
            with self._opener.open(request, timeout=timeout) as answer:
                return Response(answer.status, answer.read(), dict(answer.headers.items()))
        except urllib.error.HTTPError as e:
            with e:
                return Response(e.code, e.read(), dict(e.headers.items()) if e.headers else {})
        except (urllib.error.URLError, http.client.HTTPException, socket.timeout, OSError) as e:
            reason = getattr(e, "reason", e)
            # Upload URLs are signed in their query string: keep that out of error messages.
            raise TransportError(f"{method} {url.split('?', 1)[0]} failed: {reason}") from e
