// Simple Gemini Chatbot — frontend logic
// No frameworks, no build step: just talks to /api/chat and /api/health.

(function () {
  "use strict";

  const messagesEl = document.getElementById("messages");
  const formEl = document.getElementById("chat-form");
  const inputEl = document.getElementById("message-input");
  const sendBtn = document.getElementById("send-btn");
  const clearBtn = document.getElementById("clear-btn");
  const forgetBtn = document.getElementById("forget-btn");
  const loadingEl = document.getElementById("loading-indicator");
  const errorBannerEl = document.getElementById("error-banner");

  // ---------------------------------------------------------------------
  // Memory model
  //
  // `memory` is the full conversation Gemini uses for context. It is
  // persisted to localStorage and is NOT cleared by "Clear Chat" — that
  // button only hides the transcript from view (via `visibleStart`, the
  // index into `memory` where the currently-shown transcript begins).
  // Only "Forget Everything" actually erases `memory` itself.
  //
  // This is still per-browser, per-device storage — nothing is saved on
  // the server or in a database.
  // ---------------------------------------------------------------------
  const MEMORY_KEY = "gemini-chatbot:memory";
  const VISIBLE_START_KEY = "gemini-chatbot:visible-start";
  const MAX_STORED_MESSAGES = 200;

  function loadMemory() {
    try {
      const raw = localStorage.getItem(MEMORY_KEY);
      const parsed = raw ? JSON.parse(raw) : [];
      return Array.isArray(parsed) ? parsed : [];
    } catch {
      // Corrupted data, storage disabled, or private-browsing restrictions —
      // fall back to empty memory rather than breaking the app.
      return [];
    }
  }

  function loadVisibleStart(memoryLength) {
    try {
      const raw = localStorage.getItem(VISIBLE_START_KEY);
      const n = raw ? parseInt(raw, 10) : 0;
      if (!Number.isFinite(n) || n < 0) return 0;
      return Math.min(n, memoryLength);
    } catch {
      return 0;
    }
  }

  let memory = loadMemory();
  let visibleStart = loadVisibleStart(memory.length);

  function persistState() {
    try {
      // Cap stored memory so it never grows unbounded; shift visibleStart
      // by the same amount so it still points at the right message.
      if (memory.length > MAX_STORED_MESSAGES) {
        const overflow = memory.length - MAX_STORED_MESSAGES;
        memory = memory.slice(overflow);
        visibleStart = Math.max(0, visibleStart - overflow);
      }
      localStorage.setItem(MEMORY_KEY, JSON.stringify(memory));
      localStorage.setItem(VISIBLE_START_KEY, String(visibleStart));
    } catch {
      // Storage full or unavailable — the chat still works for this
      // session, it just won't be remembered next time.
    }
  }

  const MAX_MESSAGE_LENGTH = 8000;

  // ---------------------------------------------------------------------
  // Rendering helpers
  // ---------------------------------------------------------------------
  function renderMarkdown(text) {
    // marked converts Markdown -> HTML; DOMPurify strips anything unsafe
    // before it's injected into the page.
    if (window.marked && window.DOMPurify) {
      const rawHtml = window.marked.parse(text, { breaks: true });
      return window.DOMPurify.sanitize(rawHtml);
    }
    // Fallback: if the CDN scripts failed to load, escape and show as
    // plain text so nothing unsafe is ever rendered.
    return escapeHtml(text);
  }

  function escapeHtml(text) {
    const div = document.createElement("div");
    div.textContent = text;
    return div.innerHTML;
  }

  function addMessageToUI(role, content) {
    const bubble = document.createElement("div");
    bubble.className = "message " + (role === "user" ? "user" : "assistant");

    if (role === "user") {
      // User text is inserted as plain text (never HTML) to avoid any
      // possibility of injecting markup via the input box.
      bubble.textContent = content;
    } else {
      bubble.innerHTML = renderMarkdown(content);
    }

    messagesEl.appendChild(bubble);
    messagesEl.scrollTop = messagesEl.scrollHeight;
    return bubble;
  }

  function showError(message) {
    errorBannerEl.textContent = message;
    errorBannerEl.hidden = false;
  }

  function clearError() {
    errorBannerEl.hidden = true;
    errorBannerEl.textContent = "";
  }

  function setLoading(isLoading) {
    loadingEl.hidden = !isLoading;
    sendBtn.disabled = isLoading;
    inputEl.disabled = isLoading;
  }

  // ---------------------------------------------------------------------
  // Auto-resize the textarea as the user types (up to a max height set in CSS)
  // ---------------------------------------------------------------------
  function autoResizeInput() {
    inputEl.style.height = "auto";
    inputEl.style.height = Math.min(inputEl.scrollHeight, 140) + "px";
  }
  inputEl.addEventListener("input", autoResizeInput);

  // Enter sends the message, Shift+Enter inserts a newline.
  inputEl.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      formEl.requestSubmit();
    }
  });

  // ---------------------------------------------------------------------
  // Sending a message
  // ---------------------------------------------------------------------
  async function sendMessage(text) {
    clearError();

    memory.push({ role: "user", content: text });
    addMessageToUI("user", text);
    persistState();

    inputEl.value = "";
    autoResizeInput();
    setLoading(true);

    try {
      const res = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ messages: memory }),
      });

      let data;
      try {
        data = await res.json();
      } catch (parseErr) {
        throw new Error("The server returned an unreadable response.");
      }

      if (!res.ok) {
        const detail = (data && data.detail) || "Something went wrong. Please try again.";
        throw new Error(detail);
      }

      const reply = data.response;
      memory.push({ role: "assistant", content: reply });
      addMessageToUI("assistant", reply);
      persistState();
    } catch (err) {
      // Remove the optimistically-added user message from memory so a
      // retry doesn't duplicate it, but leave it visible in the UI so the
      // user can see what they tried to send.
      memory.pop();
      persistState();

      if (err instanceof TypeError) {
        // fetch() throws a TypeError on network failure (e.g. server down).
        showError("Network error: could not reach the server. Is it running?");
      } else {
        showError(err.message || "An unexpected error occurred.");
      }
    } finally {
      setLoading(false);
      inputEl.focus();
    }
  }

  formEl.addEventListener("submit", (event) => {
    event.preventDefault();

    const text = inputEl.value.trim();
    if (!text) {
      showError("Please enter a message before sending.");
      return;
    }
    if (text.length > MAX_MESSAGE_LENGTH) {
      showError(`Message is too long (max ${MAX_MESSAGE_LENGTH} characters).`);
      return;
    }

    sendMessage(text);
  });

  clearBtn.addEventListener("click", () => {
    // Hide the transcript from view without erasing what Gemini remembers —
    // new messages will still have full earlier context.
    visibleStart = memory.length;
    messagesEl.innerHTML = "";
    clearError();
    inputEl.value = "";
    autoResizeInput();
    inputEl.focus();
    persistState();
  });

  forgetBtn.addEventListener("click", () => {
    const confirmed = window.confirm(
      "This will permanently erase everything Gemini remembers about this " +
        "conversation, including your name and anything else you've shared. " +
        "This cannot be undone. Continue?"
    );
    if (!confirmed) return;

    memory = [];
    visibleStart = 0;
    messagesEl.innerHTML = "";
    clearError();
    inputEl.value = "";
    autoResizeInput();
    inputEl.focus();

    try {
      localStorage.removeItem(MEMORY_KEY);
      localStorage.removeItem(VISIBLE_START_KEY);
    } catch {
      // Nothing more to do if storage is unavailable — in-memory state is
      // already cleared, which is what matters for this session.
    }
  });

  // ---------------------------------------------------------------------
  // Restore whatever is currently visible (i.e. everything from
  // visibleStart onward) into the UI on page load. Anything hidden by a
  // past "Clear Chat" stays hidden, but is still part of `memory` and
  // still sent to Gemini as context.
  // ---------------------------------------------------------------------
  function restoreConversation() {
    for (const message of memory.slice(visibleStart)) {
      if (message && (message.role === "user" || message.role === "assistant") && message.content) {
        addMessageToUI(message.role, message.content);
      }
    }
  }
  restoreConversation();

  // ---------------------------------------------------------------------
  // Startup: quick health check so a misconfigured backend is obvious
  // ---------------------------------------------------------------------
  async function checkHealth() {
    try {
      const res = await fetch("/api/health");
      if (!res.ok) throw new Error();
    } catch {
      showError("Could not reach the backend server. Please check that it is running.");
    }
  }

  checkHealth();
  inputEl.focus();
})();
