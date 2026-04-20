"""Storage-layer exceptions."""


class StaleStateError(Exception):
    """Raised when an optimistic version check fails.

    This indicates that another session modified the entity between
    the time it was loaded and the time the save was attempted.
    """
