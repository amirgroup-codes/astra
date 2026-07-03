"""
Validator agents for ChemOrigins reference validation.

Validators are imported lazily to avoid dependency issues at import time.
"""

__all__ = [
    "ChemOriginsValidator",
    "ValidationOrchestrator",
]


def __getattr__(name):
    """Lazy import of validators to avoid dependency issues."""
    if name == "ChemOriginsValidator":
        from agents.validators.chemorigins_validator import ChemOriginsValidator
        return ChemOriginsValidator
    elif name == "ValidationOrchestrator":
        from agents.validators.validation_orchestrator import ValidationOrchestrator
        return ValidationOrchestrator
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
