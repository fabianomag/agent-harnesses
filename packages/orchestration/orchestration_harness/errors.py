"""Domain errors with stable public exit behavior."""


class HarnessError(Exception):
    """Base class for expected harness failures."""


class ValidationError(HarnessError):
    """Input or persisted state violates a closed contract."""


class CollisionError(ValidationError):
    """An ID, alias, or path collides with registered state."""


class StateError(HarnessError):
    """The requested lifecycle transition is not currently valid."""


class LockBusyError(HarnessError):
    """Another writer owns the portable workspace lock."""


class RecoveryRequiredError(HarnessError):
    """A durable journal must be recovered before further mutation."""


class RecoveryError(HarnessError):
    """Recovery cannot proceed without risking unrelated data."""


class TransactionError(HarnessError):
    """A mutation failed and was rolled back."""
