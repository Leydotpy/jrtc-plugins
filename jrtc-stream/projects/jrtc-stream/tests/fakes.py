from __future__ import annotations

from types import SimpleNamespace


class FakeHandle:
    def __init__(self, responses):
        self.responses = list(responses)
        self.requests = []
        self.trickles = []
        self.closed = False

    async def request(self, body, *, operation, jsep=None, timeout_seconds=None):
        self.requests.append((operation, body, jsep))
        if self.responses:
            return self.responses.pop(0)
        return event_response({"streaming": "ok"})

    async def trickle(self, candidates, *, timeout_seconds=None):
        self.trickles.append(candidates)
        return SimpleNamespace(janus="ack")

    async def close(self):
        self.closed = True


def event_response(payload, *, jsep=None):
    return SimpleNamespace(
        janus="event",
        plugindata=SimpleNamespace(data=payload),
        jsep=SimpleNamespace(**jsep) if jsep else None,
    )
