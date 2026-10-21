from alembic import context
from sqlalchemy import create_engine

from app.config import settings
from app.db.models import Base

target_metadata = Base.metadata


def include_object(obj, name, type_, reflected, compare_to):
    """Only our own tables: the chunk and checkpoint tables belong to the libraries."""
    return not (type_ == "table" and reflected and name not in target_metadata.tables)


def run() -> None:
    # The runner passes its own connection (it holds an advisory lock on it); the CLI does not.
    connection = context.config.attributes.get("connection")
    engine = None
    if connection is None:
        engine = create_engine(settings.database_url_async)
        connection = engine.connect()
    try:
        context.configure(
            connection=connection, target_metadata=target_metadata, include_object=include_object
        )
        with context.begin_transaction():
            context.run_migrations()
        connection.commit()
    finally:
        if engine is not None:
            connection.close()
            engine.dispose()


run()
