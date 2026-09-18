# Simple Gemini Chatbot

A minimal, easy-to-understand AI chatbot web app. FastAPI backend, Google
Gemini API for responses, and a plain HTML/CSS/JavaScript frontend — no
React, no database, no Docker, no authentication.

## What it does

- Serves a single-page chat UI (user messages on the right, Gemini's replies
  on the left).
- Sends the full conversation history to Gemini on every message so it has
  context.
- Renders Gemini's replies with basic Markdown (paragraphs, lists, bold,
  code blocks, inline code).
- Keeps conversation memory in the browser's `localStorage`, so it survives
  page reloads and closing/reopening the browser on the same device.
  **Clear Chat** only clears what's on screen — Gemini still remembers
  earlier facts (like your name) for future messages. **Forget Everything**
  permanently erases that memory.

## Requirements

- Python 3.12
- A Gemini API key ([aistudio.google.com/apikey](https://aistudio.google.com/apikey))

## Project structure

```
simple-chatbot/
│
├── backend/
│   ├── main.py            FastAPI app: routes + serves the frontend
│   ├── config.py          Configuration values (limits, CORS origins, .env loading)
│   ├── chatbot.py         Gemini API client, system prompt, error handling
│   ├── __init__.py
│   └── requirements.txt
│
├── frontend/
│   ├── index.html
│   ├── style.css
│   └── script.js
│
├── .env.example
├── .gitignore
└── README.md
```

## Installation

On Ubuntu/Linux:

```bash
sudo apt update
sudo apt install python3 python3-venv python3-pip -y

cd simple-chatbot
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
```

On macOS/Windows, the steps are the same after `cd simple-chatbot` — just
use the Python you already have installed to create the virtual
environment (`python3 -m venv .venv`, or `py -m venv .venv` on Windows).

## Environment variables

Create your `.env` file from the example:

```bash
cp .env.example .env
```

Then open `.env` in a text editor and add your Gemini API key:

```
GEMINI_API_KEY=your-real-key-here
GEMINI_MODEL=gemini-3.5-flash
```

- `GEMINI_API_KEY` — **required**. Get one from
  [Google AI Studio](https://aistudio.google.com/apikey). The app will
  refuse to call Gemini (with a clear error message) until this is set.
- `GEMINI_MODEL` — the Gemini model to use. If you get an error saying the
  model is invalid or unavailable, update this value to a currently
  supported model name (check
  [ai.google.dev/gemini-api/docs/models](https://ai.google.dev/gemini-api/docs/models)
  for the current list) and restart the server.

> **Key type note:** API keys created in Google AI Studio normally start
> with `AIza`. If your key instead starts with `AQ.`, it may have been
> issued as an OAuth-style "auth key" rather than a plain API key, which
> some SDK versions reject with a 401 error even though the key itself is
> valid. If you hit persistent authentication errors, generate a fresh key
> from [aistudio.google.com/apikey](https://aistudio.google.com/apikey) and
> confirm it starts with `AIza` before troubleshooting further.

## How to run

Development (auto-reloads when you edit code):

```bash
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

Then open your browser to:

```
http://localhost:8000
```

Production (no auto-reload):

```bash
uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

For real production use, put this behind a reverse proxy (e.g. nginx or
Caddy) that terminates HTTPS and forwards requests to uvicorn — this app
does not set up HTTPS itself.

## Changing the Gemini model

Edit `GEMINI_MODEL` in your `.env` file and restart the server. No code
changes are needed.

## Changing the system prompt

Open `backend/chatbot.py` and edit the `SYSTEM_PROMPT` variable near the
top of the file. Restart the server afterward.

## How conversation memory works

The app has two layers of memory, kept deliberately separate:

1. **What's on screen** — the visible chat transcript.
2. **What Gemini remembers** — every message ever exchanged, used as
   context for future replies.

Details:

- Every message (yours and Gemini's) is saved to the browser's
  `localStorage` under the key `gemini-chatbot:memory`.
- **Clear Chat** only clears what's *displayed* (tracked via a
  `gemini-chatbot:visible-start` marker) — it does **not** erase Gemini's
  memory. Send a new message afterward and it will still recall earlier
  facts like your name, even though the screen looks empty.
- **Forget Everything** is the button that actually erases memory — it
  wipes both the visible transcript and everything stored in
  `localStorage`, with a confirmation prompt first since it can't be
  undone.
- This is **per-browser, per-device** — it is not stored on the server or
  in a database, and won't follow you to a different browser or computer.
- Only the most recent 200 messages are kept in storage, and the backend
  itself only forwards the most recent 50 to Gemini on each request — so
  memory isn't literally unlimited, but should comfortably cover normal
  use. If a conversation runs long enough to exceed that, the oldest
  facts (e.g. something mentioned very early on) may eventually drop out
  of context.

## API endpoints

### `GET /api/health`

Health check.

**Response:**
```json
{ "status": "ok" }
```

### `POST /api/chat`

Send a conversation to Gemini and get a reply.

**Request:**
```json
{
  "messages": [
    { "role": "user", "content": "What is AWS?" },
    { "role": "assistant", "content": "AWS is..." },
    { "role": "user", "content": "What is EC2?" }
  ]
}
```

Note: the API and frontend both use `"assistant"` for AI turns (matching
the spec this app was built to). Internally, `chatbot.py` translates that
to Gemini's own `"model"` role before calling the Gemini API — you never
need to send `"model"` yourself.

**Response:**
```json
{ "response": "EC2 is..." }
```

**Error response** (4xx/5xx status codes):
```json
{ "detail": "A human-readable explanation of what went wrong." }
```

## Example request (curl)

```bash
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"messages": [{"role": "user", "content": "Hello!"}]}'
```

## Troubleshooting

**"GEMINI_API_KEY is not set" error**
You haven't created a `.env` file, or it's missing the key. Run
`cp .env.example .env`, add your key, and restart the server.

**"Authentication with the Gemini API failed"**
Your API key is invalid, expired, or was issued as an unsupported key type
(see the key type note above). Generate a fresh key at
[aistudio.google.com/apikey](https://aistudio.google.com/apikey) and make
sure it starts with `AIza`.

**"The Gemini model '...' appears to be invalid or unavailable"**
The model name in `GEMINI_MODEL` is no longer supported. Update it in your
`.env` file to a current model name and restart the server.

**"The Gemini API rate limit or quota was exceeded"**
You've hit your plan's request or token limits. Wait a bit, or check your
usage/quota in Google AI Studio.

**Page loads but sending a message does nothing / network error**
Make sure the server is actually running (check the terminal for errors)
and that you're visiting `http://localhost:8000` (not opening `index.html`
directly as a file — the frontend needs to be served by FastAPI so its
`fetch()` calls to `/api/chat` work).

**Port 8000 already in use**
Run on a different port, e.g. `--port 8080`, and open
`http://localhost:8080` instead.

**Changes to frontend files aren't showing up**
Hard-refresh your browser (Ctrl+Shift+R / Cmd+Shift+R) to bypass the
cache.
