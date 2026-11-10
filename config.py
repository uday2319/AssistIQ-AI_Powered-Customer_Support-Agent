import os
from dotenv import load_dotenv

load_dotenv()

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
DB_HOST=os.getenv("DB_HOST")
DB_PORT=os.getenv("DB_PORT")
DB_NAME=os.getenv("DB_NAME")
DB_USER=os.getenv("DB_USER")
DB_PASSWORD=os.getenv("DB_PASSWORD")

# Gemini model used by the agent. Set GEMINI_MODEL in .env to change it.
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.6-flash")

# Where conversations are saved: "postgres" (default) or "memory" (tests).
CHECKPOINT_BACKEND = os.getenv("CHECKPOINT_BACKEND", "postgres").strip().lower()

# Secret key that support staff must send to approve or reject refunds.
# If it is not set, the approval endpoint is disabled.
ADMIN_API_KEY = os.getenv("ADMIN_API_KEY")

if not GOOGLE_API_KEY:
    raise ValueError("GOOGLE_API_KEY is not set")

if not DB_PASSWORD:
    raise ValueError("DB_PASSWORD is not set")
