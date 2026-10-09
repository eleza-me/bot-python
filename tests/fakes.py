"""A transport that answers from a queue and records what was sent."""

from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from eleza_bot import Client, Response, Transport, TransportError  # noqa: E402


class FakeTransport(Transport):
    def __init__(self):
        self.requests = []
        self._queue = []

    def json(self, status, body=None, headers=None):
        raw = b"" if body is None else json.dumps(body, ensure_ascii=False).encode()
        self._queue.append(Response(status, raw, headers))
        return self

    def problem(self, status, code, retryable=False, retry_after=0):
        body = {"type": "https://errors.eleza.app/" + code, "code": code, "title": "x", "status": status,
                "request_id": "req-1", "retryable": retryable}
        if retry_after:
            body["retry_after"] = retry_after
        return self.json(status, body)

    def fail(self, message="connection reset"):
        self._queue.append(TransportError(message))
        return self

    def send(self, method, url, headers=None, body=None, timeout=30.0):
        self.requests.append({"method": method, "url": url, "headers": dict(headers or {}), "body": body, "timeout": timeout})
        if not self._queue:
            raise AssertionError(f"No answer queued for {method} {url}")
        answer = self._queue.pop(0)
        if isinstance(answer, Exception):
            raise answer
        return answer

    def sent(self, index=-1):
        r = dict(self.requests[index])
        r["json"] = json.loads(r["body"]) if r["body"] else None
        return r


def make_client(http, slept=None, **options):
    slept = slept if slept is not None else []
    return Client("ezb1.bot.key.secret", transport=http, sleep=slept.append, **options)
