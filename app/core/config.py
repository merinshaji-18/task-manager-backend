import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    PROJECT_NAME: str = "Task Manager API"
    SECRET_KEY: str = os.getenv("SECRET_KEY", "your-super-secret-64-character-key")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    DATABASE_URL:str ="postgresql://postgres:geobhavan@localhost:5432/task_manager"

settings = Settings()