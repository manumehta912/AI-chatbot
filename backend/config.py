"""
Configuration values for the chatbot backend.

Environment variables are read here (via os.getenv) so the rest of the
codebase doesn't need to know where configuration comes from.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

# Load variables from the .env file (in the project root) into the process
# environment. This must happen before any os.getenv() call below, and
# before chatbot.py reads GEMINI_API_KEY / GEMINI_MODEL — importing
# this config module first (main.py does) guarantees that ordering.
_ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=_ENV_PATH)

# Maximum number of characters allowed in a single chat message.
# Prevents accidentally sending huge payloads to the Gemini API.
MAX_MESSAGE_LENGTH = 8000

# Maximum number of messages (from the conversation history) that will be
# forwarded to Gemini. Keeps request size bounded even if the frontend
# sends a very long history.
MAX_HISTORY_MESSAGES = 50

# Comma-separated list of origins allowed to call this API.
# For local development the FastAPI server serves the frontend itself,
# so the browser and the API share the same origin and CORS isn't even
# strictly required — but it's configured here in case the frontend is
# ever served from somewhere else.
ALLOWED_ORIGINS = os.getenv(
    "ALLOWED_ORIGINS",
    "http://localhost:8000,http://127.0.0.1:8000",
).split(",")
