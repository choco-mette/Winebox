"""WineBox common utilities and exceptions."""

from winebox.common.exceptions import (
    WineboxError,
    SystemDependencyError,
    PolicyValidationError,
    PrefixAuditError,
    PrefixLockError,
    ExecutionError,
    ResourceNotFoundError,
)

__all__ = [
    "WineboxError",
    "SystemDependencyError",
    "PolicyValidationError",
    "PrefixAuditError",
    "PrefixLockError",
    "ExecutionError",
    "ResourceNotFoundError",
]

