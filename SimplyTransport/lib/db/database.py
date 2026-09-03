import SimplyTransport.lib.settings as settings
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor

# Patch sqlalchemy module factories before importing create_async_engine into this
# module. A local `from sqlalchemy.ext.asyncio import create_async_engine` binds whatever callable
# the module held at import time; if that happens before instrument(), we keep the unwrapped
# function and never attach EngineTracer (no query spans — only the global Engine.connect wrap
# shows "connect").
SQLAlchemyInstrumentor().instrument(enable_commenter=True)

from advanced_alchemy.config import AsyncSessionConfig  # noqa: E402
from advanced_alchemy.extensions.litestar.plugins import (  # noqa: E402
    SQLAlchemyAsyncConfig,
    SQLAlchemyInitPlugin,
)
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine  # noqa: E402

from .timescale_database import get_async_timescale_engine, get_async_timescale_sessionmaker  # noqa: E402

_async_engine: AsyncEngine | None = None
_async_sessionmaker: async_sessionmaker | None = None


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


def create_sqlalchemy_plugin() -> SQLAlchemyInitPlugin:
    session_config = AsyncSessionConfig(expire_on_commit=False)
    main_config = SQLAlchemyAsyncConfig(
        engine_instance=get_async_engine(),
        session_maker=get_async_sessionmaker(),
        session_config=session_config,
    )
    timescale_config = SQLAlchemyAsyncConfig(
        engine_instance=get_async_timescale_engine(),
        session_maker=get_async_timescale_sessionmaker(),
        session_config=session_config,
        session_dependency_key="timescale_db_session",
        engine_dependency_key="timescale_db_engine",
        session_scope_key="_sqlalchemy_timescale_db_session",
        engine_app_state_key="timescale_db_engine",
        session_maker_app_state_key="timescale_session_maker",
    )
    return SQLAlchemyInitPlugin(config=[main_config, timescale_config])


def reset_engines() -> None:
    """Dispose cached engines so the next access uses current settings."""
    global _async_engine, _async_sessionmaker
    if _async_engine is not None:
        _async_engine.sync_engine.dispose()
        _async_engine = None
    _async_sessionmaker = None
