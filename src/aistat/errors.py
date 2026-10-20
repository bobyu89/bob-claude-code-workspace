"""Error types. Every message is user-facing and written in Traditional Chinese."""


class AistatError(Exception):
    """Base class for all expected, user-facing errors."""


class WorkspaceNotFound(AistatError):
    pass


class DataImportError(AistatError):
    pass


class NotFound(AistatError):
    pass


class PlanError(AistatError):
    pass


class InvalidState(AistatError):
    pass


class EngineUnavailable(AistatError):
    pass


class EngineFailed(AistatError):
    pass
