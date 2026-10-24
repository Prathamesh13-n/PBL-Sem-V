"""Create the database tables (run once on a fresh install).

    python init_db.py

Safe to run again: existing tables and data are left alone.
Docker:  docker compose run --rm backend python /app/backend/init_db.py
"""
from app.database import Base, engine
from app import models  # noqa: F401  (loads the table definitions)


def main():
    Base.metadata.create_all(bind=engine)
    print("Database tables are ready.")


if __name__ == "__main__":
    main()