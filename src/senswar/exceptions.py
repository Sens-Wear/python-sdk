"""SDK exception types."""


class SenswarError(Exception):
    """Base exception for SDK errors."""


class SenswarDependencyError(SenswarError, ImportError):
    """Raised when an optional runtime dependency is missing."""


class DeviceNotFoundError(SenswarError):
    """Raised when no matching Senswar BLE peripheral is discovered."""


class NotConnectedError(SenswarError):
    """Raised when a GATT operation is attempted before connecting."""


class ProtocolError(SenswarError):
    """Raised when firmware data does not match the expected protocol."""
