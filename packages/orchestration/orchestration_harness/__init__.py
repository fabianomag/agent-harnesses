"""Public API for the clean-room Orchestration Harness."""

from .errors import (
    CollisionError,
    HarnessError,
    LockBusyError,
    RecoveryError,
    RecoveryRequiredError,
    StateError,
    TransactionError,
    ValidationError,
)
from .service import ControlPlane

__all__ = [
    "CollisionError",
    "ControlPlane",
    "HarnessError",
    "LockBusyError",
    "RecoveryError",
    "RecoveryRequiredError",
    "StateError",
    "TransactionError",
    "ValidationError",
]

__version__ = "0.1.0"
