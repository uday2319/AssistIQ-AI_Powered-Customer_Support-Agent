import os
from dotenv import load_dotenv

load_dotenv()

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

if not GOOGLE_API_KEY:
    print("GOOGLE_API_KEY is set.")
    raise ValueError("GOOGLE_API_KEY is not set")
print("GOOGLE_API_KEY is set.")
