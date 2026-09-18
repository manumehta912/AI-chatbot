"""
FastAPI application entrypoint for the simple Gemini chatbot.

Run with:
    uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
"""

import logging
from pathlib import Path
from typing import List, Literal

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator

# config is imported first so its load_dotenv() call runs before chatbot.py
# (or anything else) ever reads GEMINI_API_KEY / GEMINI_MODEL.
from .config import ALLOWED_ORIGINS, MAX_HISTORY_MESSAGES, MAX_MESSAGE_LENGTH
from .chatbot import ChatbotError, get_chatbot_response

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("chatbot")

app = FastAPI(title="Simple Gemini Chatbot")

# ---------------------------------------------------------------------------
# CORS
#
# For local development the frontend is served by this same FastAPI app, so
# the browser and API share one origin and CORS isn't strictly needed. This
# is configured anyway so the API still works if the frontend is ever hosted
# separately. In production, ALLOWED_ORIGINS should be set to only the
# real domain(s) that need access — never "*".
# ---------------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------
class Message(BaseModel):
    role: Literal["user", "assistant"]
    content: str

    @field_validator("content")
    @classmethod
    def validate_content(cls, value: str) -> str:
        if len(value) > MAX_MESSAGE_LENGTH:
            raise ValueError(
                f"Message exceeds the maximum length of {MAX_MESSAGE_LENGTH} characters."
            )
        return value


class ChatRequest(BaseModel):
    messages: List[Message] = Field(..., min_length=1)


class ChatResponse(BaseModel):
    response: str


# ---------------------------------------------------------------------------
# API routes (registered before the static file mount below, so they take
# priority over it)
# ---------------------------------------------------------------------------
@app.get("/api/health")
async def health():
    return {"status": "ok"}


@app.post("/api/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    # Trim history so we never send an unbounded number of messages to Gemini.
    messages = request.messages[-MAX_HISTORY_MESSAGES:]

    if not messages:
        raise HTTPException(status_code=400, detail="No messages provided.")

    last_message = messages[-1]
    if last_message.role != "user":
        raise HTTPException(status_code=400, detail="The last message must be from the user.")
    if not last_message.content.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty.")

    chat_messages = [{"role": m.role, "content": m.content} for m in messages]

    try:
        reply = get_chatbot_response(chat_messages)
    except ChatbotError as e:
        logger.error("Chatbot error: %s", e)
        raise HTTPException(status_code=502, detail=str(e))
    except Exception:
        logger.exception("Unexpected error while handling /api/chat")
        raise HTTPException(status_code=500, detail="An unexpected server error occurred.")

    return ChatResponse(response=reply)


# ---------------------------------------------------------------------------
# Serve the frontend (HTML/CSS/JS) from the same server, so the user only
# needs to run one process and open http://localhost:8000
#
# This is mounted LAST so the /api/* routes above always take priority.
# ---------------------------------------------------------------------------
app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")
