# Frontend Changes

No frontend files were modified in this change.

This implementation added API endpoint testing infrastructure to the backend test suite:

## Files Changed

### `pyproject.toml`
- Added `httpx>=0.27.0` to `[dependency-groups] dev` (required by FastAPI's TestClient)
- Added `[tool.pytest.ini_options]` section:
  - `testpaths = ["backend/tests"]` — pytest discovers tests in the right directory
  - `pythonpath = ["backend"]` — makes backend modules importable without `sys.path` hacks in each file
  - `addopts = "-v"` — verbose output by default

### `backend/tests/conftest.py`
Added imports and three new fixtures above the existing shared data fixtures:
- **`_build_test_app(mock_rag)`** — builds a minimal FastAPI app with `/api/query` and `/api/courses` routes but *without* the static file mount (which requires `frontend/` to exist). This isolates tests from the filesystem.
- **`mock_rag`** fixture — a `MagicMock` pre-configured with sensible defaults that mirrors the `RAGSystem` interface used by the API layer.
- **`api_client`** fixture — a `fastapi.testclient.TestClient` wired to the test app; can be injected into any test that needs HTTP-level testing.

### `backend/tests/test_api.py` (new file)
18 tests across two classes:

**`TestQueryEndpoint`** — covers `POST /api/query`:
- Happy-path status code and response shape
- `session_id` auto-creation when omitted
- Provided `session_id` is passed through unchanged and `create_session` is not called
- Query string is forwarded to `RAGSystem.query()`
- Sources with and without URLs serialise correctly
- Missing `query` field returns HTTP 422
- RAGSystem exception propagates as HTTP 500

**`TestCoursesEndpoint`** — covers `GET /api/courses`:
- Happy-path status code and response shape
- Analytics values from the RAG system are returned verbatim
- Empty catalog (`total_courses=0`) serialises correctly
- RAGSystem exception propagates as HTTP 500
