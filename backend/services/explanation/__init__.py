"""Phase 6 explanation contracts and handler registry."""

from .contracts import (
    ExplanationContext,
    ExplanationGenerator,
    ExplanationType,
    GeneratedExplanation,
    LineageSource,
)
from .registry import (
    DuplicateExplanationHandlerError,
    ExplanationHandlerNotFoundError,
    ExplanationHandlerRegistry,
)

__all__ = [
    "DuplicateExplanationHandlerError",
    "ExplanationContext",
    "ExplanationGenerator",
    "ExplanationHandlerNotFoundError",
    "ExplanationHandlerRegistry",
    "ExplanationType",
    "GeneratedExplanation",
    "LineageSource",
]
