from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, declarative_base

from app.config import DATABASE_URL

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_recycle=300,  # Neon can drop an idle connection server-side before the client notices
    connect_args={"connect_timeout": 10},  # fail fast instead of hanging forever on a dead route
)


@event.listens_for(engine, "connect")
def _set_statement_timeout(dbapi_connection, _record):
    # Neon's pooled endpoint (the "-pooler" host) rejects statement_timeout as a startup
    # parameter (`options=...`), so it's set as a regular SQL statement on every new
    # connection instead. This bounds any query (including one stuck on a lock) so a stuck
    # connection surfaces as a clear error within 30s instead of hanging forever.
    cursor = dbapi_connection.cursor()
    cursor.execute("SET statement_timeout = 30000")
    cursor.close()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
