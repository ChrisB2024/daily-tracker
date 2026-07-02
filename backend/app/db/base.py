from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """
    Single declarative base. Every model inherits from this so Alembic/SQLAlchemy
    can discover them via `Base.metadata`.
    """

    pass
