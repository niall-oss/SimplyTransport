import asyncio

from advanced_alchemy.base import UUIDBase
from sqlalchemy import Connection, MetaData, Table, text
from sqlalchemy.ext.asyncio import AsyncEngine

from .database import get_async_engine
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


async def recreate_indexes(table_name: str | None = None) -> None:
    """Recreate all indexes

    Args:
        table_name (str | None): The name of the table to recreate indexes for.
        If None, indexes will be recreated for all tables.

    """
    engine = get_async_engine()

    def _recreate(sync_conn: Connection) -> None:
        metadata = MetaData()
        metadata.reflect(bind=sync_conn)
        tables: list[Table] = (
            [metadata.tables[table_name]] if table_name is not None else list(metadata.tables.values())
        )
        for table in tables:
            indexes = list(table.indexes)
            for index in indexes:
                index.drop(bind=sync_conn)
            for index in indexes:
                index.create(bind=sync_conn)

    async with engine.connect() as conn:
        await conn.run_sync(_recreate)
        await conn.commit()


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
