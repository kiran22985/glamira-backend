import logging
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .config import settings
from .routers import auth, parlors, partner_auth

logging.basicConfig(level=logging.INFO)

# Schema is managed by Alembic migrations (`alembic upgrade head`), run on
# deploy — see README. The app no longer creates tables at startup.
app = FastAPI(title="Glamira API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve uploaded files (e.g. avatars) from /media.
os.makedirs("media/avatars", exist_ok=True)
app.mount("/media", StaticFiles(directory="media"), name="media")

app.include_router(auth.router)
app.include_router(partner_auth.router)
app.include_router(parlors.router)


@app.get("/health", tags=["health"])
async def health():
    return {"status": "ok"}
