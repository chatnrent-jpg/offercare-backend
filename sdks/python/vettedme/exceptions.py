"""VettedMe SDK Exceptions"""


class VettedMeError(Exception):
    """Base exception for all VettedMe errors"""
    pass


class AuthenticationError(VettedMeError):
    """Invalid API key or authentication failed"""
    pass


class NotFoundError(VettedMeError):
    """Resource not found"""
    pass


class ValidationError(VettedMeError):
    """Invalid request data"""
    pass


class RateLimitError(VettedMeError):
    """API rate limit exceeded"""
    pass


class ServerError(VettedMeError):
    """Server-side error"""
    pass
