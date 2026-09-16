"""
Run this once to create all tables defined in app/models.py.

Usage:
    python init_db.py

Safe to re-run: create_all() only creates tables that don't already exist,
it never drops or overwrites existing data.
"""

from app.database import engine, Base
from app import models  # noqa: F401  (import needed so models register with Base)


def main():
    print("Creating tables...")
    Base.metadata.create_all(bind=engine)
    print("Done. Tables created:")
    for table_name in Base.metadata.tables.keys():
        print(f"  - {table_name}")


if __name__ == "__main__":
    main()