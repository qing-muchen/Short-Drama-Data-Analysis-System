"""Explicit registry for explanation Generators."""

from __future__ import annotations

from collections.abc import Mapping

from .contracts import ExplanationGenerator, ExplanationType


class DuplicateExplanationHandlerError(ValueError):
    """Raised when a handler would overwrite an existing registration."""


class ExplanationHandlerNotFoundError(LookupError):
    """Raised when no handler is registered for an explanation type."""


class ExplanationHandlerRegistry:
    """Small explicit registry with no dynamic discovery or plugin scanning."""

    def __init__(
        self,
        handlers: Mapping[ExplanationType, ExplanationGenerator] | None = None,
    ) -> None:
        self._handlers: dict[ExplanationType, ExplanationGenerator] = {}
        for explanation_type, generator in (handlers or {}).items():
            self.register(explanation_type, generator)

    def register(
        self,
        explanation_type: ExplanationType,
        generator: ExplanationGenerator,
    ) -> None:
        """Register one handler, refusing accidental replacement."""

        if not isinstance(explanation_type, ExplanationType):
            raise TypeError("explanation_type must be an ExplanationType")
        if explanation_type in self._handlers:
            raise DuplicateExplanationHandlerError(
                f"Handler already registered for {explanation_type.value}"
            )
        if not callable(getattr(generator, "generate", None)):
            raise TypeError("generator must implement generate(context)")
        self._handlers[explanation_type] = generator

    def get_handler(self, explanation_type: ExplanationType) -> ExplanationGenerator:
        """Return a registered handler or raise a descriptive lookup error."""

        if not isinstance(explanation_type, ExplanationType):
            raise TypeError("explanation_type must be an ExplanationType")
        try:
            return self._handlers[explanation_type]
        except KeyError as error:
            raise ExplanationHandlerNotFoundError(
                f"No explanation handler registered for {explanation_type.value}"
            ) from error

    def __contains__(self, explanation_type: object) -> bool:
        return explanation_type in self._handlers

    def __len__(self) -> int:
        return len(self._handlers)


__all__ = [
    "DuplicateExplanationHandlerError",
    "ExplanationHandlerNotFoundError",
    "ExplanationHandlerRegistry",
]
