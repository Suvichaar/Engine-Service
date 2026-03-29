"""Model router that selects narrative model clients based on Mode."""

from __future__ import annotations

from typing import Mapping

from app.domain.dto import Mode
from app.domain.interfaces import ModelClient, ModelRouter


class ModelRoutingError(KeyError):
    """Raised when no model client is registered for the requested mode."""


class DefaultModelRouter(ModelRouter):
    """Router that resolves model clients using a mapping keyed by Mode."""

    def __init__(self, clients: Mapping[Mode, ModelClient]) -> None:
        if not clients:
            raise ValueError("Model router requires at least one client.")
        self._clients = dict(clients)

    def route(self, mode: str | Mode) -> ModelClient:
        resolved_mode = self._resolve_mode(mode)
        try:
            return self._clients[resolved_mode]
        except KeyError as exc:
            raise ModelRoutingError(f"No model client registered for mode '{resolved_mode.value}'.") from exc

    def _resolve_mode(self, mode: str | Mode) -> Mode:
        if isinstance(mode, Mode):
            return mode
        try:
            return Mode(mode.lower())
        except ValueError as exc:
            raise ModelRoutingError(f"Unsupported mode '{mode}'.") from exc


__all__ = ["DefaultModelRouter", "ModelRoutingError"]

