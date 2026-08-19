from __future__ import annotations

from .errors import DriverNotRegistered
from .ports import SourceDriver, SourceGate


class SourceDriverRegistry:
    def __init__(self) -> None:
        self._drivers: dict[str, SourceDriver] = {}

    def register(self, driver: SourceDriver, *, replace: bool = False) -> None:
        if driver.name in self._drivers and not replace:
            raise ValueError(f"driver {driver.name!r} is already registered")
        self._drivers[driver.name] = driver

    def get(self, name: str) -> SourceDriver:
        try:
            return self._drivers[name]
        except KeyError as exc:
            raise DriverNotRegistered(name) from exc

    def __contains__(self, name: str) -> bool:
        return name in self._drivers

    def names(self) -> tuple[str, ...]:
        return tuple(sorted(self._drivers))


class SourceGateRegistry:
    def __init__(self) -> None:
        self._gates: dict[str, SourceGate] = {}

    def register(self, gate: SourceGate, *, replace: bool = False) -> None:
        if gate.kind in self._gates and not replace:
            raise ValueError(f"gate {gate.kind!r} is already registered")
        self._gates[gate.kind] = gate

    def get_optional(self, kind: str) -> SourceGate | None:
        return self._gates.get(kind)

    def names(self) -> tuple[str, ...]:
        return tuple(sorted(self._gates))
