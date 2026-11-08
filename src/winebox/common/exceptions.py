"""WineBox exception hierarchy."""


class WineboxError(Exception):
    """Base exception for all WineBox errors."""
    pass


class SystemDependencyError(WineboxError):
    """Raised when host dependencies (bwrap, wine, userns) are missing or misconfigured."""
    pass


class PolicyValidationError(WineboxError):
    """Raised when security policy validation fails."""
    pass


class PrefixAuditError(WineboxError):
    """Raised when prefix audit detects security violations or corrupted files."""
    pass


class PrefixLockError(WineboxError):
    """Raised when a prefix is already locked by an active running process."""
    pass


class ExecutionError(WineboxError):
    """Raised when application execution fails."""
    pass


class ResourceNotFoundError(WineboxError):
    """Raised when an application, prefix, or runner is not found."""
    pass
