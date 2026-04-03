import sys
import os
import pytest

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
