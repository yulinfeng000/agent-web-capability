"""Protocol-independent application errors."""


class CapabilityError(Exception):
    """Base class for errors safe to expose to callers."""


class InvalidInput(CapabilityError):
    pass


class CapacityExceeded(CapabilityError):
    pass


class OperationTimeout(CapabilityError):
    pass


class UpstreamFailure(CapabilityError):
    pass
