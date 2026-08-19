from stream_orchestrator_django.registry import ServiceRegistry


def test_registry_requires_explicit_registration() -> None:
    registry = ServiceRegistry()
    marker = object()
    registry.register("orchestrator", marker)
    assert registry.get("orchestrator") is marker
