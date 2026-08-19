from __future__ import annotations

from threading import RLock
from typing import Any, TypeVar

T = TypeVar("T")


class ServiceRegistry:
    """Explicit process-local dependency registry for Django composition roots.

    Configure it from ASGI lifespan, a management command, or another explicit
    startup hook. Do not perform network I/O in AppConfig.ready().
    """

    def __init__(self) -> None:
        self._services: dict[str, Any] = {}
        self._lock = RLock()

    def register(self, name: str, service: Any) -> None:
        with self._lock:
            if name in self._services:
                raise RuntimeError(f"service {name!r} is already registered")
            self._services[name] = service

    def get(self, name: str, expected_type: type[T] | None = None) -> T:
        with self._lock:
            try:
                service = self._services[name]
            except KeyError as exc:
                raise RuntimeError(f"service {name!r} has not been registered") from exc
        if expected_type is not None and not isinstance(service, expected_type):
            raise TypeError(f"service {name!r} is not a {expected_type.__name__}")
        return service

    def remove(self, name: str) -> Any | None:
        with self._lock:
            return self._services.pop(name, None)

    def clear(self) -> None:
        with self._lock:
            self._services.clear()


services = ServiceRegistry()
