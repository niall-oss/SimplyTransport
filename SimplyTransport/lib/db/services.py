import asyncio

import rich.progress as rp
from advanced_alchemy.base import UUIDBase
from sqlalchemy import Connection, Table, text
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


def _model_tables(table_name: str | None) -> list[Table]:
    tables = UUIDBase.metadata.tables
    if table_name is not None:
        return [tables[table_name]]
    return list(tables.values())


def _drop_secondary_indexes_sync(sync_conn: Connection, table_name: str) -> None:
    table = UUIDBase.metadata.tables[table_name]
    for index in table.indexes:
        index.drop(bind=sync_conn, checkfirst=True)


def _create_secondary_indexes_sync(sync_conn: Connection, table_name: str) -> None:
    table = UUIDBase.metadata.tables[table_name]
    for index in table.indexes:
        index.create(bind=sync_conn, checkfirst=True)


async def drop_secondary_indexes(table_name: str) -> None:
    """Drop non-primary-key indexes defined on the model for ``table_name``."""
    engine = get_async_engine()
    async with engine.begin() as conn:
        await conn.run_sync(_drop_secondary_indexes_sync, table_name)


async def create_secondary_indexes(table_name: str) -> None:
    """Create non-primary-key indexes defined on the model for ``table_name``."""
    indexes = list(UUIDBase.metadata.tables[table_name].indexes)
    if not indexes:
        return

    engine = get_async_engine()
    with rp.Progress(
        rp.SpinnerColumn(finished_text="✅"),
        "[progress.description]{task.description}",
        rp.BarColumn(),
        rp.MofNCompleteColumn(),
        "|| Taken:",
        rp.TimeElapsedColumn(),
    ) as progress:
        task = progress.add_task(f"[cyan]Rebuilding {table_name} indexes...", total=len(indexes))
        async with engine.begin() as conn:
            await conn.execute(text("SET LOCAL maintenance_work_mem = '256MB'"))
            for index in indexes:

                def _create(sync_conn: Connection, idx=index) -> None:
                    idx.create(bind=sync_conn, checkfirst=True)

                await conn.run_sync(_create)
                progress.update(task, advance=1)


async def recreate_indexes(table_name: str | None = None) -> None:
    """Recreate all indexes

    Args:
        table_name (str | None): The name of the table to recreate indexes for.
        If None, indexes will be recreated for all tables.

    """
    engine = get_async_engine()

    def _recreate(sync_conn: Connection) -> None:
        for table in _model_tables(table_name):
            _drop_secondary_indexes_sync(sync_conn, table.name)
            _create_secondary_indexes_sync(sync_conn, table.name)

    async with engine.begin() as conn:
        await conn.execute(text("SET LOCAL maintenance_work_mem = '256MB'"))
        await conn.run_sync(_recreate)


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
