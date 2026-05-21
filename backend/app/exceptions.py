class NotFoundError(Exception):
    """Raised when a requested resource does not exist."""


class InvalidIDError(Exception):
    """Raised when a provided ID is not a valid UUID."""


class FileTooLargeError(Exception):
    """Raised when an uploaded file exceeds the size limit."""


class UnsupportedFileTypeError(Exception):
    """Raised when an uploaded file's MIME type is not allowed."""
