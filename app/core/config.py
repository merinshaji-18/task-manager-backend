import os
from dotenv import load_dotenv

# Load the .env file
load_dotenv()

class Settings:
    DATABASE_URL: str = os.getenv("DATABASE_URL")
    SECRET_KEY: str = os.getenv("SECRET_KEY")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    
    # NEW: Add Brevo Key here so auth.py can see it
    BREVO_API_KEY: str = os.getenv("BREVO_API_KEY")

# Create a single instance of the settings to be used across the app
settings = Settings()