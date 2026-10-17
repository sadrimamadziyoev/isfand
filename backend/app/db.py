from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from .config import settings


class Base(DeclarativeBase):
    pass


engine = create_engine(settings.database_url, pool_pre_ping=True)
Session = sessionmaker(engine, expire_on_commit=False)


def scope(db, company_id):
    db.execute(
        text("SELECT set_config('app.company_id', :id, true)"), {"id": str(company_id)}
    )


def get_db():
    with Session() as db:
        try:
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
