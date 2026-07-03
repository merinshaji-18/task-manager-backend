from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
import traceback

from app.database.connection import engine, Base
from app.api import tasks, auth
from app.models.user import User 
from app.models.task import Task 
from app.core.scheduler import scheduler

# Create tables (Only works for NEW tables)
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Task Manager API")

# 1. NUCLEAR CORS - Allows everything to stop the "Fake" CORS error
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 2. EMERGENCY REPAIR - This forces the columns into your Neon DB
@app.on_event("startup")
def repair_database():
    print("--- ATTEMPTING DATABASE REPAIR ---")
    try:
        with engine.connect() as conn:
            # Fix Users
            conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS google_access_token VARCHAR;"))
            conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS google_refresh_token VARCHAR;"))
            conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS google_token_expiry VARCHAR;"))
            # Fix Tasks
            conn.execute(text("ALTER TABLE tasks ADD COLUMN IF NOT EXISTS calendar_event_id VARCHAR;"))
            conn.execute(text("ALTER TABLE tasks ADD COLUMN IF NOT EXISTS google_event_id VARCHAR;"))
            conn.execute(text("ALTER TABLE tasks ADD COLUMN IF NOT EXISTS notification_sent BOOLEAN DEFAULT FALSE;"))
            # Create Notifications Table
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS notifications (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER,
                    task_id INTEGER,
                    message TEXT,
                    is_read BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                );
            """))
            conn.commit()
            print("--- DATABASE REPAIRED SUCCESSFULLY ---")
    except Exception as e:
        print(f"--- REPAIR FAILED: {e} ---")

# 3. GLOBAL ERROR LOGGER - If the app crashes, it will show the REAL error in the browser
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={
            "message": str(exc),
            "traceback": traceback.format_exc()
        },
        headers={"Access-Control-Allow-Origin": "*"}
    )

# 4. SCHEDULER LOGIC
@app.on_event("startup")
def start_scheduler():
    if not scheduler.running:
        scheduler.start()

@app.on_event("shutdown")
def stop_scheduler():
    scheduler.shutdown()

# 5. ROUTES
app.include_router(auth.router)
app.include_router(tasks.router)

@app.get("/")
def home():
    return {"message": "Welcome to the Task Manager API"}

@app.get("/debug-db")
def debug_db():
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name = 'users'"))
            columns = [row[0] for row in result]
            return {"columns_found_in_users_table": columns}
    except Exception as e:
        return {"error": str(e)}