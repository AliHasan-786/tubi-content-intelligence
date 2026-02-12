"""
ASGI entrypoint convenience module.

Many deployment platforms expect `app:app` by default.
"""

from backend.main import app  # noqa: F401

