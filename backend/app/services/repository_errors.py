"""Controlled persistence failures shared by repository implementations."""


class RepositoryError(RuntimeError):
    """Base failure raised instead of leaking database client exceptions."""


class UserPersistenceError(RepositoryError):
    """A durable user operation failed."""


class WorkflowPersistenceError(RepositoryError):
    """A durable workflow operation failed."""
