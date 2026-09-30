import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

import app.models  # noqa: F401  registers every table on Base.metadata before any route runs
from app import config
from app.database import engine
from app.routers import auth, chat, itinerary, places, tracker, trips, weather as weather_router
from app.services import google_places, llm, weather

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("app")

if not config.JWT_SECRET or len(config.JWT_SECRET) < 32:
    raise RuntimeError("JWT_SECRET must be set to a random string of at least 32 characters (see .env.example)")

for _name, _value in (("ANTHROPIC_API_KEY", config.ANTHROPIC_API_KEY), ("GOOGLE_PLACES_API_KEY", config.GOOGLE_PLACES_API_KEY)):
    if not _value:
        log.warning("%s is not set - the features that depend on it will fail", _name)

app = FastAPI(title="Budget Travel Chatbot API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Operational detail goes to the log; clients get a generic message (no config or upstream internals).
@app.exception_handler(llm.LLMUnavailable)
async def _llm_unavailable(_: Request, exc: llm.LLMUnavailable):
    log.error("LLM unavailable: %s", exc)
    return JSONResponse(status_code=503, content={"detail": "The assistant is temporarily unavailable. Please try again in a moment."})


@app.exception_handler(google_places.PlacesError)
async def _places_error(_: Request, exc: google_places.PlacesError):
    log.error("Places error: %s", exc)
    return JSONResponse(status_code=502, content={"detail": "Place information is temporarily unavailable. Please try again."})


@app.exception_handler(weather.WeatherError)
async def _weather_error(_: Request, exc: weather.WeatherError):
    log.error("Weather error: %s", exc)
    return JSONResponse(status_code=502, content={"detail": "Weather is temporarily unavailable."})


for r in (auth, trips, itinerary, tracker, places, chat):
    app.include_router(r.router)
app.include_router(weather_router.router)


@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.get("/health/db")
def db_check():
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return {"database": "connected"}
    except Exception:
        return JSONResponse(status_code=503, content={"database": "unavailable"})
