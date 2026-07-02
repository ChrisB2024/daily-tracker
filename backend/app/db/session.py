from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings

# SQLAlchemy 2.x async engine. `echo=False` keeps logs clean — flip to True if you
# want to see every SQL statement when debugging.
engine = create_async_engine(settings.database_url, echo=False, future=True)

# A session factory. We don't instantiate sessions directly — we ask the factory
# for one per request via the `get_session` dependency below.
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,  # keeps ORM objects usable after commit; matches FastAPI's request lifecycle
)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency. Yields one session per request and ensures it's closed
    even if the route raises.

    Usage in a route:
        async def endpoint(session: AsyncSession = Depends(get_session)): ...
    """
    async with AsyncSessionLocal() as session:
        yield session
