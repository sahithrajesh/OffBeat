"""Environment configuration loaded from .env file."""

import os
from dotenv import load_dotenv

load_dotenv()

SPOTIFY_CLIENT_ID: str = os.environ["SPOTIFY_CLIENT_ID"]
SPOTIFY_CLIENT_SECRET: str = os.environ["SPOTIFY_CLIENT_SECRET"]
SPOTIFY_REDIRECT_URI: str = os.environ["SPOTIFY_REDIRECT_URI"]
LASTFM_API_KEY: str = os.environ["LASTFM_API_KEY"]

# PocketBase
POCKETBASE_URL: str = os.environ.get("POCKETBASE_URL", "http://127.0.0.1:8090")
POCKETBASE_ADMIN_EMAIL: str = os.environ.get("POCKETBASE_ADMIN_EMAIL", "admin@example.com")
POCKETBASE_ADMIN_PASSWORD: str = os.environ.get("POCKETBASE_ADMIN_PASSWORD", "admin12345678")

# JWT session secret – generate a strong random value for production
JWT_SECRET: str = os.environ.get("JWT_SECRET", "change-me-to-a-real-secret")

# Frontend URL for CORS & redirect after login
FRONTEND_URL: str = os.environ.get("FRONTEND_URL", "http://localhost:5173")
