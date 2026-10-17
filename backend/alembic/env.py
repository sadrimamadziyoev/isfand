import os

from alembic import context
from app import models  # noqa: F401 - registers ORM metadata
from app.db import Base
from sqlalchemy import create_engine

config = context.config
url = os.getenv("MIGRATION_DATABASE_URL", os.environ["DATABASE_URL"])
with create_engine(url).connect() as connection:
    context.configure(connection=connection, target_metadata=Base.metadata)
    with context.begin_transaction():
        context.run_migrations()
