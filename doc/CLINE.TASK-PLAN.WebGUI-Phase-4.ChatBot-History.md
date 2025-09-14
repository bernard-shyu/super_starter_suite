# Phase 4: ChatBOT User History & Core Enhancements

## Overview
Phase 4 focuses on adding **persistent chat history** and core ChatBOT interface improvements to the Super Starter Suite. This phase builds on the in‑memory chat implementation from Phase 3, introducing session management, LlamaIndex memory integration, and a richer UI experience (typing indicators, advanced message formatting, and basic history management UI).

## Goals
1. **Persistent Chat History** – Store and retrieve conversation history across browser sessions and user logins.
2. **Session Management** – Unique session IDs per user/workflow, with ability to start new sessions or resume (load) existing ones.
3. **LlamaIndex Memory Integration** – Leverage LlamaIndex's `ChatMemoryBuffer` (or similar) to keep context for multi‑turn interactions.
4. **Core UI Enhancements** – Typing indicators, error handling UI, basic history navigation, and improved message styling (code block syntax highlighting, timestamps).
5. **Backend API** – Endpoints for saving, loading, and clearing chat history per workflow and session.
6. **Backward Compatibility** – Existing Phase 3 functionality remains functional; new features are additive.

## Phase Breakdown
| Phase | Description |
|-------|-------------|
| **4.1 – LlamaIndex Memory Investigation & Setup** | Research LlamaIndex memory modules, decide on `ChatMemoryBuffer` or `VectorContextRetrieverMemory`, add settings in `settings.<USER-ID>.toml` (e.g., `CHAT_HISTORY_MAX_SIZE`, `CHAT_HISTORY_STORAGE_TYPE`). |
| **4.2 – Backend API for Chat History** | Add FastAPI routes: `POST /api/{workflow}/chat_history/{session_id}`, `GET /api/{workflow}/chat_history/{session_id}`, `DELETE /api/{workflow}/chat_history/{session_id}`. Connect these routes to the chosen LlamaIndex memory backend. |
| **4.3 – Frontend Integration for Persistent History** | On workflow selection, fetch existing history (`GET`). After each exchange, push updated history (`POST`). Manage `session_id` via local storage (or server‑side session for authenticated users). |
| **4.4 – Core UI Enhancements** | Implement typing indicator ("AI is typing…"), improve message bubbles (timestamps, code block syntax highlighting), add error toast UI, and ensure auto‑scroll works with long histories. |
| **4.5 – Dedicated History Management UI** | Sidebar or modal listing saved sessions per workflow, with actions: **New Chat**, **Load History**, **Clear History**. |
| **4.6 – Verification & Testing** | End‑to‑end tests: start a session, close/reopen browser, verify history loads; test error handling; cross‑browser checks (Chrome, Firefox). |

