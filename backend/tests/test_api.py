"""
Tests for FastAPI endpoint behaviour (/api/query, /api/courses).

The test app is assembled in conftest.py without static-file mounting so
that these tests run in any environment (no frontend/ directory required).
The RAGSystem is replaced by a MagicMock via the `mock_rag` fixture.
"""
import pytest
from unittest.mock import MagicMock


# ── /api/query ────────────────────────────────────────────────────────────────

class TestQueryEndpoint:
    def test_returns_200_with_valid_body(self, api_client):
        resp = api_client.post("/api/query", json={"query": "What is Python?"})
        assert resp.status_code == 200

    def test_response_contains_required_fields(self, api_client):
        resp = api_client.post("/api/query", json={"query": "Tell me about loops."})
        body = resp.json()
        assert "answer" in body
        assert "sources" in body
        assert "session_id" in body

    def test_answer_is_string(self, api_client):
        resp = api_client.post("/api/query", json={"query": "Explain variables."})
        assert isinstance(resp.json()["answer"], str)

    def test_sources_is_list(self, api_client):
        resp = api_client.post("/api/query", json={"query": "Any question."})
        assert isinstance(resp.json()["sources"], list)

    def test_session_id_auto_created_when_omitted(self, api_client, mock_rag):
        resp = api_client.post("/api/query", json={"query": "Hello?"})
        assert resp.status_code == 200
        mock_rag.session_manager.create_session.assert_called_once()

    def test_provided_session_id_is_passed_through(self, api_client, mock_rag):
        resp = api_client.post(
            "/api/query",
            json={"query": "Follow-up question.", "session_id": "session_42"},
        )
        assert resp.status_code == 200
        assert resp.json()["session_id"] == "session_42"
        # create_session should NOT be called when a session_id is provided
        mock_rag.session_manager.create_session.assert_not_called()

    def test_query_is_forwarded_to_rag(self, api_client, mock_rag):
        api_client.post("/api/query", json={"query": "What are decorators?"})
        call_args = mock_rag.query.call_args
        assert call_args[0][0] == "What are decorators?"

    def test_sources_with_url_serialised_correctly(self, api_client, mock_rag):
        mock_rag.query.return_value = (
            "Answer with source",
            [{"label": "Python Basics — Lesson 1", "url": "https://example.com/1"}],
        )
        resp = api_client.post("/api/query", json={"query": "Any?"})
        sources = resp.json()["sources"]
        assert len(sources) == 1
        assert sources[0]["label"] == "Python Basics — Lesson 1"
        assert sources[0]["url"] == "https://example.com/1"

    def test_sources_with_null_url_serialised_correctly(self, api_client, mock_rag):
        mock_rag.query.return_value = (
            "Answer without URL",
            [{"label": "General knowledge", "url": None}],
        )
        resp = api_client.post("/api/query", json={"query": "Any?"})
        sources = resp.json()["sources"]
        assert sources[0]["url"] is None

    def test_missing_query_field_returns_422(self, api_client):
        resp = api_client.post("/api/query", json={})
        assert resp.status_code == 422

    def test_rag_exception_returns_500(self, api_client, mock_rag):
        mock_rag.query.side_effect = RuntimeError("Vector store unavailable")
        resp = api_client.post("/api/query", json={"query": "Crash?"})
        assert resp.status_code == 500
        assert "Vector store unavailable" in resp.json()["detail"]


# ── /api/courses ──────────────────────────────────────────────────────────────

class TestCoursesEndpoint:
    def test_returns_200(self, api_client):
        resp = api_client.get("/api/courses")
        assert resp.status_code == 200

    def test_response_contains_required_fields(self, api_client):
        body = api_client.get("/api/courses").json()
        assert "total_courses" in body
        assert "course_titles" in body

    def test_total_courses_is_integer(self, api_client):
        body = api_client.get("/api/courses").json()
        assert isinstance(body["total_courses"], int)

    def test_course_titles_is_list(self, api_client):
        body = api_client.get("/api/courses").json()
        assert isinstance(body["course_titles"], list)

    def test_returns_correct_analytics_from_rag(self, api_client, mock_rag):
        mock_rag.get_course_analytics.return_value = {
            "total_courses": 3,
            "course_titles": ["Course A", "Course B", "Course C"],
        }
        body = api_client.get("/api/courses").json()
        assert body["total_courses"] == 3
        assert body["course_titles"] == ["Course A", "Course B", "Course C"]

    def test_empty_catalog_returns_zero_courses(self, api_client, mock_rag):
        mock_rag.get_course_analytics.return_value = {
            "total_courses": 0,
            "course_titles": [],
        }
        body = api_client.get("/api/courses").json()
        assert body["total_courses"] == 0
        assert body["course_titles"] == []

    def test_rag_exception_returns_500(self, api_client, mock_rag):
        mock_rag.get_course_analytics.side_effect = RuntimeError("DB error")
        resp = api_client.get("/api/courses")
        assert resp.status_code == 500
        assert "DB error" in resp.json()["detail"]
