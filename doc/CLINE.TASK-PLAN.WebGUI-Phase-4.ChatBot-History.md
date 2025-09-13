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
| **4.0 – LlamaIndex Memory Investigation & Setup** | Research LlamaIndex memory modules, decide on `ChatMemoryBuffer` or `VectorContextRetrieverMemory`, add settings in `settings.<USER-ID>.toml` (e.g., `CHAT_HISTORY_MAX_SIZE`, `CHAT_HISTORY_STORAGE_TYPE`). |
| **4.1 – Backend API for Chat History** | Add FastAPI routes: `POST /api/{workflow}/chat_history/{session_id}`, `GET /api/{workflow}/chat_history/{session_id}`, `DELETE /api/{workflow}/chat_history/{session_id}`. Connect these routes to the chosen LlamaIndex memory backend. |
| **4.2 – Frontend Integration for Persistent History** | On workflow selection, fetch existing history (`GET`). After each exchange, push updated history (`POST`). Manage `session_id` via local storage (or server‑side session for authenticated users). |
| **4.3 – Core UI Enhancements** | Implement typing indicator ("AI is typing…"), improve message bubbles (timestamps, code block syntax highlighting), add error toast UI, and ensure auto‑scroll works with long histories. |
| **4.4 – Dedicated History Management UI** | Sidebar or modal listing saved sessions per workflow, with actions: **New Chat**, **Load History**, **Clear History**. |
| **4.5 – Verification & Testing** | End‑to‑end tests: start a session, close/reopen browser, verify history loads; test error handling; cross‑browser checks (Chrome, Firefox). |

---

# Phase 5: Workflows & Multi‑Agents Enhancement

## Overview
Phase 5 establishes a **pluggable architecture** for adding new workflows and multi‑agent capabilities. It finalizes the integration of complex workflow‑specific UI components (e.g., `ui_event.jsx` for `code‑generator` and `cli_human_input.tsx` for `human_in_the_loop`) and provides a framework for future workflow extensions.

## Goals
1. **Workflow‑Specific UI Component Integration** – Fully integrate existing React/TSX components, or provide vanilla‑JS equivalents where appropriate.
2. **Pluggable Workflow System** – Define a clear plugin interface so new workflows can be dropped into the system with minimal code changes.
3. **Multi‑Agent Orchestration** – Enable workflows that involve multiple agents (e.g., a "research‑then‑write" pipeline) with shared context.
4. **Extensible Configuration** – Add configuration entries for enabling/disabling workflows and agents.
5. **Documentation & Testing** – Provide developer docs for creating new workflow plugins and comprehensive tests.

## Phase Breakdown
| Phase | Description |
|-------|-------------|
| **5.0 – Architecture Design** | Define plugin interface (Python classes, FastAPI router registration, frontend component registry). |
| **5.1 – Plugin System Implementation** | Implement dynamic discovery of workflow modules, auto‑register routes, and expose metadata to the frontend. |
| **5.2 – UI Component Integration** | Refactor `ui_event.jsx` and `cli_human_input.tsx` into reusable components; set up a lightweight React build (Vite/Webpack) or provide vanilla‑JS fallbacks. |
| **5.3 – Multi‑Agent Framework** | Introduce a coordinator service that can chain multiple agents, share LlamaIndex memory, and expose a unified API endpoint. |
| **5.4 – Documentation & Testing** | Write developer guides, add unit/integration tests for the plugin system, and verify multi‑agent pipelines. |

---

# Next Steps
- Implement Phase 4.0–4.5 (persistent history, UI, API).
- Begin Phase 5.0–5.4 in parallel once Phase 4 foundations are stable.
- Update project documentation and onboarding guides to reflect the new pluggable workflow model.

*Prepared by Cline – Software Engineer*  
*Date: 2025‑08‑27*
