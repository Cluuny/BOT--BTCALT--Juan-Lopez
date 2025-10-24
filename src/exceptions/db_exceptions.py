class DatabaseError(Exception):
    """Base exception for database errors"""

    pass


class EntityNotFoundError(DatabaseError):
    """Raised when an entity is not found"""

    pass


class DuplicateEntityError(DatabaseError):
    """Raised when trying to create a duplicate entity"""

    pass
