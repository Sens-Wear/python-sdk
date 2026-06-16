"""SDK exception types."""


class SenswearError(Exception):
    """Base exception for SDK errors."""


class SenswearDependencyError(SenswearError, ImportError):
    """Raised when an optional runtime dependency is missing."""


class DeviceNotFoundError(SenswearError):
    """Raised when no matching SensWear BLE peripheral is discovered."""


class NotConnectedError(SenswearError):
    """Raised when a GATT operation is attempted before connecting."""


class ProtocolError(SenswearError):
    """Raised when firmware data does not match the expected protocol."""

