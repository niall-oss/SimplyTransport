import asyncio
from collections.abc import AsyncGenerator

from advanced_alchemy.base import UUIDBase
from sqlalchemy import MetaData, create_engine, text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from SimplyTransport.lib import settings

from .database import get_async_engine, get_sync_engine
from .timescale_database import get_async_timescale_engine


async def create_database_tables() -> None:
    """
    Creates the database tables.

    This function creates all the tables defined in the SQLAlchemy models
    using the metadata and the database connection from the current session.

    Raises:
        ConnectionRefusedError: If the database connection is refused.
    """
    async_engine = get_async_engine()
    try:
        async with async_engine.begin() as conn:
            await conn.run_sync(UUIDBase.metadata.create_all)
    except ConnectionRefusedError as e:
        print(e)
        print(
            f"\nDatabase connection refused. Please ensure the database is "
            f"running and accessible.\nURL: {async_engine.url}\n"
        )
        raise e

    async_timescale_engine = get_async_timescale_engine()
    try:
        async with async_timescale_engine.begin() as conn:
            await conn.run_sync(UUIDBase.metadata.create_all)
    except ConnectionRefusedError as e:
        print(e)
        print(
            f"\nTimescale database connection refused. Please ensure the database is "
            f"running and accessible.\nURL: {async_timescale_engine.url}\n"
        )
        raise e


def create_database_sync() -> None:
    """Create tables on Postgres and Timescale using sync engines."""
    engine = get_sync_engine()
    try:
        UUIDBase.metadata.create_all(bind=engine)
    except ConnectionRefusedError as e:
        print(e)
        print(
            f"\nDatabase connection refused. Please ensure the database is "
            f"running and accessible.\nURL: {engine.url}\n"
        )
        raise e

    timescale_sync_url = settings.app.TIMESCALE_URL.replace(
        "postgresql+asyncpg://", "postgresql+psycopg2://"
    )
    timescale_engine = create_engine(
        timescale_sync_url, echo=settings.app.DB_ECHO, pool_pre_ping=True
    )
    try:
        UUIDBase.metadata.create_all(bind=timescale_engine)
    except ConnectionRefusedError as e:
        print(e)
        print(
            f"\nTimescale database connection refused. Please ensure the database is "
            f"running and accessible.\nURL: {timescale_engine.url}\n"
        )
        raise e
    finally:
        timescale_engine.dispose()


async def recreate_indexes(table_name: str | None = None):
    """Recreate all indexes

    Args:
        table_name (str | None): The name of the table to recreate indexes for.
        If None, indexes will be recreated for all tables.

    """
    engine = get_sync_engine()
    metadata = MetaData()
    metadata.reflect(bind=engine)

    if table_name is None:
        # recreate index on every table
        for table_name in metadata.tables:
            table = metadata.tables[table_name]
            indexes = list(table.indexes)
            for index in indexes:
                index.drop(bind=engine)
            for index in indexes:
                index.create(bind=engine)
    else:
        table = metadata.tables[table_name]
        indexes = list(table.indexes)
        for index in indexes:
            index.drop(bind=engine)
        for index in indexes:
            index.create(bind=engine)


async def test_database_connections():
    """
    Test the connection to the databases.

    Raises:
        Exception: If the database connection is refused.
    """

    async def check_connection(engine: AsyncEngine, db_name: str) -> None:
        try:
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
        except Exception as e:
            print(e)
            print(
                f"\n{db_name} Database connection refused. Please ensure the database "
                f"is running and accessible.\nURL: {engine.url}\n"
            )
            raise e

    async def main():
        tasks = [
            asyncio.create_task(check_connection(get_async_engine(), "Main")),
            asyncio.create_task(check_connection(get_async_timescale_engine(), "Timescale")),
        ]
        await asyncio.gather(*tasks)

    await main()


async def provide_timescale_db_session() -> AsyncGenerator[AsyncSession]:
    """This provides the Timescale database session."""

    session = AsyncSession(get_async_timescale_engine())
    try:
        async with session.begin():
            yield session
    finally:
        await session.close()
