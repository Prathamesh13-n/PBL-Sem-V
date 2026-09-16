# Backend – Cloud Resource Provisioning Portal

FastAPI + PostgreSQL backend.

## Local Setup

1. **Install PostgreSQL** (if not already installed) and create a database:
   ```sql
   CREATE DATABASE portal_db;
   CREATE USER portal_user WITH PASSWORD 'portal_pass';
   GRANT ALL PRIVILEGES ON DATABASE portal_db TO portal_user;
   ```

2. **Create a virtual environment and install dependencies:**
   ```bash
   cd backend
   python3 -m venv venv
   source venv/bin/activate        # Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```

3. **Set up environment variables:**
   ```bash
   cp .env.example .env
   # edit .env with your real DATABASE_URL and a random SECRET_KEY
   ```

   Generate a random secret key:
   ```bash
   python3 -c "import secrets; print(secrets.token_hex(32))"
   ```

4. **Run the server:**
   ```bash
   uvicorn app.main:app --reload
   ```

5. **Verify it's working:**
   - Open http://127.0.0.1:8000 → should show `{"message": "Provisioning Portal API is running"}`
   - Open http://127.0.0.1:8000/health → should show `{"status": "ok", "database": "connected"}`
   - Open http://127.0.0.1:8000/docs → interactive Swagger UI (this is what Day 10 testing will use)

## Project Structure
```
backend/
├── app/
│   ├── __init__.py
│   ├── main.py        # FastAPI app + routes
│   ├── config.py       # Settings loaded from .env
│   ├── database.py     # SQLAlchemy engine/session
│   └── models.py       # (Day 5) SQLAlchemy table models
├── requirements.txt
├── .env.example
├── .gitignore
└── README.md
```

## Git Setup
```bash
cd backend
git init
git add .
git commit -m "Day 4: FastAPI + PostgreSQL project scaffolding"
```

Then create a repo on GitHub and push:
```bash
git remote add origin <your-repo-url>
git branch -M main
git push -u origin main
```

**Important:** `.env` is in `.gitignore` — never commit real credentials or your `SECRET_KEY`.
