import SimplyTransport.lib.settings as settings
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor

SQLAlchemyInstrumentor().instrument(enable_commenter=True)

from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine  # noqa: E402

_async_timescale_engine: AsyncEngine | None = None
_async_timescale_sessionmaker: async_sessionmaker | None = None


def get_async_timescale_engine() -> AsyncEngine:
    global _async_timescale_engine
    if _async_timescale_engine is None:
        _async_timescale_engine = create_async_engine(
            settings.app.TIMESCALE_URL,
            echo=settings.app.DB_ECHO,
            pool_pre_ping=True,
        )
    return _async_timescale_engine


def get_async_timescale_sessionmaker() -> async_sessionmaker:
    global _async_timescale_sessionmaker
    if _async_timescale_sessionmaker is None:
        _async_timescale_sessionmaker = async_sessionmaker(
            get_async_timescale_engine(), expire_on_commit=False
        )
    return _async_timescale_sessionmaker


def async_timescale_session_factory(**kwargs):
    """Return a new async Timescale session from the lazy sessionmaker."""
    return get_async_timescale_sessionmaker()(**kwargs)


def reset_timescale_engines() -> None:
    """Dispose cached Timescale engines so the next access uses current settings."""
    global _async_timescale_engine, _async_timescale_sessionmaker
    if _async_timescale_engine is not None:
        _async_timescale_engine.sync_engine.dispose()
        _async_timescale_engine = None
    _async_timescale_sessionmaker = None
