from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text, inspect
from sqlalchemy.orm import Session

from app.database import get_db, engine
from app.routes_auth import router as auth_router
from app.routes_requests import router as requests_router

app = FastAPI(
    title="Cloud Resource Provisioning Portal API",
    description="Backend for the EC2 self-service provisioning portal",
    version="0.1.0",
)

# Allows the React dev server to call this API from the browser.
# In production this should be restricted to the real frontend domain.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5174",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(requests_router)


@app.get("/")
def root():
    return {"message": "Provisioning Portal API is running"}


@app.get("/health")
def health_check(db: Session = Depends(get_db)):
    """Confirms the API is up AND can talk to PostgreSQL."""
    db.execute(text("SELECT 1"))
    return {"status": "ok", "database": "connected"}


@app.get("/db-check")
def db_check():
    """Lists tables that actually exist in the database (created via init_db.py)."""
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    return {"tables_found": tables}