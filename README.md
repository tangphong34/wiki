# Wiki Agentic RAG Platform

Enterprise-grade Wiki & Agentic RAG backend built with **FastAPI**, **LangChain** (PDF parsing), and **Dify** (AI/RAG/Agent engine).

FastAPI acts as the orchestrator: it handles API requests, document processing, and database management. Dify handles all AI workloads — embeddings, knowledge retrieval, and streaming chat. FastAPI does **not** call LLM APIs (OpenAI/Claude) directly.

---

## Architecture

```
┌─────────────┐     HTTP/SSE      ┌──────────────────────────────────────┐
│   React     │ ───────────────►  │            FastAPI (C:\wiki)          │
│  Frontend   │ ◄───────────────  │  Auth · Upload · Chat · Orchestration │
└─────────────┘                   └───────┬──────────────┬─────────────────┘
                                          │              │
                              LangChain   │              │  REST API
                              PDF Parse   │              │
                                          ▼              ▼
                                   ┌──────────┐   ┌─────────────┐
                                   │  SQLite  │   │ Dify Engine │
                                   │ (local)  │   │ cloud/local │
                                   └──────────┘   └─────────────┘
```

### Data flow

**Document upload**
```
PDF upload → FastAPI saves metadata (status: processing)
          → LangChain extracts text page-by-page
          → Dify ingests text into Knowledge Base
          → FastAPI updates status (completed / failed)
```

**Chat (SSE streaming)**
```
User query → FastAPI forwards to Dify (stream mode)
          → Dify retrieves relevant chunks + LLM response
          → FastAPI relays SSE stream to frontend
```

### Component roles

| Component | Responsibility |
|-----------|----------------|
| **FastAPI** | REST API, orchestration, CORS, exception handling |
| **LangChain + PyMuPDF** | Advanced PDF parsing (text, tables, page metadata) |
| **SQLite** | App metadata: documents, conversations, users (phase 1) |
| **Dify** | Knowledge base, embeddings, RAG retrieval, AI chat streaming |

---

## Project structure

```
wiki/
├── app/
│   ├── main.py                 # FastAPI app, CORS, global error handlers
│   ├── dependencies.py         # Auth dependencies (bypassed in phase 1)
│   ├── core/
│   │   ├── config.py           # Pydantic settings from .env
│   │   └── security.py         # JWT + password hashing
│   ├── database/
│   │   ├── session.py          # SQLAlchemy engine & sessions
│   │   └── models.py           # User, Workspace, Document, Conversation
│   ├── services/
│   │   ├── dify_service.py     # Dify API wrapper (ingest + chat stream)
│   │   └── parser_service.py   # LangChain PDF parsing
│   └── routers/
│       ├── auth.py             # Signup / login
│       ├── documents.py        # PDF upload → parse → Dify ingest
│       └── chat.py             # SSE streaming chat via Dify
├── data/
│   └── wiki.db                 # SQLite database (auto-created)
├── setup/
│   ├── init_sqlite.ps1         # Initialize / reset SQLite DB
│   └── sqlite-tools-win-x64-3530400/
│       └── sqlite3.exe         # Optional CLI for DB inspection
├── .env                        # Environment config (not committed)
├── .env.example                # Template for .env
├── requirements.txt
└── README.md
```

---

## Prerequisites

- **Python 3.11+**
- **Dify account** (cloud) or **self-hosted Dify** (Docker)
- No PostgreSQL required for phase 1 (SQLite is used)

---

## Quick start

### 1. Clone / open project

```powershell
cd C:\wiki
```

### 2. Create virtual environment & install dependencies

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Configure environment

```powershell
copy .env.example .env
```

Edit `.env` with your values:

```env
# Required
SECRET_KEY=your-random-secret-at-least-32-chars
DATABASE_URL=sqlite:///./data/wiki.db

# Dify — get from your Dify dashboard
DIFY_API_BASE_URL=https://api.dify.ai
DIFY_API_KEY=app-your-real-api-key
DIFY_DEFAULT_DATASET_ID=your-dataset-id
DIFY_CHAT_APP_ID=your-chat-app-id
```

Generate a secret key:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

### 4. Initialize SQLite database

```powershell
powershell -ExecutionPolicy Bypass -File .\setup\init_sqlite.ps1
```

Expected output:

```
Tables created: users, workspaces, workspace_members, documents, conversations
```

### 5. Start the server

```powershell
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 6. Verify

| Check | URL / Command |
|-------|---------------|
| Health | `curl http://localhost:8000/health` |
| Swagger UI | http://localhost:8000/api/v1/docs |
| OpenAPI JSON | http://localhost:8000/api/v1/openapi.json |

---

## Dify setup

Dify is the AI engine. It can run in the **cloud** or **self-hosted** — your FastAPI app talks to it via REST API only.

### Cloud (recommended for phase 1)

1. Sign up at [https://dify.ai](https://dify.ai)
2. Create a **Dataset** (Knowledge Base) → copy ID to `DIFY_DEFAULT_DATASET_ID`
3. Create a **Chat App** linked to that dataset (enable RAG)
4. Go to **API Access** → copy API Key to `DIFY_API_KEY`
5. Configure an LLM provider inside Dify (OpenAI, Anthropic, Ollama, etc.)

```env
DIFY_API_BASE_URL=https://api.dify.ai
DIFY_API_KEY=app-xxxxxxxx
DIFY_DEFAULT_DATASET_ID=abc123-dataset-id
```

### Self-hosted (local Docker)

1. Install Dify: [https://github.com/langgenius/dify](https://github.com/langgenius/dify)
2. Create dataset + chat app in your local Dify UI
3. Point FastAPI to your instance:

```env
DIFY_API_BASE_URL=http://localhost/v1
DIFY_API_KEY=app-your-local-key
DIFY_DEFAULT_DATASET_ID=your-local-dataset-id
```

> **Note:** LLM API keys are configured inside Dify, not in this FastAPI project.

---

## Phase 1 — development mode

Phase 1 is configured for fast local development:

| Feature | Phase 1 status |
|---------|----------------|
| Authentication (JWT) | **Bypassed** — no token required |
| Workspace permissions | **Bypassed** |
| Database | **SQLite** — no PostgreSQL install |
| Dify integration | **Required** for upload & chat |

Auth bypass is marked with `# PHASE 1` comments in:

- `app/dependencies.py`
- `app/routers/documents.py`
- `app/routers/chat.py`

Re-enable auth in phase 2 by uncommenting the original logic in those files.

---

## API reference

Base URL: `http://localhost:8000`

### Health

```
GET /health
```

### Auth (available but not required in phase 1)

```
POST /api/v1/auth/signup
POST /api/v1/auth/login
```

### Document upload

```
POST /api/v1/documents/upload
Content-Type: multipart/form-data

Fields:
  file          (required) PDF file
  category      (optional) string
  workspace_id  (optional) UUID string
```

**Example (no auth in phase 1):**

```powershell
curl -X POST "http://localhost:8000/api/v1/documents/upload" `
  -F "file=@C:\path\to\document.pdf" `
  -F "category=finance"
```

**Response:**

```json
{
  "id": "uuid",
  "title": "document",
  "status": "completed",
  "dify_document_id": "dify-doc-id"
}
```

### Chat (SSE streaming)

```
POST /api/v1/chat/message
Content-Type: application/json
```

**Body:**

```json
{
  "query": "Summarize the uploaded document",
  "conversation_id": null,
  "workspace_id": null,
  "inputs": {}
}
```

**Example:**

```powershell
curl -N -X POST "http://localhost:8000/api/v1/chat/message" `
  -H "Content-Type: application/json" `
  -d "{\"query\":\"Hello\",\"inputs\":{}}"
```

Response is a **Server-Sent Events (SSE)** stream with Dify event payloads.

---

## Environment variables

| Variable | Required | Description |
|----------|----------|-------------|
| `SECRET_KEY` | Yes | JWT signing key (random string) |
| `DATABASE_URL` | Yes | `sqlite:///./data/wiki.db` (phase 1) |
| `DIFY_API_KEY` | Yes | Dify app API key (`app-...`) |
| `DIFY_DEFAULT_DATASET_ID` | Yes | Target knowledge base dataset ID |
| `DIFY_API_BASE_URL` | No | Default: `https://api.dify.ai` |
| `DIFY_CHAT_APP_ID` | No | Chat app ID (reserved for future use) |
| `CORS_ORIGINS` | No | Allowed frontend origins (JSON array) |
| `MAX_UPLOAD_SIZE_MB` | No | Max PDF upload size (default: 50) |
| `DEBUG` | No | Enable debug logging (default: false) |

---

## Database

### Phase 1: SQLite

- File: `data/wiki.db`
- No server install needed
- Tables created automatically on startup or via `setup/init_sqlite.ps1`

**Inspect with bundled SQLite CLI:**

```powershell
C:\wiki\setup\sqlite-tools-win-x64-3530400\sqlite3.exe C:\wiki\data\wiki.db
```

```sql
.tables
SELECT id, title, status FROM documents;
.quit
```

### Phase 2: PostgreSQL (production)

Update `.env`:

```env
DATABASE_URL=postgresql+psycopg2://wiki_user:wiki_pass@localhost:5432/wiki_db
```

Models use SQLAlchemy types compatible with both SQLite and PostgreSQL.

---

## Troubleshooting

### App won't start — missing env vars

```
ValidationError: secret_key / dify_api_key / database_url Field required
```

→ Fill in all required values in `.env`.

### Upload fails — Dify error

```
502 Document ingestion failed
```

→ Check `DIFY_API_KEY` and `DIFY_DEFAULT_DATASET_ID` in `.env`.
→ Verify the dataset exists in your Dify dashboard.
→ Confirm your Dify instance has an LLM provider configured.

### Chat returns error event

→ Ensure your Dify Chat App has RAG/knowledge retrieval enabled.
→ Verify the chat app API key matches `DIFY_API_KEY`.

### Empty SQLite database

Re-run init script:

```powershell
powershell -ExecutionPolicy Bypass -File .\setup\init_sqlite.ps1
```

### PDF upload rejected

→ Only `.pdf` files are supported in the current version.
→ Check file size against `MAX_UPLOAD_SIZE_MB`.

---

## Roadmap

- [x] Phase 1: FastAPI scaffold, LangChain PDF parsing, Dify proxy
- [x] Phase 1: SQLite local database
- [x] Phase 1: Auth bypass for development
- [ ] Phase 2: Re-enable JWT auth & workspace permissions
- [ ] Phase 2: PostgreSQL + Alembic migrations
- [ ] Phase 2: Background job queue for large PDF ingestion (Celery/ARQ)
- [ ] Phase 3: Workspace CRUD API
- [ ] Phase 3: React frontend integration

---

## License

Private / internal use.
