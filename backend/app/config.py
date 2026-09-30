import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
GOOGLE_PLACES_API_KEY = os.getenv("GOOGLE_PLACES_API_KEY")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

JWT_SECRET = os.getenv("JWT_SECRET")
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_MINUTES = int(os.getenv("JWT_EXPIRE_MINUTES", str(60 * 24 * 7)))

# Cheap model for extraction/fallback/chat; stronger model for itinerary planning.
EXTRACTION_MODEL = os.getenv("EXTRACTION_MODEL", "claude-haiku-4-5")
CHAT_MODEL = os.getenv("CHAT_MODEL", "claude-haiku-4-5")
PLANNER_MODEL = os.getenv("PLANNER_MODEL", "claude-sonnet-5")

CORS_ORIGINS = [
    o.strip()
    for o in os.getenv("CORS_ORIGINS", "http://localhost:8081,http://localhost:19006,http://127.0.0.1:8081").split(",")
    if o.strip()
]

MAX_MESSAGES_PER_DAY = int(os.getenv("MAX_MESSAGES_PER_DAY", "300"))
