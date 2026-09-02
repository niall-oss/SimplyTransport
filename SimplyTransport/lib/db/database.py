import SimplyTransport.lib.settings as settings
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor

# Patch sqlalchemy module factories before importing create_engine / create_async_engine into this
# module. A local `from sqlalchemy import create_engine` binds whatever callable the module held
# at import time; if that happens before instrument(), we keep the unwrapped function and never
# attach EngineTracer (no query spans — only the global Engine.connect wrap shows "connect").
SQLAlchemyInstrumentor().instrument(enable_commenter=True)

from advanced_alchemy.config import AsyncSessionConfig  # noqa: E402
from advanced_alchemy.extensions.litestar.plugins import (  # noqa: E402
    SQLAlchemyAsyncConfig,
    SQLAlchemyInitPlugin,
)
from sqlalchemy import Engine, create_engine  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

_sync_engine: Engine | None = None
_async_engine: AsyncEngine | None = None
_async_sessionmaker: async_sessionmaker | None = None


def get_sync_engine() -> Engine:
    global _sync_engine
    if _sync_engine is None:
        _sync_engine = create_engine(settings.app.DB_URL_SYNC, echo=settings.app.DB_ECHO, pool_pre_ping=True)
    return _sync_engine


def get_async_engine() -> AsyncEngine:
    global _async_engine
    if _async_engine is None:
        _async_engine = create_async_engine(
            settings.app.DB_URL,
            echo=settings.app.DB_ECHO,
            pool_pre_ping=True,
        )
    return _async_engine


def get_async_sessionmaker() -> async_sessionmaker:
    global _async_sessionmaker
    if _async_sessionmaker is None:
        _async_sessionmaker = async_sessionmaker(get_async_engine(), expire_on_commit=False)
    return _async_sessionmaker


def async_session_factory(**kwargs):
    """Return a new async session from the lazy sessionmaker."""
    return get_async_sessionmaker()(**kwargs)


def get_sync_session() -> Session:
    """Return a new short-lived sync session."""
    return Session(get_sync_engine())


def create_sqlalchemy_plugin() -> SQLAlchemyInitPlugin:
    session_config = AsyncSessionConfig(expire_on_commit=False)
    sqlalchemy_config = SQLAlchemyAsyncConfig(
        engine_instance=get_async_engine(), session_config=session_config
    )
    return SQLAlchemyInitPlugin(config=sqlalchemy_config)


def reset_engines() -> None:
    """Dispose cached engines so the next access uses current settings."""
    global _sync_engine, _async_engine, _async_sessionmaker
    if _sync_engine is not None:
        _sync_engine.dispose()
        _sync_engine = None
    if _async_engine is not None:
        _async_engine.sync_engine.dispose()
        _async_engine = None
    _async_sessionmaker = None
