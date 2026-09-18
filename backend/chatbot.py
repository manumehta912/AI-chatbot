"""
Handles all communication with the Google Gemini API.

Keeping this in its own file means main.py stays focused on HTTP concerns,
and the system prompt / model / client setup all live in one obvious place.
"""

import os
from typing import Dict, List

from google import genai
from google.genai import types
from google.genai.errors import APIError, ClientError, ServerError

# ---------------------------------------------------------------------------
# System prompt
#
# This is intentionally kept as a single variable so it's easy to find and
# change later without touching any other logic.
# ---------------------------------------------------------------------------
SYSTEM_PROMPT = (
    "You are a helpful, friendly, general-purpose AI assistant. "
    "Answer questions clearly and concisely. When it improves readability, "
    "format your responses using Markdown (headings, bullet lists, bold "
    "text, and fenced code blocks for code)."
)

DEFAULT_MODEL = "gemini-3.5-flash"
MAX_OUTPUT_TOKENS = 1024


class ChatbotError(Exception):
    """Raised for any problem talking to Gemini, with a user-friendly message."""


_client: genai.Client | None = None


def get_client() -> genai.Client:
    """
    Lazily create (and cache) the Gemini client.

    Lazy creation means the app can still start even if the API key is
    missing — the error only surfaces when a chat request is actually made,
    with a clear explanation instead of crashing on startup.
    """
    global _client
    if _client is None:
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ChatbotError(
                "GEMINI_API_KEY is not set. Add it to your .env file "
                "(copy .env.example to .env first) and restart the server."
            )
        _client = genai.Client(api_key=api_key)
    return _client


def get_model() -> str:
    """Read the model name from the environment, with a sane default."""
    return os.getenv("GEMINI_MODEL") or DEFAULT_MODEL


def _to_gemini_contents(messages: List[Dict[str, str]]) -> List[types.Content]:
    """
    Convert our {"role": "user"|"assistant", "content": str} messages into
    the google-genai SDK's Content objects.

    Gemini uses "model" (not "assistant") as the role for AI turns, so that
    mapping happens here — everywhere else in the app can keep using
    "assistant", which matches what the frontend already sends.
    """
    contents = []
    for message in messages:
        role = "model" if message["role"] == "assistant" else "user"
        contents.append(
            types.Content(role=role, parts=[types.Part.from_text(text=message["content"])])
        )
    return contents


def get_chatbot_response(messages: List[Dict[str, str]]) -> str:
    """
    Send a conversation to Gemini and return the assistant's reply text.

    `messages` must be a list of {"role": "user"|"assistant", "content": str}
    dictionaries, already trimmed/validated by the caller.
    """
    client = get_client()
    model = get_model()
    contents = _to_gemini_contents(messages)

    try:
        response = client.models.generate_content(
            model=model,
            contents=contents,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                max_output_tokens=MAX_OUTPUT_TOKENS,
            ),
        )
    except ClientError as e:
        code = getattr(e, "code", None)
        message = str(getattr(e, "message", None) or e)
        if code in (401, 403) or "API_KEY_INVALID" in message or "UNAUTHENTICATED" in message.upper():
            raise ChatbotError(
                "Authentication with the Gemini API failed. Double-check that "
                "GEMINI_API_KEY in your .env file is correct and active."
            )
        if code == 404 or "not found" in message.lower() or "NOT_FOUND" in message:
            raise ChatbotError(
                f"The Gemini model '{model}' appears to be invalid or "
                "unavailable. Open your .env file and update GEMINI_MODEL "
                "to a currently supported model name."
            )
        if code == 429:
            raise ChatbotError(
                "The Gemini API rate limit or quota was exceeded. Wait a "
                "moment and try again."
            )
        raise ChatbotError(f"The Gemini API rejected the request: {message}")
    except ServerError as e:
        raise ChatbotError(
            f"The Gemini API is currently unavailable ({e}). Please try again shortly."
        )
    except APIError as e:
        raise ChatbotError(f"The Gemini API returned an error: {e}")
    except Exception as e:  # pragma: no cover - safety net
        raise ChatbotError(f"Unexpected error while calling the Gemini API: {e}")

    reply = (getattr(response, "text", None) or "").strip()

    if not reply:
        raise ChatbotError("Gemini returned an empty response. Please try again.")

    return reply
