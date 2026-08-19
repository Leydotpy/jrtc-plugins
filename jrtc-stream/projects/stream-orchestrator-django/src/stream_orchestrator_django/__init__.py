"""Django integration package.

Objects that depend on configured Django settings are intentionally not imported
at package import time. Import them from their concrete modules after
``django.setup()``.
"""

__all__: list[str] = []
