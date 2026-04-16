import os
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker, DeclarativeBase

from app.config import settings

db_dir = os.path.dirname(settings.DATABASE_PATH)
if db_dir:
    os.makedirs(db_dir, exist_ok=True)

engine = create_engine(
    f"sqlite:///{settings.DATABASE_PATH}", connect_args={"check_same_thread": False}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    Base.metadata.create_all(bind=engine)
    _migrate_existing_tables()


def _migrate_existing_tables():
    inspector = inspect(engine)
    existing_tables = inspector.get_table_names()

    for table in Base.metadata.sorted_tables:
        if table.name not in existing_tables:
            continue
        existing_columns = {col["name"] for col in inspector.get_columns(table.name)}
        for column in table.columns:
            if column.name not in existing_columns:
                col_type = column.type.compile(engine.dialect)
                sql = text(
                    f"ALTER TABLE {table.name} ADD COLUMN {column.name} {col_type}"
                )
                with engine.connect() as conn:
                    conn.execute(sql)
                    conn.commit()
