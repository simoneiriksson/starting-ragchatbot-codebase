# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Important Notes

- Always use `uv` to run the server, Python files, and manage dependencies. Do not use `pip` directly.

## Running the Application

```bash
# First-time setup
cp .env.example .env   # then add your ANTHROPIC_API_KEY

# Install dependencies
uv sync

# Start the server (from repo root)
./run.sh

# Or manually
cd backend && uv run uvicorn app:app --reload --port 8000
```

The app serves both the API and frontend at `http://localhost:8000`. API docs at `http://localhost:8000/docs`.

## Architecture

This is a full-stack RAG chatbot. The **backend** (`backend/`) is a FastAPI app; the **frontend** (`frontend/`) is plain HTML/CSS/JS served as static files from the same server. Course documents live in `docs/`.

### RAG Pipeline

The core flow for a user query:

1. **`app.py`** receives `POST /api/query`, creates a session if needed, delegates to `RAGSystem`
2. **`rag_system.py`** (`RAGSystem`) is the orchestrator — it calls `AIGenerator` with the `search_course_content` tool available
3. **`ai_generator.py`** makes a first Claude API call; if Claude decides to search, it triggers tool use
4. **`search_tools.py`** (`CourseSearchTool` / `ToolManager`) executes the tool call by querying `VectorStore`
5. **`vector_store.py`** (`VectorStore`) queries ChromaDB — it resolves fuzzy course names via semantic search on `course_catalog`, then fetches content chunks from `course_content`
6. `AIGenerator` makes a second Claude API call with the retrieved chunks to produce the final answer
7. Sources and response are returned to the frontend

### Data Model

Course documents (`.txt`) follow a strict format parsed by `document_processor.py`:
```
Course Title: <title>
Course Link: <url>
Course Instructor: <name>
Lesson 1: <title>
Lesson Link: <url>
...content...
Lesson 2: <title>
...
```

The `DocumentProcessor` chunks lesson content (800 chars, 100 overlap) into `CourseChunk` objects. These are stored in two ChromaDB collections:
- `course_catalog` — one document per course (used for fuzzy course name resolution)
- `course_content` — one document per chunk, filtered by `course_title` and `lesson_number`

### Session Management

`SessionManager` stores conversation history in-memory (keyed by `"session_1"`, `"session_2"`, etc.). History is injected into Claude's system prompt as plain text. Max history is 2 exchanges (configurable via `config.py`).

### Key Configuration (`backend/config.py`)

| Setting | Default | Purpose |
|---|---|---|
| `ANTHROPIC_MODEL` | `claude-sonnet-4-20250514` | Claude model used |
| `EMBEDDING_MODEL` | `all-MiniLM-L6-v2` | Sentence transformer for embeddings |
| `CHUNK_SIZE` | 800 | Characters per content chunk |
| `CHUNK_OVERLAP` | 100 | Overlap between chunks |
| `MAX_RESULTS` | 5 | ChromaDB search results returned |
| `CHROMA_PATH` | `./chroma_db` | Persistent vector store location (relative to `backend/`) |

### Adding a New Tool

Implement `Tool` (abstract base in `search_tools.py`), define `get_tool_definition()` returning an Anthropic-compatible tool schema, implement `execute(**kwargs)`, then register with `tool_manager.register_tool(your_tool)` in `RAGSystem.__init__`.
