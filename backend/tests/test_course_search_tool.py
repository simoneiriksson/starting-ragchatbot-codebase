"""
Tests for CourseSearchTool.execute()

Covers:
- Results returned and formatted correctly
- Filters (course_name, lesson_number) forwarded to VectorStore
- Sources tracked after a search
- Error and empty-result paths
"""
import pytest
from unittest.mock import MagicMock, patch

from search_tools import CourseSearchTool
from vector_store import SearchResults


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_results(docs, metas, distances=None):
    return SearchResults(
        documents=docs,
        metadata=metas,
        distances=distances or [0.1] * len(docs),
    )


# ── Tests: return value shape ─────────────────────────────────────────────────

class TestCourseSearchToolExecute:
    def test_returns_string(self, populated_vector_store):
        tool = CourseSearchTool(populated_vector_store)
        result = tool.execute(query="python programming")
        assert isinstance(result, str)

    def test_non_empty_results_contain_content(self, populated_vector_store):
        tool = CourseSearchTool(populated_vector_store)
        result = tool.execute(query="python programming")
        assert len(result) > 0

    def test_result_contains_course_title_header(self, populated_vector_store):
        tool = CourseSearchTool(populated_vector_store)
        result = tool.execute(query="python programming")
        assert "Test Python Course" in result

    def test_result_contains_lesson_header(self, populated_vector_store):
        tool = CourseSearchTool(populated_vector_store)
        result = tool.execute(query="python programming", lesson_number=1)
        assert "Lesson 1" in result

    def test_result_contains_document_text(self, populated_vector_store):
        tool = CourseSearchTool(populated_vector_store)
        result = tool.execute(query="python programming")
        # The stored chunk text should appear in the result
        assert "Python" in result or "python" in result.lower()


# ── Tests: source tracking ────────────────────────────────────────────────────

class TestCourseSearchToolSources:
    def test_last_sources_populated_after_search(self, populated_vector_store):
        tool = CourseSearchTool(populated_vector_store)
        tool.execute(query="python programming")
        assert len(tool.last_sources) > 0

    def test_sources_are_dicts_with_label_and_url(self, populated_vector_store):
        tool = CourseSearchTool(populated_vector_store)
        tool.execute(query="python programming")
        for src in tool.last_sources:
            assert "label" in src, f"'label' key missing from source: {src}"
            assert "url" in src, f"'url' key missing from source: {src}"

    def test_source_label_contains_course_title(self, populated_vector_store):
        tool = CourseSearchTool(populated_vector_store)
        tool.execute(query="python programming")
        labels = [s["label"] for s in tool.last_sources]
        assert any("Test Python Course" in lbl for lbl in labels)

    def test_source_url_is_string_or_none(self, populated_vector_store):
        tool = CourseSearchTool(populated_vector_store)
        tool.execute(query="python programming")
        for src in tool.last_sources:
            assert src["url"] is None or isinstance(src["url"], str)


# ── Tests: filter forwarding ──────────────────────────────────────────────────

class TestCourseSearchToolFilters:
    def test_course_name_filter_forwarded_to_store(self):
        mock_store = MagicMock()
        mock_store.search.return_value = SearchResults(
            documents=["some content"],
            metadata=[{"course_title": "My Course", "lesson_number": 1}],
            distances=[0.1],
        )
        mock_store.get_lesson_link.return_value = "https://example.com/1"

        tool = CourseSearchTool(mock_store)
        tool.execute(query="test", course_name="My Course")

        mock_store.search.assert_called_once_with(
            query="test",
            course_name="My Course",
            lesson_number=None,
        )

    def test_lesson_number_filter_forwarded_to_store(self):
        mock_store = MagicMock()
        mock_store.search.return_value = SearchResults(
            documents=["lesson content"],
            metadata=[{"course_title": "My Course", "lesson_number": 3}],
            distances=[0.1],
        )
        mock_store.get_lesson_link.return_value = None

        tool = CourseSearchTool(mock_store)
        tool.execute(query="variables", lesson_number=3)

        mock_store.search.assert_called_once_with(
            query="variables",
            course_name=None,
            lesson_number=3,
        )

    def test_both_filters_forwarded_together(self):
        mock_store = MagicMock()
        mock_store.search.return_value = SearchResults(
            documents=["content"],
            metadata=[{"course_title": "Course A", "lesson_number": 2}],
            distances=[0.1],
        )
        mock_store.get_lesson_link.return_value = "https://example.com/2"

        tool = CourseSearchTool(mock_store)
        tool.execute(query="test", course_name="Course A", lesson_number=2)

        mock_store.search.assert_called_once_with(
            query="test",
            course_name="Course A",
            lesson_number=2,
        )


# ── Tests: empty / error paths ────────────────────────────────────────────────

class TestCourseSearchToolEdgeCases:
    def test_empty_results_returns_no_content_message(self, empty_vector_store):
        tool = CourseSearchTool(empty_vector_store)
        result = tool.execute(query="anything")
        assert "No relevant content found" in result

    def test_empty_results_with_course_filter_mentions_course(self):
        mock_store = MagicMock()
        mock_store.search.return_value = SearchResults.empty(
            "No course found matching 'Nonexistent'"
        )
        tool = CourseSearchTool(mock_store)
        result = tool.execute(query="test", course_name="Nonexistent")
        # Either the VectorStore error message or the "no results" message
        assert "No" in result or "not found" in result.lower()

    def test_search_error_returned_as_string(self):
        mock_store = MagicMock()
        mock_store.search.return_value = SearchResults.empty("Search error: connection refused")
        tool = CourseSearchTool(mock_store)
        result = tool.execute(query="test")
        assert isinstance(result, str)
        assert "error" in result.lower() or "Search error" in result

    def test_last_sources_empty_when_no_results(self, empty_vector_store):
        tool = CourseSearchTool(empty_vector_store)
        tool.execute(query="anything")
        assert tool.last_sources == []
