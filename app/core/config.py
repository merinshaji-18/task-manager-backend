import os
from dotenv import load_dotenv

# Load the .env file
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = os.getenv("ALGORITHM")
BREVO_API_KEY = os.getenv("BREVO_API_KEY")
# Convert to int because env variables are always strings
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", 30))