"""Errors safe to present to a user (never include dialogue or subprocess stderr)."""


class StudioError(Exception):
    """An actionable operation failure."""


class InvalidMediaError(StudioError):
    pass


class SubtitleError(StudioError):
    pass


class OutputConflictError(StudioError):
    pass


class OperationCancelled(StudioError):
    pass
