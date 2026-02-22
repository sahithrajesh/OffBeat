"""Environment configuration loaded from .env file."""

import os
from dotenv import load_dotenv

load_dotenv()

SPOTIFY_CLIENT_ID: str = os.environ["SPOTIFY_CLIENT_ID"]
SPOTIFY_CLIENT_SECRET: str = os.environ["SPOTIFY_CLIENT_SECRET"]
SPOTIFY_REDIRECT_URI: str = os.environ["SPOTIFY_REDIRECT_URI"]
LASTFM_API_KEY: str = os.environ["LASTFM_API_KEY"]
