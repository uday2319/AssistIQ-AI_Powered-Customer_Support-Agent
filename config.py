import os
from dotenv import load_dotenv

load_dotenv()

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
DB_HOST=os.getenv("DB_HOST")
DB_PORT=os.getenv("DB_PORT")
DB_NAME=os.getenv("DB_NAME")
DB_USER=os.getenv("DB_USER")
DB_PASSWORD=os.getenv("DB_PASSWORD")

if not GOOGLE_API_KEY:
    print("GOOGLE_API_KEY is set.")
    raise ValueError("GOOGLE_API_KEY is not set")
print("GOOGLE_API_KEY is set.")

if not DB_PASSWORD:
    raise ValueError("DB_PASSWORD is not set")