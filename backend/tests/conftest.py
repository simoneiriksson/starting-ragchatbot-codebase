import sys
import os
import pytest
from unittest.mock import MagicMock
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.testclient import TestClient
from pydantic import BaseModel
from typing import List, Optional

# Make backend/ importable from tests/
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ── Shared data fixtures ──────────────────────────────────────────────────────

@pytest.fixture
def sample_course():
    from models import Course, Lesson
    course = Course(
        title="Test Python Course",
        course_link="https://example.com/python",
        instructor="Test Instructor",
    )
    course.lessons = [
        Lesson(lesson_number=1, title="Introduction",
               lesson_link="https://example.com/python/1"),
        Lesson(lesson_number=2, title="Variables",
               lesson_link="https://example.com/python/2"),
    ]
    return course


@pytest.fixture
def sample_chunks():
    from models import CourseChunk
    return [
        CourseChunk(
            content="Lesson 1 content: Python is a high-level programming language used for many purposes.",
            course_title="Test Python Course",
            lesson_number=1,
            chunk_index=0,
        ),
        CourseChunk(
            content="Variables store data values in Python. You assign them with the = operator.",
            course_title="Test Python Course",
            lesson_number=2,
            chunk_index=1,
        ),
    ]


# ── Vector store fixtures ─────────────────────────────────────────────────────

@pytest.fixture
def temp_chroma_path(tmp_path):
    return str(tmp_path / "test_chroma")


@pytest.fixture
def populated_vector_store(temp_chroma_path, sample_course, sample_chunks):
    from vector_store import VectorStore
    store = VectorStore(temp_chroma_path, "all-MiniLM-L6-v2", max_results=5)
    store.add_course_metadata(sample_course)
    store.add_course_content(sample_chunks)
    return store


@pytest.fixture
def empty_vector_store(temp_chroma_path):
    from vector_store import VectorStore
    return VectorStore(temp_chroma_path, "all-MiniLM-L6-v2", max_results=5)


# ── API test app and client ───────────────────────────────────────────────────
#
# We build a minimal test app that mirrors the real app's routes but without
# mounting static files (which don't exist in the test environment). The
# RAGSystem is replaced by a MagicMock so tests stay fast and isolated.

class QueryRequest(BaseModel):
    query: str
    session_id: Optional[str] = None

class Source(BaseModel):
    label: str
    url: Optional[str] = None

class QueryResponse(BaseModel):
    answer: str
    sources: List[Source]
    session_id: str

class CourseStats(BaseModel):
    total_courses: int
    course_titles: List[str]


def _build_test_app(mock_rag):
    """Return a FastAPI test app whose routes delegate to mock_rag."""
    _app = FastAPI(title="Test RAG App")
    _app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

    @_app.post("/api/query", response_model=QueryResponse)
    async def query_documents(request: QueryRequest):
        try:
            session_id = request.session_id
            if not session_id:
                session_id = mock_rag.session_manager.create_session()
            answer, sources = mock_rag.query(request.query, session_id)
            return QueryResponse(answer=answer, sources=sources, session_id=session_id)
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @_app.get("/api/courses", response_model=CourseStats)
    async def get_course_stats():
        try:
            analytics = mock_rag.get_course_analytics()
            return CourseStats(
                total_courses=analytics["total_courses"],
                course_titles=analytics["course_titles"],
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    return _app


@pytest.fixture
def mock_rag():
    """A MagicMock that mimics the RAGSystem interface used by the API layer."""
    rag = MagicMock()

    # Default happy-path returns
    rag.session_manager.create_session.return_value = "session_1"
    rag.query.return_value = ("This is a test answer.", [])
    rag.get_course_analytics.return_value = {
        "total_courses": 2,
        "course_titles": ["Python Basics", "Advanced FastAPI"],
    }
    return rag


@pytest.fixture
def api_client(mock_rag):
    """TestClient wired to the test app with a mock RAGSystem."""
    test_app = _build_test_app(mock_rag)
    return TestClient(test_app)


# ── Anthropic mock helpers ────────────────────────────────────────────────────

def make_text_response(text: str):
    """Return a mock Anthropic response that contains only a text block."""
    from unittest.mock import MagicMock
    block = MagicMock()
    block.type = "text"
    block.text = text

    resp = MagicMock()
    resp.stop_reason = "end_turn"
    resp.content = [block]
    return resp


def make_tool_use_response(tool_name: str, tool_input: dict, tool_id: str = "toolu_test_001"):
    """Return a mock Anthropic response that requests a tool call."""
    from unittest.mock import MagicMock
    block = MagicMock()
    block.type = "tool_use"
    block.name = tool_name
    block.input = tool_input
    block.id = tool_id

    resp = MagicMock()
    resp.stop_reason = "tool_use"
    resp.content = [block]
    return resp
